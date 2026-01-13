import os
from datetime import datetime
from pydantic import (
    BaseModel,
    IPvAnyAddress,
    Field,
)

from settings import BACKUP_FAILURES_JSON_FILE
from utils import (
    load_json_file,
    write_json_file,
)


class BackupFailureRecord(BaseModel):
    machine: str = Field(
        min_length= 1,
        description="Guardian label/name"
    )
    ip: IPvAnyAddress = Field(
        description="External IP address of the machine"
    )
    error: str


class StationFailures(BaseModel):
    last_attempt: datetime
    failures: list[BackupFailureRecord]


class BackupFailuresFile(BaseModel):
    last_update: datetime
    stations: dict[str, StationFailures]


class FailuresStore:
    """
    Reads/writes a single JSON file that keeps track of the last
    backup failures for every station.
    """

    def __init__(self, path: str = BACKUP_FAILURES_JSON_FILE) -> None:
        self.path = path
        self.data = BackupFailuresFile(
            last_update= self._local_now(),
            stations= {}
        )

    def _local_now(self) -> datetime:
        """Current local time with timezone info."""
        return datetime.now().astimezone()

    def load(self) -> None:
        """
        Load and validate the JSON file.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ValidationError
            If its contents do not conform to BackupFailuresFile schema.
        """        
        raw_data = load_json_file(filepath= self.path)
        self.data = BackupFailuresFile.model_validate(raw_data)

    def save(self) -> None:
        """Write `self.data` to disk (pretty-printed JSON), updating the global timestamp."""
        self.data.last_update = self._local_now()
        write_json_file(filepath= self.path, data= self.data.model_dump(mode= "json"))

    def add_failure(self, station: str, record: BackupFailureRecord, update_last_attempt: bool = True) -> None:
        """
        Append a failure record under the given station, creating the
        station entry if necessary.
        """
        if station not in self.data.stations:
            self.data.stations[station] = StationFailures(
                last_attempt= self._local_now(),
                failures= [],
            )

        self.data.stations[station].failures.append(record)
        if update_last_attempt:
            self.data.stations[station].last_attempt = self._local_now()

    def clear_station(self, station: str) -> None:
        """Remove all stored failures for *station* """
        if station in self.data.stations:
            self.data.stations[station].failures.clear()
            self.data.stations[station].last_attempt = self._local_now()

    def get_failed_ips(self, station: str) -> list[str]:
        """Return IPs that failed in the last run for *station*."""
        if station not in self.data.stations:
            return []
        
        return [str(rec.ip) for rec in self.data.stations[station].failures]
   
    @classmethod
    def clear(cls) -> None:
        """Delete the failures JSON file if it exists."""
        if os.path.exists(BACKUP_FAILURES_JSON_FILE):
            os.remove(BACKUP_FAILURES_JSON_FILE)
