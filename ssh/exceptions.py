class PromptTimeoutError(TimeoutError):
    pass

class CommandTimeoutError(TimeoutError):
    pass

class GatewaySSHConnectionError(Exception):
    pass

class TargetSSHConnectionError(Exception):
    pass

class ExitCodeNotFoundError(Exception):
    def __init__(self):
        super().__init__("Could not find exit code delimiter in output.")

class GatewaySessionInactiveError(Exception):
    """Raised when the gateway session is no longer valid (env var missing)."""
    pass

class TargetSessionInactiveError(Exception):
    """Raised when the target session is no longer valid (env var missing)."""
    pass

class InvalidTargetCommandError(ValueError):
    """Raised when someone passes an unsupported command object to run_target."""
    pass