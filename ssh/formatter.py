import re
import shlex
from pathlib import Path
from .exceptions import ExitCodeNotFoundError


class CommandFormatter:
    """
    Provides utility methods to format shell commands consistently,
    including support for root execution, environment variable setting,
    bash script execution, and structured exit code parsing.
    """

    @staticmethod
    def regular_command(
        command: str,
        exitcode_delimiter: str,
        run_as_root: bool = False,
    ) -> str:
        """
        Formats a regular shell command to include an exit code marker.

        Args:
            command (str): The base shell command to execute.
            exitcode_delimiter (str): A unique string used to mark the exit code.
            run_as_root (bool): If True, wraps the command with `sudo su root -c`.

        Returns:
            str: The formatted command string.
        """
        base_cmd = command.strip()

        # Echo the internal exit code (last command's exit status)
        full_cmd = f"{base_cmd}; echo {exitcode_delimiter}:$?"

        if run_as_root:
            full_cmd = f"sudo su root -c {full_cmd}"
  
        return full_cmd

    @staticmethod
    def bash_script_from_string(
        script_content: str,
        exitcode_delimiter: str,
        args: list[str] | None,
        run_as_root: bool = False,
    ) -> str:
        """
        Formats a multi-line bash script string for remote execution.

        Args:
            script_content (str): The content of the script to run.
            exitcode_delimiter (str): String used to identify the script's exit code.
            args (list[str] | None): Optional list of arguments to pass to the script.
            run_as_root (bool): Whether to run the script as root.

        Returns:
            str: A formatted bash heredoc string for execution.
        """
        args = args or []
        quoted = [shlex.quote(arg) for arg in args]
        joined_args = " ".join(quoted)

        cmd = f'\'bash -s {joined_args}\' << "EOF" ; echo {exitcode_delimiter}:$? \n{script_content}\n"EOF"\n'
        if run_as_root:
            cmd = f'sudo su root -c {cmd}'

        return cmd

    @staticmethod
    def bash_script_from_local_file(
        filepath: str,
        exitcode_delimiter: str,
        args: list[str] | None,
        run_as_root: bool = False,
    ) -> str:
        """
        Loads a bash script from a file and formats it for execution.

        Args:
            filepath (str): Path to the local script file.
            exitcode_delimiter (str): Delimiter to mark the exit code in the output.
            args (list[str] | None): Optional arguments to pass to the script.
            run_as_root (bool): Whether to execute as root.

        Returns:
            str: Formatted heredoc bash command.

        Raises:
            FileNotFoundError: If the script file does not exist.
        """     
        script_path = Path(filepath)
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        script_content = script_path.read_text()

        return CommandFormatter.bash_script_from_string(script_content, exitcode_delimiter, args, run_as_root,)       

    @staticmethod
    def extract_exit_code(output: str, exitcode_delimiter: str) -> tuple[int, str]:
        """
        Extracts the exit code from command output using a defined delimiter.

        Args:
            output (str): Raw command output that includes the exit code marker.
            exitcode_delimiter (str): String prefix used to find the exit code.

        Returns:
            tuple[int, str]: The exit code and the cleaned output (without the marker).

        Raises:
            ExitCodeNotFoundError: If the delimiter is not found in the output.
        """
        match = re.search(rf"{exitcode_delimiter}:(\d+)", output)
        if not match:
            raise ExitCodeNotFoundError()
        
        # get the exit code number
        code = int(match.group(1))
        #clean ooutput by removing the exit code and what comes after
        clean_output = output[:match.start()]

        return code, clean_output
    
    @staticmethod
    def set_shell_env_variable_raw_command(key: str, value: str) -> str:
        """
        Returns a shell command that sets an environment variable
        using csh-style `setenv`.

        Args:
            key (str): Environment variable name.
            value (str): Value to assign.

        Returns:
            str: Command to set the environment variable.

        Example:
            set_shell_env_variable("MY_VAR", "value") -> 'setenv MY_VAR value'
        """
        return f"setenv {key} {value}"
 