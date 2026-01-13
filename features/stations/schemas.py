import unicodedata
from typing import (
    Annotated,
    Iterable,
    Literal,
    Optional,
)
from pydantic import (
    BaseModel,
    RootModel,
    ValidationInfo, 
    IPvAnyAddress,
    SecretStr,
    Field,
    field_validator,
    model_validator,
)


class StationRow(BaseModel):
    """
    Pydantic model representing a single row of station data from an Excel sheet.

    Attributes:
        type (Literal): The type of machine. Allowed values are specific predefined strings.
        machine_name (str): The name or identifier of the machine.
        ip_external (IPvAnyAddress): The external IP address of the machine.
        ip_internal (IPvAnyAddress): The internal IP address of the machine.
        state (Literal): The state of the machine. Allowed values are:
            'instalada', 'monitoreando', 'aprendizaje', 'pendiente'.
    
    Notes:
        - machine_name and state fields are normalized: stripped, ASCII-converted, and lowercased.
        - IPs are required unless state is 'pendiente'.
    """
    type: Literal["CMC", "GUARDIAN"]  # replace with your allowed types
    machine_name: str
    ip_external: Optional[IPvAnyAddress]
    ip_internal: Optional[IPvAnyAddress]
    state: Literal["instalada", "monitoreando", "aprendizaje", "pendiente"]

    @field_validator('machine_name', 'state', mode="before")
    @classmethod
    def lowercase(cls, value: str) -> str:
        return value.lower()
    
    @field_validator('type', mode="before")
    @classmethod
    def capitalize(cls, value: str) -> str:
        return value.upper()
    
    @field_validator('machine_name', 'state', mode="before")
    @classmethod
    def normalize_to_ascii(cls, value: str) -> str:
        """
        Normalize a string by:
        - Stripping leading/trailing whitespace
        - Removing accents and converting to closest ASCII equivalent
        """
        value = value.strip()
        return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    
    @model_validator(mode="after")
    def validate_ips_if_needed(self):
        """
        Ensures that both IP fields are provided unless the state is 'pendiente'.
        """
        if self.state != 'pendiente':
            if self.ip_internal is None or self.ip_external is None:
                raise ValueError("Internal and External IPs are required if state is not 'pendiente'")
        
        return self


class StationsSecretsTemplate(RootModel):
    """
    Root: { "<STATION_NAME>": { <IPvAnyAddress>: <SecretStr>, ... } }

    Extra runtime guarantees (checked in the validator):

    - The outer dict contains *exactly* one station.
    - If context["expected_station_name"] is provided, the name must match.
    - If context["expected_ips"] is provided, the inner dict must contain
      exactly those IPs (order-insensitive).
    """
    root: dict[
        str, # station name
        dict[
            IPvAnyAddress,  # device IP
            Annotated[SecretStr, Field(min_length=1)]  # password
        ]
    ]

    model_config = {"hide_input_in_errors": True}

    @model_validator(mode="after")
    def _validate_structure(self, info: ValidationInfo):
        station_names = list(self.root.keys())

        if len(station_names) != 1:
            raise ValueError(
                "The JSON must contain secrets for exactly one station (found "
                f"{len(self.root)})."
            )
        
        station_name = station_names[0]

        # Must have at least one device/IP
        if not self.root[station_name]:
            raise ValueError(
                "Station must have at least one device/IP."
            )

        expected_station = info.context.get("expected_station_name") if info.context else None

        # Optional station-name check
        if expected_station and station_name != expected_station:
            raise ValueError(
                f"Expected secrets for station '{expected_station}', "
                f"but found '{station_name}'."
            )
        
        # Optional IP list check
        expected_ips: Iterable[str] | None = (
            info.context.get("expected_ips") if info.context else None
        )

        if expected_ips is not None:
            actual_ips = {str(k) for k in self.root[station_name].keys()}
            expected_set = set(expected_ips)

            if actual_ips != expected_set:
                raise ValueError(
                    "IPs mismatch.\n"
                    f"  Expected: {sorted(expected_set)}\n"
                    f"  Found:    {sorted(actual_ips)}"
                )


        return self        