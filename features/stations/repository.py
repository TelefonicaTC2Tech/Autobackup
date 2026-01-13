import os
from typing import Literal

import utils
from settings import (
    STATIONS_GENERAL_INFO_JSON_FILE,
    STATIONS_JSONS_CHECKSUM_FILE,
    STATIONS_JSON_FILES_DIRECTORY,
)
from exceptions import (
    ChecksumVerificationError,
)

from features.stations.exceptions import (
    CorruptedDataFileError,
)

class StationDataRepository:
    """
    Handles loading of previously saved station data and secrets from JSON files.

    Responsibilities:
    - Load station data from general_info.json and per-station JSON files.
    - Load and decrypt station secrets using StationSecretsHandler.
    """
    def __init__(
        self,
    ) -> None:
        self._general_info = self._load_general_info()

        # Caches
        self._data_cache: dict[str, list[dict]] = {}

    def _load_general_info(self) -> dict:
        return utils.load_json_file(STATIONS_GENERAL_INFO_JSON_FILE)
    
    def get_stations_data_files(self) -> dict[str, str]:
        try:
            return self._general_info["stations_data"]
        except KeyError:
            raise CorruptedDataFileError(f"'stations_data' key is missing from {STATIONS_GENERAL_INFO_JSON_FILE}")
    
    def get_station_names(self) -> list[str]:        
        keys = self.get_stations_data_files().keys()
        if len(keys) == 0:
            raise CorruptedDataFileError(f"'stations_data' key in {STATIONS_GENERAL_INFO_JSON_FILE} does not contain any station entries")
        
        return list(keys)

    def get_station_data(self, station_name: str) -> list[dict]:
        """
        Returns cached data if available, otherwise loads from file and caches it.
        """
        if station_name not in self._data_cache:
            self._data_cache[station_name] = self.load_station_data(station_name)

        return self._data_cache[station_name]

    def load_station_data(self, station_name: str) -> list[dict]:
        """
        Load all available station data from JSON files listed in general_info.json.

        Returns:
            dict[str, list[dict]]: Mapping of station name → list of machine records.
        """
        stations_data_files = self.get_stations_data_files()
        
        file_name = stations_data_files.get(station_name)
        if not file_name:
            raise ValueError(f"The station {station_name} does NOT exists, invalid station name.")
        
        file_path = os.path.join(STATIONS_JSON_FILES_DIRECTORY, file_name)
        if not os.path.isfile(file_path):
                raise FileNotFoundError(f"Station data file missing: {file_path}")

        content = utils.load_json_file(filepath= file_path)[station_name]

        return content
    
    def load_multiple_stations_data(self, station_names: list[str]) -> dict[str, list[dict]]:
        result: dict[str, list[dict]] = {}
        for name in station_names:
            content = self.load_station_data(station_name= name)
            result[name] = content

        return result

    def verify_stations_data_checksum_file(self) -> bool:
        try:
            is_valid = utils.checksum_verfication_sha256(STATIONS_JSONS_CHECKSUM_FILE)
        except FileNotFoundError as e:
            raise e
        
        if not is_valid:
            raise ChecksumVerificationError("Stations JSON data files checksum verification failed")
        
        return is_valid
    
    def build_station_index(
        self,
        station_name: str,
        by: Literal["ip_external", "ip_internal", "machine_name"],
        *,
        skip_missing: bool = True,        # skip rows lacking the key
        crash_on_duplicates: bool = True, # guard against accidental duplicate keys
    ) -> dict[str, dict]:
        """
        Return an *in-memory* index (``dict[str, dict]``) of the machine
        records for *station_name*, keyed by the chosen field.

        Args:
            station_name: Name of the station to index.
            by: Field to use as the dictionary key
                ("ip_external", "ip_internal", or "machine_name").
            skip_missing: If True (default) silently drop rows that
                lack *by*; if False raise KeyError.
            crash_on_duplicates: If True (default) raise ValueError
                when duplicate keys are encountered; if False, the last
                row wins.

        Returns:
            dict[str, dict]
                Mapping ``key → machine-dict`` for that station.

        Examples
        --------
        >>> repo.build_station_index("CENIT", by="ip_external")
        {'10.190.50.200': {...}, ...}

        >>> repo.build_station_index("HOCOL", by="machine_name")
        {'cantagallo': {...}}
        """
        allowed = ["ip_external", "ip_internal", "machine_name"]
        if by not in allowed:
            raise ValueError(f"'by' must be one of {allowed}")

        data = self.get_station_data(station_name)
        result: dict[str, dict] = {}

        for machine in data:
            key_val = machine.get(by, None)
            if key_val is None:
                if skip_missing:
                    continue
                raise KeyError(f"Machine is missing '{by}': {machine}")

            if crash_on_duplicates and key_val in result:
                raise ValueError(
                    f"Duplicate value '{key_val}' for key '{by}' in '{station_name}' data"
                )

            result[key_val] = machine

        return result