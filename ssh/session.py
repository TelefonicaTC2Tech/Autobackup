from .base import (
    SSHConnectionData,
    InternalExitCode,
)
from .responders import (
    Responder,
    get_ssh_login_password_responder,
    SSH_CONNECTION_YES_NO_FINGERPRINT_RESPONDER,
)
from .formatter import CommandFormatter
from .connection import SSHConnection
from .exceptions import (
    GatewaySSHConnectionError,
    TargetSSHConnectionError,
    GatewaySessionInactiveError,
    TargetSessionInactiveError,
    CommandTimeoutError
)


class RecursiveSSHSession:
    """
    Manages a two-hop SSH session: first connecting to a gateway (intermediate) host,
    then establishing a persistent interactive shell session to a target (final) host.
    
    The class ensures the target connection remains valid and can execute commands 
    remotely at the final destination, optionally as root.
    """

    SSH_TARGET_CONNECTION_EXITCODE = "__SSH_TARGET_CONNECTION_EXITCODE"
    TARGET_SESSION_EXITCODE_DELIMITER = "__TARGET_EXITCODE"

    # Session state variable keys
    TARGET_SESSION_VAR = "__TARGET_SESSION"
    GATEWAY_SESSION_VAR = "__GATEWAY_SESSION"
    SESSION_VAR_VALUE = "__OK__"

    def __init__(self, gateway_data: SSHConnectionData, target_data: SSHConnectionData) -> None:
        """
        Initializes the RecursiveSSHSession with credentials for the gateway and destination hosts.

        Args:
            gateway_data: SSHConnectionData
                Connection data for the intermediate (gateway) machine.
            destination_data: SSHConnectionData
                Connection data for the target (final) machine.
        """        
        self.gateway = SSHConnection(
            hostname= gateway_data.host,
            username= gateway_data.user,
            password= gateway_data.password.get_secret_value(),
            port= gateway_data.port
        )
        self.target_data = target_data

    def _verify_env_variable(
            self, var_name: str, hide: bool, error_msg: str
        ) -> None:
        """
        Internal helper to check whether a specific shell environment variable
        exists in the current session.

        Args:
            var_name (str): Name of the shell environment variable to check.
            hide (bool): Whether to suppress output from the command.
            error_msg (str): Error message to raise if the variable is not found.

        Raises:
            RuntimeError: If the variable is not present in the shell session.
        """
        cmd = f"echo exists: $?{var_name}"
            
        output, _ = self.gateway.run(
            command=cmd,
            timeout=10,
            hide=hide,
        )
        if "exists: 0" in output:
            raise RuntimeError(error_msg)

    def verify_target_session_token(self, hide: bool = False) -> None:
        """
        Checks if the target shell session is still active by verifying
        the presence of a specific environment variable.

        This variable must have been set previously when establishing the
        target connection. If it is not found, the session is considered broken.

        Args:
            hide (bool): If True, suppresses command output during the check.

        Raises:
            TargetSessionInactive: If the session variable is not present, indicating the
                                    target connection is inactive or has been closed.
        """
        try:
            self._verify_env_variable(
                var_name= self.TARGET_SESSION_VAR,
                hide= hide,
                error_msg= "Target SSH session shell seems inactive — unable to verify connection variable."
            )
        except RuntimeError as e:
            raise TargetSessionInactiveError(str(e)) from e
    
    def verify_gateway_session_token(self, hide: bool = False) -> None:
        """
        Checks if the gateway shell session is still active by verifying
        the presence of a specific environment variable.

        This variable must have been set during the initial gateway connection setup.
        If it is not present, the session is considered invalid or terminated.

        Args:
            hide (bool): If True, suppresses command output during the check.

        Raises:
            GatewaySessionInactive: If the session variable is not present, indicating the
                                    gateway session is inactive.
        """
        try:
            self._verify_env_variable(
                var_name= self.GATEWAY_SESSION_VAR,
                hide= hide,
                error_msg= "Gateway SSH session shell unable to verify connection variable."
            )
        except RuntimeError as e:
            raise GatewaySessionInactiveError(str(e)) from e

    def establish_gateway_connection(
            self,
            shell_prompt_pattern: str,
            verbose: bool = False,
            connection_timeout: float = 60,
            shell_prompt_timeout: float = 60,
        ) -> None:
        """
        Establishes an SSH connection to the gateway host and marks the session as active.

        If the gateway session is not already open, this method connects to it and sets a
        shell environment variable to mark the session as valid. This token is later used
        to verify that commands are running in the correct session context.

        Args:
            verbose (bool): Whether to display SSH output during connection.
            shell_prompt_pattern (str): Regex pattern to detect when the shell is ready.
            connection_timeout (float): Timeout in seconds for the SSH connection.
            shell_prompt_timeout (float): Timeout in seconds to wait for the shell prompt after login.

        Raises:
            GatewaySSHConnectionError: If the connection to the gateway fails.
        """
        if (
            self.gateway.channel is None or
            self.gateway.channel.closed
        ):
            try:
                self.gateway.connect(
                    verbose= verbose,
                    connection_timeout= connection_timeout,
                    shell_prompt_timeout= shell_prompt_timeout,
                    shell_prompt_pattern= shell_prompt_pattern
                )
            except Exception as e:
                raise GatewaySSHConnectionError("Error occurred while establishing gateway connection") from e
            
            # set shell variable
            cmd = CommandFormatter.set_shell_env_variable_raw_command(
                key= self.GATEWAY_SESSION_VAR,
                value= self.SESSION_VAR_VALUE    
            )
            self.gateway.run(
                command= cmd,
                timeout= 10,
                hide= not verbose,
            )

            self.verify_gateway_session_token(hide= not verbose)

    def establish_target_host_connection(
            self,
            shell_prompt_pattern, 
            verbose: bool = False,
            shell_prompt_timeout: float = 90,
        ) -> None:
        """
        Connects from the gateway host to the target host via interactive SSH and validates the session.

        This method initiates an SSH connection to the target machine from within the
        gateway session. It handles first-time host key confirmation and password prompts
        automatically using responders. Once connected, it sets a shell variable to mark
        the target session as active.

        Args:
            verbose (bool): Whether to show SSH output during connection.
            shell_prompt_pattern (str): Regex pattern to detect the target shell prompt.
            shell_prompt_timeout (float): Timeout in seconds to wait for the shell prompt on the target.

        Raises:
            TargetSSHConnectionError: If the connection to the target host fails or does not reach the expected prompt.
        """
        try:
            self.verify_gateway_session_token(hide= not verbose)
        except RuntimeError as e:
            raise TargetSSHConnectionError(
                "SSH connection to the target host should only be made from the gateway session"
            ) from e
        
        password_responder = get_ssh_login_password_responder(password= self.target_data.password.get_secret_value())

        add_ssh_to_hostfile_responder = SSH_CONNECTION_YES_NO_FINGERPRINT_RESPONDER

        cmd = f'ssh {self.target_data.user}@{self.target_data.host}'

        output, exit_code = self.gateway.run(
            command= cmd,
            hide= not verbose,
            responders= [add_ssh_to_hostfile_responder, password_responder],
            break_on= shell_prompt_pattern,
            timeout= shell_prompt_timeout,
            exitcode_delimiter= self.SSH_TARGET_CONNECTION_EXITCODE,
        )



        if exit_code != InternalExitCode.BREAK_TRIGGERED:
            raise TargetSSHConnectionError(
                f"Failed to connect to target host — SSH exited or did not reach prompt.\n"
                f"Exit code: {exit_code}\n"
                f"Output:\n{output}"
            )

        # set shell variable
        cmd = CommandFormatter.set_shell_env_variable_raw_command(
            key= self.TARGET_SESSION_VAR,
            value= self.SESSION_VAR_VALUE,
        )
        try:
            self.gateway.run(
                command= cmd,
                exitcode_delimiter= self.TARGET_SESSION_EXITCODE_DELIMITER,
                timeout= 10,
                hide= not verbose,
            )
        except (TimeoutError, CommandTimeoutError) as e:
            raise TargetSSHConnectionError("Erro occured while setting the shell varible") from e
        
        try:
            self.verify_target_session_token(hide= not verbose)
        except TargetSessionInactiveError as e:
            raise TargetSSHConnectionError(
                "Target shell conection varible could NOT be verify after establishign the target connection"
            ) from e

    def connect(
            self,
            shell_gateway_prompt_pattern: str,
            shell_target_prompt_pattern: str,
            verbose: bool = False,
            connection_timeout: float = 60,
            shell_prompt_timeout: float = 90,
        ) -> None:
        """
        Establishes the full two-hop SSH session: first to the gateway,
        then from the gateway to the target host.

        This method delegates to both `establish_gateway_connection` and
        `establish_target_host_connection` to ensure the entire path is ready
        for executing commands remotely.

        Args:
            verbose (bool): Whether to display SSH output during connection.
            shell_gateway_prompt_pattern (str): Regex used to detect the shell prompt in the gateway session.
            shell_target_prompt_pattern (str): Regex used to detect the shell prompt in the target session.
            connection_timeout (float): Timeout (in seconds) to establish the SSH connection to the gateway.
            shell_prompt_timeout (float): Timeout (in seconds) to wait for shell prompts after each hop.
        """
        self.establish_gateway_connection(
            verbose= verbose,
            connection_timeout= connection_timeout,
            shell_prompt_timeout= shell_prompt_timeout,
            shell_prompt_pattern= shell_gateway_prompt_pattern,
        )
        self.establish_target_host_connection(
            verbose= verbose,
            shell_prompt_timeout= shell_prompt_timeout,
            shell_prompt_pattern= shell_target_prompt_pattern,
        )

    def run_at_target(
            self,
            command: str,
            hide: bool = False,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            timeout: float = 30.0,
        ) -> tuple[str, int]:
        """
        Executes a command on the target host via the active SSH session.

        This method assumes the connection to the target has already been established.

        Args:
            command (str): Command to execute, already formatted with exit code handling.
            hide (bool): Whether to suppress command output.
            responders (list[Responder] | None): Optional responders for handling interactive prompts.
            break_on (str | None): Optional regex pattern to break execution early.
            timeout (float): Max time to wait for command completion.

        Returns:
            tuple[str, int]: Cleaned output and command exit code.

        Raises:
            RuntimeError: If the target session is not active.
        """       
        self.verify_target_session_token(hide= hide)

        return self.gateway.run(
            command= command,
            hide= hide,
            responders= responders,
            timeout= timeout,
            break_on= break_on,
            exitcode_delimiter= self.TARGET_SESSION_EXITCODE_DELIMITER
        )
    
    def run_as_root_at_target(
            self,
            command: str,
            password: str,
            hide: bool = False,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            timeout: float = 30.0,
        ) -> tuple[str, int]:
        """
        Executes a preformatted root-level command on the target host.

        Args:
            formatted_command (str): Command to execute as root.
            password (str): Password for `sudo` prompt handling.
            hide (bool): Whether to suppress output during execution.
            responders (list[Responder] | None): Optional additional responders.
            break_on (str | None): Optional regex pattern to break execution early.
            timeout (float): Max time to wait for command completion.

        Returns:
            tuple[str, int]: Cleaned output and command exit code.

        Raises:
            RuntimeError: If the target session is not active.
        """
        self.verify_target_session_token(hide= hide)

        return self.gateway.run_as_root(
            command= command,
            password= password,
            hide= hide,
            responders= responders,            
            break_on= break_on,
            timeout= timeout,
            exitcode_delimiter= self.TARGET_SESSION_EXITCODE_DELIMITER
        )
    
    def run_bash_script_at_target_as_root(
            self,
            script: str,
            password: str,
            args: list[str] | None,
            from_file: bool,
            hide: bool = False,
            timeout: float = 60.0,
            responders: list[Responder] | None = None,
            break_on: str | None = None,        
        ) -> tuple[str, int]:
            """
            Executes a bash script as root via `sudo su root -c` over an interactive SSH session.

            Args:
                script (str): Either the literal bash script string or path to a local file.
                password (str): Password to respond to sudo prompt.
                args (list[str] | None): Optional list of arguments to pass to the script.
                from_file (bool): If True, interprets `script` as a file path. If False, treats it as raw content.
                hide (bool): Whether to suppress output printing during execution.
                timeout (float): Maximum time to wait for the command to complete (in seconds).
                responders (list[Responder] | None): List of additional responders (sudo responder will be prepended).
                break_on (str | None): Optional regex pattern that forces early exit if matched in the output.
                exitcode_delimiter (str): String used to mark the exit code in output.

            Returns:
                tuple[str, int]: A tuple with cleaned output and the command exit code.
            """
            self.verify_target_session_token(hide= hide)

            return self.gateway.run_bash_script_as_root(
                script= script,
                args= args,
                password= password,
                from_file= from_file,
                hide= hide,
                timeout= timeout,
                responders= responders,
                break_on= break_on,
                exitcode_delimiter= self.TARGET_SESSION_EXITCODE_DELIMITER,
            )

    def exit_target_session(self, hide: bool = False) -> None:
        """
        Gracefully exits the target host session and verifies return to the gateway.

        If the target session is already inactive, it skips the exit command.

        Args:
            hide (bool): Whether to suppress output during the exit process.
        """
        try:
            cmd = "exit"
            self.run_at_target(cmd, hide=hide)
        except TargetSessionInactiveError:
            pass

        # Regardless of target, we should still confirm we're on the gateway
        self.verify_gateway_session_token(hide=hide)

    def close(self) -> None:
        """
        Gracefully exits the target session (if active) and closes the gateway SSH connection.

        This method should be called when you're done with the recursive session
        to ensure all SSH resources are properly released.
        """
        self.exit_target_session(hide= True)
        self.gateway.close()

