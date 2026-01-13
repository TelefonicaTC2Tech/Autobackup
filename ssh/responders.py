import re
from dataclasses import dataclass, field


@dataclass
class Responder:
    """
    Represents a pattern-based responder for interactive SSH sessions.

    This class is used to automatically detect specific output patterns
    (e.g., password prompts) and send predefined responses during command execution.

    Args:
        pattern: A regular expression pattern to match in the output stream.
        response: The response to send when the pattern is matched.
        _compiled_regex (re.Pattern): Compiled version of the pattern, created internally.

    Raises:
        ValueError: If the given pattern is not a valid regular expression
    """
    pattern: str # raw string regex
    response: str
    _compiled_regex: re.Pattern = field(init=False, repr=False)

    def __post_init__(self):
        try:
            self._compiled_regex = re.compile(self.pattern)
        except re.error as e:
            raise ValueError(f"Invalid regex patter {self.pattern}") from e


# Built-in responders
SSH_CONNECTION_YES_NO_FINGERPRINT_RESPONDER = Responder(
    pattern=r"(?i)are you sure you want to continue connecting .+yes/no.*",
    response="yes\n",
)

def get_sudo_password_responder(password: str) -> Responder:
    return Responder(
        pattern= r'(?i)password:',
        response= password + '\n',
    )


def get_ssh_login_password_responder(password: str) -> Responder:
    """
    Returns a Responder that handles SSH login password prompts.

    Example matched prompts:
        - Password:
        - Password for admin@Nozomi-Copey:
        - admin@10.210.175.116's password:

    Args:
        password (str): The password to send.

    Returns:
        Responder: A configured responder for SSH password prompts.
    """
    return Responder(
        pattern= r"(?i)password\s.*:",  # Matches "Password:" and "Password for user@host:"
        response= password + "\n",
    )