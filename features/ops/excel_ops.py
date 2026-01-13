from settings import (
    STATION_MACHINES_DATA_SHEET,
    STATIONS_JSON_FILES_DIRECTORY,
    STATIONS_JSONS_CHECKSUM_FILE,
)

from features.stations.data_manager import StationDataManager
from features.stations.exceptions import InvalidExcelRowError, InvalidExcelFormatError


def generate_station_data_files() -> list[str]:

    try:
        manager = StationDataManager(
            xls_file= STATION_MACHINES_DATA_SHEET,
            stations_data_dir= STATIONS_JSON_FILES_DIRECTORY,
        )
    except FileNotFoundError as e:
        raise e

    sheet_names = manager.get_sheet_names()
    try:
        manager.load_sheet_data(sheet_names=sheet_names)
    except (InvalidExcelRowError, InvalidExcelFormatError) as e:
        raise e

    files = manager.generate_stations_data_files(
        sheet_names= sheet_names,
        checksum_file= STATIONS_JSONS_CHECKSUM_FILE,
        clear_directory= True,
    )

    return files
