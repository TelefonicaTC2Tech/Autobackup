import os

from settings import (
    STATIONS_SECRETS_TEMPLATES_DIR,
    STATIONS_JSON_FILES_DIRECTORY,
)

from features.stations.secrets_handler import StationSecretsHandler
from features.stations.repository import StationDataRepository


def generate_secret_templates(
    station_names: list[str],
    station_data_repo: StationDataRepository,
) -> list[str]:
    all_data_files = station_data_repo.get_stations_data_files()

    desired_files = []
    for name in station_names:
        if name not in all_data_files:
            raise ValueError(f"Station '{name}' does not exist.")
        
        filepath = os.path.join(STATIONS_JSON_FILES_DIRECTORY, all_data_files[name])
        desired_files.append(filepath)

    return StationSecretsHandler.generate_secrets_templates(
        json_data_files= desired_files,
        output_dir= STATIONS_SECRETS_TEMPLATES_DIR,
    )


def get_station_secrets(handler: StationSecretsHandler, station_name: str) -> dict[str, str]:
    return handler.get_station_secrets(station_name=station_name)
