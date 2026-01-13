from pydantic import SecretStr

from .base import SSHConnectionData
from .session import RecursiveSSHSession
from .commands import TargetCommand, TargetBashScript, TargetExecutionResult
from .exceptions import (
    CommandTimeoutError,
    ExitCodeNotFoundError,
    GatewaySessionInactiveError,
    TargetSessionInactiveError,
    TargetSSHConnectionError,
    GatewaySSHConnectionError,
    InvalidTargetCommandError,
)


class SerialRecursiveSSHGroup:
    """
    Manages a set of serial recursive SSH connections to multiple target hosts 
    via a single gateway (jump) server.

    This class reuses one persistent gateway connection to iterate over a list of 
    target machines, connecting to each via nested SSH (recursive shell), executing 
    commands or scripts, and collecting their results. The connections are interactive 
    and can optionally escalate to root on the target using `sudo`.

    Features:
        - Handles two-hop SSH logic (gateway → target) with session validation.
        - Supports executing both simple shell commands and bash scripts on targets.
        - Gracefully recovers from target-specific errors without aborting the whole batch.
        - Shared gateway session reduces overhead when dealing with many targets.
    """

    def __init__(
            self,
            gateway_data: SSHConnectionData,
            targets: list[SSHConnectionData],
            shell_gateway_prompt_pattern: str,
            shell_target_prompt_pattern: str,
            connection_timeout: float = 60,
            shell_prompt_timeout: float = 90,
        ):
        """
        Initialize the group with gateway and target SSH configuration.

        Args:
            gateway_data: Connection details for the gateway server.
            targets: List of connection details for each target machine.
            shell_gateway_prompt_pattern: Regex to detect the shell prompt on the gateway.
            shell_target_prompt_pattern: Regex to detect the shell prompt on the target.
            connection_timeout: Timeout for SSH connections (in seconds).
            shell_prompt_timeout: Timeout to wait for shell prompts (in seconds).

        Raises:
            ValueError: If the target list is empty.
        """
        self.gateway_data = gateway_data
        self.shell_gateway_prompt_pattern = shell_gateway_prompt_pattern
        self.shell_target_prompt_pattern = shell_target_prompt_pattern
        self.connection_timeout = connection_timeout
        self.shell_prompt_timeout = shell_prompt_timeout

        if not targets:
            raise ValueError("Target list must not be empty.")

        self.targets = targets

        self._dummy_target = SSHConnectionData(
            host="",
            user="",
            password= SecretStr("")
        )
        self.session = RecursiveSSHSession(
            gateway_data= gateway_data,
            target_data= self._dummy_target
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self, target: SSHConnectionData, hide: bool = False):
        """
        Establish a recursive SSH connection to a specific target host via the gateway.

        Args:
            target (SSHConnectionData): Target host to connect to.
            verbose (bool): If True, print session output during connection.
        """
        self.session.target_data = target
        self.session.connect(
            verbose= not hide,
            shell_gateway_prompt_pattern= self.shell_gateway_prompt_pattern,
            shell_target_prompt_pattern= self.shell_target_prompt_pattern,
            connection_timeout= self.connection_timeout,
            shell_prompt_timeout= self.shell_prompt_timeout
        )

    def _run_on_target(self, target: SSHConnectionData, command: TargetCommand) -> tuple[str, int]:
        """
        Execute a single shell command on the target, as root or regular user.

        Args:
            target: SSH credentials for the target host.
            command: TargetCommand object with execution settings.

        Returns:
            Output and exit code of the command.
        """
        if command.run_as_root:
            return self.session.run_as_root_at_target(
                command= command.command,
                password= target.password.get_secret_value(),
                hide= command.hide_output,
                responders= command.responders,
                break_on= command.break_on,
                timeout= command.timeout,
            )
        else:
            return self.session.run_at_target(
                command=  command.command,
                hide= command.hide_output,
                responders= command.responders,
                break_on= command.break_on,
                timeout= command.timeout,
            )
        
    def _run_bash_script_on_target(self, target: SSHConnectionData, script: TargetBashScript) -> tuple[str, int]:
        """
        Execute a bash script on the target (must run as root for now).

        Args:
            target: SSH credentials for the target host.
            script: TragetBashScript object with script content and options.

        Returns:
            Output and exit code of the script execution.

        Raises:
            NotImplementedError: If script is not marked to run as root.
        """
        if script.run_as_root:
            return self.session.run_bash_script_at_target_as_root(
                script= script.script,
                args= script.args,
                password= target.password.get_secret_value(),
                from_file= script.from_file,
                hide= script.hide_output,
                responders= script.responders,
                break_on= script.break_on,
                timeout= script.timeout,
            )
        else:
            raise NotImplementedError("run script as root for now")
        
    def run_target(self, target: SSHConnectionData, commands: list[TargetCommand | TargetBashScript], hide: bool = False) -> TargetExecutionResult:
        """
        Establish a connection and execute multiple commands or scripts on a single target.

        Args:
            target: SSH credentials for the target host.
            commands: List of commands or scripts to execute.
            hide: Whether to suppress output during execution.

        Returns:
            A TargetExecutionResult with outputs and execution status.

        Raises:
            InvalidTargetCommandError: If commands list contains items other than TargetCommand or TargetBashScript
            GatewaySSHConnectionError: If the gateway connection fails.
            GatewaySessionInactiveError: If the gateway session is inactive.
        """
        for cmd in commands:
            if not isinstance(cmd, (TargetCommand, TargetBashScript)):
                raise InvalidTargetCommandError(
                    f"run_target expected TargetCommand or TargetBashScript. "
                    f"Got {repr(cmd)} ({type(cmd).__name__})"
                )

        result: TargetExecutionResult 
        target_outputs: list[tuple[str, int]] = []
        try:                
            self.connect(target= target, hide= hide)

            target_outputs = [
                self._run_on_target(target, cmd) 
                if isinstance(cmd, TargetCommand)
                else self._run_bash_script_on_target(target, cmd)
                for cmd in commands
            ]

            result = TargetExecutionResult(
                success= True,
                outputs= target_outputs,
                error= None
            )

            self.session.exit_target_session(hide= hide)
        
        except (GatewaySSHConnectionError, GatewaySessionInactiveError) as e:
            raise e
        except TargetSSHConnectionError as e:
            result = TargetExecutionResult(
                success= False,
                outputs= [],    
                error= e
            )
        except TargetSessionInactiveError as e:
            result = TargetExecutionResult(
                success= False,
                outputs= target_outputs,
                error= e
            )
        except (CommandTimeoutError, ExitCodeNotFoundError) as e:
            result = TargetExecutionResult(
                success= False,
                outputs= target_outputs,
                error= e
            )

        return result
    
    def run_all_targets(self, commands: list[TargetCommand | TargetBashScript], hide: bool = False) -> dict[str, TargetExecutionResult]:
        """
        Runs the same list of commands/scripts on all targets in sequence.

        Args:
            commands: List of commands or scripts to execute.
            hide: Whether to suppress output during execution.

        Returns:
            A mapping of target host to its execution result.
        """
        results = {}
        for target in self.targets:
            out = self.run_target(target= target, commands= commands, hide= hide)

            results[target.host] = out

            if isinstance(out.error, (TargetSessionInactiveError, TargetSSHConnectionError)):
                # this foces the session to start from zero for the next target
                self.session.close()

        return results
    
    def close(self):
        """
        Closes the gateway SSH connection.

        This should be called when done to clean up SSH resources.
        """
        self.session.gateway.close()

