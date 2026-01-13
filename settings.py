import os
from dotenv import load_dotenv

load_dotenv()

DEBUG: bool = os.getenv("DEBUG", "false").lower().strip() == "true"

LOG_FILE = "./app.log"

LOG_FILE_MODE = os.getenv("LOG_FILE_MODE", "w")


STATION_MACHINES_DATA_SHEET = os.getenv("STATION_MACHINES_DATA_SHEET", "")

DATA_DIR = os.path.join(".", "data")

STATIONS_JSON_FILES_DIRECTORY = os.path.join(DATA_DIR, "stations_metadata")

STATIONS_JSONS_CHECKSUM_FILE = os.path.join(STATIONS_JSON_FILES_DIRECTORY, "sha256sum.txt")

STATIONS_GENERAL_INFO_JSON_FILE = os.path.join(STATIONS_JSON_FILES_DIRECTORY, "general_info.json")

STATIONS_SECRETS_DIRECTORY = os.path.join(DATA_DIR, "stations_secrets")

STATIONS_SECRETS_ENCRYPTED_DIR = os.path.join(STATIONS_SECRETS_DIRECTORY, "encrypted")

STATIONS_SECRETS_TEMPLATES_DIR = os.path.join(STATIONS_SECRETS_DIRECTORY, "templates")

# STATIONS_SECRETS_CHECKSUM_FILE = os.path.join(STATIONS_SECRETS_DIRECTORY, "sha256sum.txt")

BACKUPS_DESTINATION_DIRECTORY = os.path.join(DATA_DIR, "nozomi_backups")

BACKUP_FAILURES_DIRECTORY = os.path.join(DATA_DIR, "backup_failures")

BACKUP_FAILURES_JSON_FILE = os.path.join(BACKUP_FAILURES_DIRECTORY, "backup_failures.json")

BASH_SCRIPTS_DIRECTORY = os.getenv("BASH_SCRIPTS_DIRECTORY", os.path.join(".", "bash_scripts") )

BASH_BACKUPS_SCRIPT = os.path.join(BASH_SCRIPTS_DIRECTORY, "backups.sh")


DEFAULT_SSH_USERNAME = "admin"

DEFAULT_CLI_NAME = "narbal"

VERSION = "0.1.0"