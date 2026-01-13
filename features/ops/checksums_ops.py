from settings import (
    STATION_MACHINES_DATA_SHEET,
    STATIONS_GENERAL_INFO_JSON_FILE,
)

from features.stations.utils import verify_stations_xls_file_checksum
from features.stations.repository import StationDataRepository
from exceptions import ChecksumVerificationError


def verify_xls_checksum() -> bool:
    return verify_stations_xls_file_checksum(
        xls_file=STATION_MACHINES_DATA_SHEET,
        json_checksum_file=STATIONS_GENERAL_INFO_JSON_FILE,
    )


def verify_station_json_data_files_checksums(stations_data_repo: StationDataRepository) -> bool:
    try:
        return stations_data_repo.verify_stations_data_checksum_file()
    except FileNotFoundError as e:
        raise e
    except ChecksumVerificationError as e:
        raise e
