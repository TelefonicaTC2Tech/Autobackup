import re
from dataclasses import dataclass
from typing import Iterator
from socket import error as SocketError
from paramiko.ssh_exception import (
    SSHException,
    AuthenticationException,
    NoValidConnectionsError,
)
from fabric import Connection
from fabric.transfer import Result as TransferResult
from invoke.exceptions import UnexpectedExit
from pydantic import SecretStr

from settings import (
    BASH_BACKUPS_SCRIPT,
    DEFAULT_SSH_USERNAME,
)

from ssh.group import SerialRecursiveSSHGroup
from ssh.responders import Responder, SSH_CONNECTION_YES_NO_FINGERPRINT_RESPONDER
from ssh.commands import TargetBashScript, TargetExecutionResult
from ssh.base import SSHConnectionData, DEFAULT_SHELL_PROMPT_PATTERN
from ssh.exceptions import (
    GatewaySessionInactiveError,
    GatewaySSHConnectionError,
    InvalidTargetCommandError,
)

from features.stations.exceptions import (
    CorruptedDataFileError,
    MachinePasswordMissingError,
)


REMOTE_BACKUP_FILEPATH_REGEX = re.compile(r'Backup file .* copied to .*?:(/.+?\.nozomi_backup)')


@dataclass
class BackupResult:
    """
    Represents the outcome of running the backup script on one target.
    """
    gateway: SSHConnectionData
    target: SSHConnectionData
    execution_result: TargetExecutionResult
    remote_backup_filepath: str | None


@dataclass
class RemoteFileCopyResult:
    remote: str                                  # remote filepath you asked for
    local: str                                   # local destination
    success: bool                                # overall outcome
    result: TransferResult | None = None         # present only on success
    error: Exception | None = None               # present only on failure


class BackupsRunner:
    def __init__(
            self,
            station_data: list[dict],
            station_secrets: dict[str, str],
            script_timeout: float,          # seconds
            connection_timeout: float,      # seconds
            shell_prompt_timeout: float,    # seconds
            verbose: bool,
            ssh_username: str = DEFAULT_SSH_USERNAME,
        ):
        self.station_data = station_data
        self.station_secrets = station_secrets
        self.ssh_username = ssh_username

        self.script_timeout = script_timeout
        self.connection_timeout = connection_timeout
        self.shell_prompt_timeout = shell_prompt_timeout
        
        self.verbose = verbose

    def build_scp_responders(self, password: str) -> list[Responder]:
        """ build passwor responder for the scp(secure copy) command """
        scp_password_responder = Responder(
            pattern=r'(?i)password .*:',  # case-insensitive match
            response= password + '\n'
        )

        return [scp_password_responder, SSH_CONNECTION_YES_NO_FINGERPRINT_RESPONDER]
    
    def get_machine_password(self, machine_external_ip: str) -> str:
        password = self.station_secrets.get(machine_external_ip, None)
        if password is None:
            raise MachinePasswordMissingError(f"No password configured for machine IP {machine_external_ip}")

        return password
    
    def get_gateway_machine(self) -> dict:
        """
        Return the single ``type == "CMC"`` record for this station.

        Raises
        ------
        CorruptedDataFileError
            If zero or more than one CMC entry is found.
        """
        cmc_list = [m for m in self.station_data if m["type"] == "CMC"]
        if len(cmc_list) != 1:
            # each station should only have one CMC
            raise CorruptedDataFileError(
                f"Expected exactly one CMC entry, found {len(cmc_list)}."
            )
        return cmc_list[0]
    
    def get_target_machines(self) -> list[dict]:
        """
        Return the subset of ``self.station_data`` eligible for backup
        (currently: type == "GUARDIAN" and state != "pendiente").
        """
        return [
            m
            for m in self.station_data
            if m["type"] == "GUARDIAN" and m["state"] != "pendiente"
        ]
    
    def build_gateway_ssh_connection_data_instance(self) -> SSHConnectionData:
        cmc_data = self.get_gateway_machine()
        cmc_password = self.get_machine_password(machine_external_ip= cmc_data["ip_external"])

        connection_data = SSHConnectionData(
            host= cmc_data["ip_external"],
            user= self.ssh_username,
            password= SecretStr(cmc_password),
            internal_host= cmc_data["ip_internal"],
        )
        
        return connection_data

    def build_target_ssh_connection_data_instances(self) -> list[SSHConnectionData]:
        """
        Build SSHConnectionData objects for each machine returned by
        the method `get_target_machines`.
        """
        targets_connection_data: list[SSHConnectionData] = []

        for machine in self.get_target_machines():                
            external_ip = machine["ip_external"]
            password = self.get_machine_password(machine_external_ip= external_ip)
            
            c_data = SSHConnectionData(
                host= external_ip,
                user= self.ssh_username,
                password= SecretStr(password),
                internal_host= machine["ip_internal"]
            )

            targets_connection_data.append(c_data)


        return targets_connection_data
    
    def copy_remote_file_to_local_machine(
            self,
            remote_filepath: str,
            local_destination: str,
            ssh_user: str,
            ssh_host: str,
            ssh_password: str,
        ) -> RemoteFileCopyResult:
        """Copy *remote_filepath* to *local_destination*, always returning a result wrapper."""
        # building Fabric connection
        fabric_connection = Connection(
            f"{ssh_user}@{ssh_host}",
            connect_kwargs={"password": f"{ssh_password}"}
        )

        try:
            # coping backup file from the gateway(the CMC) to my local machine
            result = fabric_connection.get(remote_filepath, local_destination)

            return RemoteFileCopyResult(
                success= True,
                local= result.local,
                remote= result.remote,
                result= result,
                error= None,
            )

        # network / auth / banner / TCP problems
        except (
            TimeoutError, # socket.timeout is just an alias to TimeoutError
            SocketError,
            AuthenticationException,
            NoValidConnectionsError,            
            SSHException,
        ) as e:
            return RemoteFileCopyResult(
                success= False,
                local= local_destination,
                remote= remote_filepath,
                result= None,
                error= e,
            )
        
        except UnexpectedExit as e:
            return RemoteFileCopyResult(
                success= False,
                local= local_destination,
                remote= remote_filepath,
                result= None,
                error= e,   
            )
    

    def _run_and_extract_backup_path(
        self,
        group: SerialRecursiveSSHGroup,
        target: SSHConnectionData,
        script: TargetBashScript,
    ) -> BackupResult:
        """
        Runs the backup script on `target` via `group.gateway_data`,
        parses out the .nozomi_backup filepath (or None), and
        returns a BackupResult.
        """
        try:
            t_result = group.run_target(target=target, commands=[script], hide= not self.verbose)
        except (
            GatewaySessionInactiveError,
            GatewaySSHConnectionError,
        ) as e:
            # session-level errors are raised by run_target if gateway goes down
            return BackupResult(
                gateway= group.gateway_data,
                target= target,
                execution_result= TargetExecutionResult(
                    success= False,
                    outputs= [],
                    error= e
                ),
                remote_backup_filepath= None
            )     

        # now handle target-level errors or timeouts without aborting whole run:
        if not t_result.success:
            return BackupResult(
                gateway= group.gateway_data,
                target= target,
                execution_result= t_result,
                remote_backup_filepath= None
            )
        
        script_output, _ = t_result.outputs[0]
        match = REMOTE_BACKUP_FILEPATH_REGEX.search(script_output)

        # extract remote backup filepath
        remote_path = match.group(1) if match else None

        return BackupResult(
            gateway= group.gateway_data,
            target= target,
            execution_result= t_result,
            remote_backup_filepath= remote_path
        )

    def backup_generator(self) -> Iterator[BackupResult]:
        """
        For each GUARDIAN target:
        1. Runs the backup script on the target via the CMC gateway.
        2. Parses out the remote .nozomi_backup filepath (or yields None).
        3. Yields (host, remote_path, result) so the caller can handle fetching.
        """
        script_file = BASH_BACKUPS_SCRIPT
        
        gateway_connection_data = self.build_gateway_ssh_connection_data_instance()
        targets_connection_data = self.build_target_ssh_connection_data_instances()

        scp_responders = self.build_scp_responders(password= gateway_connection_data.password.get_secret_value())

        script_cmd = TargetBashScript(
            script= script_file,
            args= [
                gateway_connection_data.user,
                gateway_connection_data.host,    
            ],
            from_file= True,
            run_as_root= True,
            responders= scp_responders,
            timeout= self.script_timeout,
            hide_output= not self.verbose,
        )

        serial_ssh_group = SerialRecursiveSSHGroup(
            gateway_data= gateway_connection_data,
            targets= targets_connection_data,
            shell_gateway_prompt_pattern= DEFAULT_SHELL_PROMPT_PATTERN,
            shell_target_prompt_pattern= DEFAULT_SHELL_PROMPT_PATTERN,
            connection_timeout= self.connection_timeout,
            shell_prompt_timeout= self.shell_prompt_timeout
        )
        try:
            for target in serial_ssh_group.targets:
                backup_result = self._run_and_extract_backup_path(
                    group= serial_ssh_group,
                    target= target,
                    script= script_cmd
                )
            
                if not backup_result.execution_result.success:
                    # covers both “target-level” errors and generic failures
                    # this foces the session to start from zero for the next target
                    serial_ssh_group.close()

                yield backup_result
                
        except InvalidTargetCommandError as e:
            raise e
        finally:
            serial_ssh_group.close()

