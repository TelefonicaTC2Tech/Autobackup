
class ChecksumVerificationError(Exception):
    """
    Raised when a file's SHA-256 checksum does not match the expected value.
    This may indicate tampering, corruption, or file replacement.
    """
    pass
