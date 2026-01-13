from enum import IntEnum
from pydantic.dataclasses import dataclass
from pydantic import SecretStr, Field


DEFAULT_SHELL_PROMPT_PATTERN: str = r"[^@\s]+@[^;\s]+[:\s].*[$#%>]"
  

class InternalExitCode(IntEnum):
    """
    Internal status codes used to represent outcomes of command execution
    in interactive SSH sessions.

    Attributes:
        UNSET (int): Indicates that no command has been run yet.
        BREAK_TRIGGERED (int): Indicates that a user-defined break condition was met during command execution.
        EXIT_CODE_NOT_FOUND (int): Indicates the absence of an expected exit code marker/delimeter in the command output.
    """
    UNSET = -9999                 # Initial state before command run
    EXIT_CODE_NOT_FOUND = -1      # Exit code delimiter not found in output
    BREAK_TRIGGERED = -2          # Special break condition triggered


@dataclass
class SSHConnectionData:
    """
    Container for SSH connection parameters.
    """
    host: str
    user: str
    password: SecretStr
    port: int = Field(default=22, ge=1, le=65535)
    # If both external and internal IPs are provided, `internal_host` is the internal IP.
    # Use `internal_host` for in-network (LAN/VPN) operations; otherwise fall back to `host`.
    internal_host: str | None = None
