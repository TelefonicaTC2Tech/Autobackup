from pydantic import ValidationError


class InvalidExcelFormatError(ValueError):
    """Raised when the Excel file does not match the expected structure."""
    pass


class InvalidExcelRowError(ValueError):
    """
    Raised when a single Excel row fails StationRow validation.

    Attributes
    ----------
    row_index : int
        1-based index of the offending row.
    sheet_name : str
        Name of the Excel sheet; optional.
    validation_error :
        The `pydantic.ValidationError` raised by the `StationRow` model.r.
    """

    def __init__(
        self,
        *,
        row_index: int,
        validation_error: ValidationError,
        sheet_name: str | None = None,
    ) -> None:
        self.row_index = row_index
        self.sheet_name = sheet_name
        self.validation_error = validation_error

        super().__init__()

    def __str__(self) -> str:
        msg = (
            f"Row {self.row_index} failed validation"
            if self.sheet_name is None
            else f"Row {self.row_index} in sheet '{self.sheet_name}' failed validation"
        )

        return f"{msg}\n{self.validation_error}"


class CorruptedDataFileError(Exception):
    """
    Raised when a required station data file or key is missing,
    malformed, or inconsistent with expected structure.
    """
    pass


class MachinePasswordMissingError(Exception):
    """Raised when no password is configured for the requested machine."""
    pass


class SecretsTemplateValidationError(Exception):
    """Raised when a secrets template fails structural validation."""