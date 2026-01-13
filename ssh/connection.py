import time
import re
import paramiko

from typing import Optional

from .base import InternalExitCode, DEFAULT_SHELL_PROMPT_PATTERN
from .responders import Responder, get_sudo_password_responder
from .formatter import CommandFormatter
from .exceptions import (
    PromptTimeoutError,
    CommandTimeoutError,
    ExitCodeNotFoundError,
)


class SSHConnection:
    """
    Manages an interactive SSH session over Paramiko.

    This class maintains a persistent shell session with a remote host and allows sending 
    commands, handling prompts interactively, running scripts, and managing privilege escalation.
    """
    RECV_BUFFER_SIZE = 4096 

    def __init__(self, hostname: str, username: str, password: str, port: int = 22) -> None:
        self.hostname: str = hostname
        self.username: str = username
        self.password: str = password
        self.port: int = port
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None

    def connect(
            self,
            verbose: bool = False,
            connection_timeout: float = 60,
            shell_prompt_timeout: float = 60,
            shell_prompt_pattern: str = DEFAULT_SHELL_PROMPT_PATTERN,    
        ):
        """
        Establish an SSH connection and open an interactive shell session.

        This method connects to the remote host using Paramiko and opens a persistent
        interactive shell channel. After the shell is opened, it waits for a shell prompt
        to confirm that the session is ready.

        Args:
            verbose (bool): If True, prints the output while waiting for the prompt.
            shell_promt_timeout (float): Maximum time (in seconds) to wait for the shell prompt.
            connection_timeout (float): Timeout (in seconds) for establishing the SSH connection.
            shell_prompt_pattern (str): Regular expression pattern used to detect the shell prompt.
                Can be customized to match different shells or environments.

        Raises:
            PromptTimeoutError: If the shell prompt is not detected within the timeout window.
        """
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.hostname,
            port=self.port,
            username=self.username,
            password=self.password,
            allow_agent=False,
            timeout= connection_timeout,
            # look_for_keys=False
        )
    
        self.channel = self.client.get_transport().open_session() #type: ignore
        self.channel.get_pty()
        self.channel.invoke_shell()

        time.sleep(1)
        try:
            self.expect(shell_prompt_pattern, timeout= shell_prompt_timeout, hide= not verbose)
        except TimeoutError as e:
            raise PromptTimeoutError(
                f"Timeout while waiting for shell prompt pattern '{shell_prompt_pattern}' after {shell_prompt_timeout}s."
            ) from e

    def ensure_channel_ready(self) -> None:
        """
        Ensures that the SSH channel is active and ready for communication.

        This method should be called before attempting to send or receive data over the channel.
        It raises an exception if the channel is not initialized or has been closed.

        Raises:
            RuntimeError: If the SSH channel is not set or is closed.
        """
        if self.channel is None or self.channel.closed:
            raise RuntimeError("SSH channel is not active or already closed.")

    def flush(self, nbytes: int = 9999) -> str | None:
        """
        Flush and return any ready output from the channel.

        Args:
            nbytes: Max number of bytes to read.

        Returns:
            The decoded output, if available.
        """
        self.ensure_channel_ready()

        if self.channel.recv_ready(): # type: ignore
            return self.channel.recv(nbytes).decode("utf-8") # type: ignore
        return None

    def send(self, cmd: str, wait: float = 0.1) -> int:
        """
        Send a command string to the remote interactive shell.

        Appends a newline to the command, sends it through the active SSH channel,
        and optionally waits for a short duration to allow the remote system to process it.

        Args:
            cmd: The command to send.
            wait: Seconds to wait after sending.

        Returns:
            Number of bytes sent.
        
        Raises:
            RuntimeError: If the SSH channel is not open.
        """
        self.ensure_channel_ready()
        
        out = self.channel.send(f"{cmd}\n".encode("utf-8")) # type: ignore
        time.sleep(wait)

        return out

    def expect(self, pattern: str, timeout: float = 10.0, hide: bool = False) -> str:
        """
        Waits for a given regex pattern to appear in the shell output.

        Continuously reads from the channel until the specified pattern is matched
        or the timeout is reached. Optionally prints the received output in real-time.

        Args:
            pattern: Regex pattern to search for.
            timeout: Max time to wait for pattern.
            hide: If True, suppresses live printing of output.

        Returns:
            The output including the match.

        Raises:
            RuntimeError: If the SSH channel is not open.
            TimeoutError: If the pattern is not found within the timeout window.
        """
        self.ensure_channel_ready()
        
        regex = re.compile(pattern)
        output: str = ""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.channel.recv_ready(): # type: ignore
                chunk = self.channel.recv(self.RECV_BUFFER_SIZE).decode("utf-8") # type: ignore
                output += chunk

                if not hide:
                    print(chunk, end="")
                
                if regex.search(output):
                    return output
                
            time.sleep(0.1)

        raise TimeoutError(f"Timeout waiting for prompt: {pattern} \n output: {output}")

    def close(self) -> None:
        """
        Close the SSH channel and client.
        """
        if self.channel:
            self.channel.close()
        if self.client:
            self.client.close()

    def _run_raw(  
            self,
            formatted_command: str,
            exitcode_delimiter: str,
            hide: bool,
            timeout: float,
            responders: list[Responder] | None,
            break_on: str | None,
        ) -> tuple[str, int]:
        """
        Execute a preformatted shell command over an interactive SSH session.

        This method sends a command (which must already include an exit code delimiter,
        typically using `CommandFormatter` class methods and processes its output
        until the command finishes, a timeout occurs, or an optional break condition is met.

        It supports pattern-based responders (e.g., for password prompts), timeout handling,
        and extraction of the command's exit code from the output.

        Args:
            formatted_command (str): The full shell command to execute, already formatted with an exit code marker.
            exitcode_delimiter (str): Prefix string used to detect and extract the command's exit code from the output.
            hide (bool): If True, suppresses output printing during execution.
            timeout (float): Maximum time to wait for the command to complete (in seconds).
            responders (list[Responder] | None): List of Responder instances to automatically respond to interactive prompts.
            break_on (str | None): Optional regex pattern that, if matched in the output, forces an early exit.

        Returns:
            tuple[str, int]: A tuple containing:
                - The cleaned output (excluding the exit code line),
                - The command's exit code as an integer.

        Raises:
            RuntimeError: If the SSH channel is not active.
            CommandTimeoutError: If the command does not finish within the specified timeout.
        """
        self.ensure_channel_ready()
        
        responders = responders or []
        break_on_pattern = re.compile(break_on) if break_on else None
        exitcode_pattern = re.compile(rf"{exitcode_delimiter}:(\d+)")
        full_output = ""
        exit_code: int = InternalExitCode.UNSET
        
        bytes_sent = self.send(formatted_command, wait=0)
        out = self.flush(bytes_sent)
        if out and not hide:        
            print(out, end="")

        output_chunks: list[str] = [""]
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
               raise CommandTimeoutError(
                   f"Command <{formatted_command}> timed out after {timeout} seconds."
                   f"expected exitcode: {exitcode_delimiter}"
                   f"break_on: {break_on}"
                )

            if self.channel.recv_ready(): # type: ignore
                chunk = self.channel.recv(self.RECV_BUFFER_SIZE).decode("utf-8") # type: ignore
                output_chunks[-1] += chunk
                if not hide:
                    print(chunk, end="")

            for responder in responders:
                if responder._compiled_regex.search(output_chunks[-1]):
                    self.send(responder.response, wait=0.5)
                    if not hide:
                        print("RESPONSE:", repr(responder.response))
                    out = self.flush()
                    if out:
                        output_chunks.append(out)
                        if not hide:                            
                            print(out, end="")

            if exitcode_pattern.search(output_chunks[-1]):
                break

            if break_on_pattern and break_on_pattern.search(output_chunks[-1]):
                if not hide:
                    print("BREAK FOUND")
                exit_code = InternalExitCode.BREAK_TRIGGERED
                break

            time.sleep(0.1)

        # Final flush (just to make sure nothing is there)
        out = self.flush()
        if out:
            output_chunks.append(out)
            if not hide:                
                print(out, end="")
        
        full_output: str = "".join(output_chunks)

        # Extract the exit code
        try:
            if exit_code == InternalExitCode.UNSET:
                exit_code, full_output = CommandFormatter.extract_exit_code(full_output, exitcode_delimiter)
        except ExitCodeNotFoundError:
            exit_code = InternalExitCode.EXIT_CODE_NOT_FOUND

        return full_output, exit_code
 
    def run(  
            self,
            command: str,
            hide: bool = False,
            timeout: float = 30.0,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            exitcode_delimiter: str = "__EXITCODE",
        ) -> tuple[str, int]:
        """
        Executes a shell command over the SSH session, with automatic command formatting.

        This method uses `CommandFormatter.regular_command` internally to wrap the command 
        with an exit code marker. Supports optional responders and timeout handling.

        Args:
            command (str): The raw shell command to execute (not pre-formatted).
            hide (bool): If True, suppress output during execution.
            timeout (float): Max time to wait for the command to finish.
            responders (list[Responder] | None): Optional responders for interactive prompts.
            break_on (str | None): Regex pattern that breaks execution early.
            exitcode_delimiter (str): Prefix string used to detect and extract the command's exit code from the output.

        Returns:
            tuple[str, int]: Cleaned output and the extracted exit code.
        
        Raises:
            RuntimeError: If the SSH channel is not active.
            CommandTimeoutError: If the command does not finish within the specified timeout.
        """
        cmd = CommandFormatter.regular_command(command= command, exitcode_delimiter= exitcode_delimiter)

        return self._run_raw(
            formatted_command= cmd,
            exitcode_delimiter= exitcode_delimiter,
            hide= hide,
            timeout= timeout,
            responders= responders,
            break_on= break_on,
        )
        
       
    def run_bash_script(
            self,
            script: str,
            args: list[str] | None,
            from_file: bool,
            hide: bool = False,
            timeout: float = 60.0,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            exitcode_delimiter: str = "__EXITCODE",
        ) -> tuple[str, int]:
        """
        Executes a bash script via an interactive SSH session.

        Args:
            script (str): Either the bash script content or a path to a local script file.
            args (list[str] | None): List of arguments to pass to the script.
            from_file (bool): If True, interprets `script` as a file path. If False, treats it as raw content.
            hide (bool): If True, suppresses output printing during execution.
            timeout (float): Maximum time to wait for the command to complete (in seconds).
            responders (list[Responder] | None): Responders for interactive prompts.
            break_on (str | None): Optional regex pattern that, if matched, exits early.
            exitcode_delimiter (str): String used to extract exit code from output.

        Returns:
            tuple[str, int]: The cleaned output and the extracted exit code.

        Raises:
            RuntimeError: If the SSH channel is not active.
            CommandTimeoutError: If the command does not finish within the specified timeout.
        """
        if from_file:
            cmd = CommandFormatter.bash_script_from_local_file(
                filepath=script,
                args=args,
                exitcode_delimiter=exitcode_delimiter
            )
        else:
            cmd = CommandFormatter.bash_script_from_string(
                script_content=script,
                args=args,
                exitcode_delimiter=exitcode_delimiter
            )

        return self._run_raw(
            formatted_command= cmd,
            exitcode_delimiter= exitcode_delimiter,
            hide= hide,
            timeout= timeout,
            responders= responders,
            break_on= break_on,
        )

    def run_as_root(
            self,
            command: str,
            password: str,
            hide: bool = False,
            timeout: float = 30.0,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            exitcode_delimiter: str = "__EXITCODE",
        ) -> tuple[str, int]:
        """
        Executes a shell command as root using `sudo`, handling password prompt automatically.

        This method formats the command with `sudo su -c ...`, appends an exit code marker,
        and inserts a responder for the sudo password prompt. Supports additional responders.

        Args:
            command (str): The raw shell command to execute with root privileges.
            password (str): Root password used in the sudo prompt.
            hide (bool): If True, suppress output during execution.
            timeout (float): Max time to wait for the command to finish.
            responders (list[Responder] | None): Optional extra responders (password responder is prepended).
            break_on (str | None): Regex pattern that breaks execution early.
            exitcode_delimiter (str): Prefix string used to detect and extract the command's exit code from the output.

        Returns:
            tuple[str, int]: Cleaned output and the extracted exit code.
        
        Raises:
            RuntimeError: If the SSH channel is not active.
            CommandTimeoutError: If the command does not finish within the specified timeout.
        """
        cmd = CommandFormatter.regular_command(
            command= command, run_as_root= True, exitcode_delimiter= exitcode_delimiter
        ) 
        password_responder = get_sudo_password_responder(password= password)

        if responders is None:
            responders = [password_responder]
        else:
            responders = [password_responder] + responders

        return self._run_raw(
            formatted_command= cmd,
            hide= hide,
            timeout= timeout,
            responders= responders,
            break_on= break_on, 
            exitcode_delimiter= exitcode_delimiter,
        )
    
    def run_bash_script_as_root(
            self,
            script: str,
            password: str,
            args: list[str] | None,
            from_file: bool,
            hide: bool = False,
            timeout: float = 60.0,
            responders: list[Responder] | None = None,
            break_on: str | None = None,
            exitcode_delimiter: str = "__EXITCODE",            
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

            Raises:
                RuntimeError: If the SSH channel is not active.
                CommandTimeoutError: If the command does not finish within the specified timeout.
            """
            if from_file:
                cmd = CommandFormatter.bash_script_from_local_file(
                    filepath=script,
                    args=args,
                    exitcode_delimiter=exitcode_delimiter,
                    run_as_root= True
                )
            else:
                cmd = CommandFormatter.bash_script_from_string(
                    script_content=script,
                    args=args,
                    exitcode_delimiter=exitcode_delimiter,
                    run_as_root= True
                )

            password_responder = get_sudo_password_responder(password= password)

            all_responders = [password_responder]
            if responders is not None:
                all_responders = [password_responder] + responders

            return self._run_raw(
                formatted_command=cmd,
                exitcode_delimiter=exitcode_delimiter,
                hide=hide,
                timeout=timeout,
                responders=all_responders,
                break_on=break_on
            )
 