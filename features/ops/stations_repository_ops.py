from features.stations.repository import StationDataRepository
from features.stations.exceptions import CorruptedDataFileError


def get_stored_station_names(repo: StationDataRepository) -> list[str]:
    try:
        return repo.get_station_names()
    except CorruptedDataFileError as e:
        raise e


def get_station_data(repo: StationDataRepository, station_name: str) -> list[dict]:
    return repo.get_station_data(station_name=station_name)
