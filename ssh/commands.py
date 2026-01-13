from dataclasses import dataclass, field
from .responders import Responder


@dataclass
class TargetCommand:
    """
    Represents a regular shell command to be executed on a target machine,
    along with its configuration parameters.

    Attributes:
        command (str): The shell command to run.
        hide_output (bool): If True, suppresses output printing. Defaults to False.
        responders (list[Responder]): Optional list of responders to handle interactive prompts.
        break_on (str | None): Optional regex pattern to break execution early.
        timeout (float): Maximum time to wait for the command to complete. Defaults to 30.0 seconds.
        run_as_root (bool): Whether to execute the command with root privileges. Defaults to False.
    """
    command: str
    hide_output: bool = False
    responders: list[Responder] = field(default_factory=list)
    break_on: str | None = None
    timeout: float = 30.0
    run_as_root: bool = False


@dataclass
class TargetBashScript:
    """
    Represents a multi-line bash script to be executed on a target machine.

    Attributes:
        script (str): Either the script content or a filepath, depending on `from_file`.
        args (list[str] | None): Optional list of arguments to pass to the script.
        from_file (bool): If True, `script` is interpreted as a local file path.
        hide_output (bool): If True, suppresses output printing. Defaults to False.
        responders (list[Responder]): Optional responders for interactive prompts.
        break_on (str | None): Optional regex pattern to break execution early.
        timeout (float): Max time allowed for script execution. Defaults to 60.0 seconds.
        run_as_root (bool): Whether to run the script with root privileges. Defaults to False.
    """
    script: str
    args: list[str] | None
    from_file: bool
    hide_output: bool = False
    responders: list[Responder] = field(default_factory=list)
    break_on: str | None = None
    timeout: float = 60.0
    run_as_root: bool = False


@dataclass
class TargetExecutionResult:
    """
    Holds the result of executing a list of commands on a target machine.

    Attributes:
        success (bool): Indicates if all commands/scripts ran without critical errors.
        outputs (list[tuple[str, int]]): List of (output, exit_code) pairs from executed commands.
        error (Exception | None): The exception raised during execution, if any.
    """
    success: bool
    outputs: list[tuple[str, int]]
    error: Exception | None = None
