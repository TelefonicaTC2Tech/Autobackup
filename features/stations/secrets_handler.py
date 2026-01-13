import os
import json
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError

from settings import (
    STATIONS_SECRETS_TEMPLATES_DIR,
    STATIONS_SECRETS_ENCRYPTED_DIR,
)
import utils

from .schemas import StationsSecretsTemplate
from .repository import StationDataRepository
from .exceptions import SecretsTemplateValidationError


class StationSecretsHandler:
    """
    Handles encryption, decryption, and management of station-specific secret files.

    This class supports:
    - Generating editable JSON templates with external IPs for manual password entry
    - Encrypting and decrypting JSON secrets using Fernet encryption
    - Loading encrypted secrets into Python dictionaries
    - Removing unencrypted template files after encryption
    - Managing secrets on a per-station basis using consistent file naming patterns

    Constants:
        TEMPLATES_SUFIX (str): Suffix used for secrets JSON templates (unencrypted).
        ENCRYPTED_TEMPLATES_SUFIX (str): Suffix used for encrypted secrets files.
    """
    TEMPLATES_SUFFIX = "_secrets.json"
    ENCRYPTED_TEMPLATES_SUFFIX= "_secrets.json.enc"

    def __init__(
            self,
            key: str | bytes,
        ) -> None:
        """
        Initializes the handler with an encryption key.

        Args:
            key (str | bytes): Fernet key used to encrypt and decrypt secrets.
        """
        self.encryption_key = key

    def decrypt_fernet_file(self, filepath: str) -> bytes:
        """
        Decrypts a file encrypted with Fernet and returns the raw decrypted bytes.

        Args:
            filepath (str): Path to the encrypted file.

        Returns:
            bytes: Decrypted contents of the file.

        Raises:
            ValueError: If the Fernet key is invalid.
            InvalidToken: If the file contents cannot be decrypted.
        """
        encrypted = Path(filepath).read_bytes()
        try: 
            fernet = Fernet(self.encryption_key)
            decrypted = fernet.decrypt(encrypted)

        except ValueError as e: #handle Fernet class initializaton errors
            raise  ValueError("Invalid Fernet key.") from e
        except (InvalidToken, TypeError) as e: #handle decrypt method errors
            raise type(e)("Error occurred during file decryption.") from e

        return decrypted

    def encrypt_fernet_file(self, data: bytes, filepath: str) -> None:
        """
        Encrypts bytes using Fernet and writes them to a file.

        Args:
            data (bytes): Data to encrypt.
            filepath (str): Path where the encrypted file will be saved.

        Raises:
            ValueError: If the Fernet key is invalid.
            TypeError: If the input data is not in byte format.
        """
        try:
            fernet = Fernet(self.encryption_key)
            encrypted = fernet.encrypt(data)
            Path(filepath).write_bytes(encrypted)
        except ValueError as e:
            raise ValueError("Invalid Fernet key.") from e
        except TypeError as e:
            raise TypeError("Invalid input type for encryption.") from e
        
    def load_encrypted_json(self, filepath: str) -> dict:
        """
        Loads and decrypts a JSON file encrypted with Fernet.

        Args:
            filepath (str): Path to the encrypted JSON file.

        Returns:
            dict: Parsed contents of the decrypted JSON file.
        """
        decrypted_bytes = self.decrypt_fernet_file(filepath)

        return json.loads(decrypted_bytes.decode("utf-8"))

    def save_encrypted_json(
            self,
            filepath: str,
            data: dict,
            indent: int | None = 4
        ) -> None:
        """
        Serializes a dictionary to JSON, encrypts it, and saves it to a file.

        Args:
            filepath (str): Path where the encrypted JSON file will be saved.
            data (dict): Data to serialize and encrypt.
            indent (int | None): Number of spaces for JSON indentation. Use None for compact output.
        """
        json_bytes = json.dumps(data, indent= indent).encode("utf-8")
        self.encrypt_fernet_file(json_bytes, filepath)
    
    @classmethod
    def get_template_paths(cls) -> list[str]:
        """
        Return paths of every *_secrets.json file found in
        STATIONS_SECRETS_TEMPLATES_DIR.  Does **no** I/O besides the directory
        scan.
        """
        pattern = f"*{cls.TEMPLATES_SUFFIX}"
        return sorted(
            utils.list_directory(
                directory= STATIONS_SECRETS_TEMPLATES_DIR,
                include_patterns= [pattern],
            )
        )

    @classmethod
    def generate_secrets_templates(
            cls,
            json_data_files: list[str],
            output_dir: str,
            indent: int | None = 4
        ) -> list[str]:
        """
        Generates editable secrets template files for the given station JSON files.

        Each template maps external IPs to empty password strings for user input.

        Args:
            json_data_files (list[str]): Paths to station JSON data files.
            output_dir (str): Directory where the templates will be saved.
            indent (int | None): Indentation used in the output JSON files.

        Returns:
            list[str]: List of paths to the generated template files.
        """
        json_filespaths = []
        for file in json_data_files:
            data = utils.load_json_file(file)
            # Get the single key. The json shuold only have
            # one global key that is the name of the station
            station_name = next(iter(data))

            new_data = {}
            for machine in data[station_name]:
                ip = machine["ip_external"]
                if ip is None:
                    continue
                # format "<external_ip>": "<password>"
                new_data[ip] = ""
            
            filename = f"{station_name}{cls.TEMPLATES_SUFFIX}"
            filepath = os.path.join(output_dir, filename)
            utils.write_json_file(filepath, {station_name: new_data}, indent= indent)
            json_filespaths.append(filepath)

        return json_filespaths
    
    def validate_template_data(self, data: dict[str, dict[str, str]]) -> None:
        """Validate the JSON structure and cross-check it against station data."""
        if len(data) != 1:
            raise SecretsTemplateValidationError("create corrupted template file eerror")

        try:
            stations_repo = StationDataRepository()
        except FileNotFoundError as e:
            raise e
        
        stations_names = stations_repo.get_station_names()
        template_station = next(iter(data)) # same as list(data.keys())[0]

        if template_station not in stations_names:
            raise SecretsTemplateValidationError("create corrupted template file eerror")
        
        station_data = stations_repo.get_station_data(template_station)
        station_ips = [
            m["ip_external"]
            for m in station_data
            if m["ip_external"] is not None
        ]

        try:
            StationsSecretsTemplate.model_validate(
                data,
                context={
                    "expected_station_name": template_station,
                    "expected_ips": station_ips,
                }
            )
        except ValidationError as e:
            raise e
        
    def validate_template_file(self, filepath: str) -> None:
        """Load a template file from disk and validate its contents."""
        tempalte_data = utils.load_json_file(filepath= filepath)
        self.validate_template_data(data= tempalte_data)
    
    def encrypt_secrets_template(self, template_path: str, validate: bool = True) -> str:
        """
        Encrypt **one** *_secrets.json template and return the path created.

        Args:
        template_path : str
            Absolute or relative path to a single template JSON file.
        validate : bool
            Validate the JSON before writing (default True).

        Returns:
            str: Filepath to the encrypted file.
        """
       
        data = utils.load_json_file(template_path)
        if validate:
            self.validate_template_data(data= data)

        # Get the single key. The json shuold only have
        # one global key that is the name of the station
        station_name = next(iter(data))
        
        outfile = os.path.join(
            STATIONS_SECRETS_ENCRYPTED_DIR,
            f"{station_name}{self.ENCRYPTED_TEMPLATES_SUFFIX}",
        )
        self.save_encrypted_json(outfile, data)
        
        return outfile
    
    def encrypt_multiple_secrets_templates(self, template_files: list[str], validate: bool = True) -> list[str]:
        outfiles = []
        for f in template_files:
            encrypted_file =  self.encrypt_secrets_template(template_path= f, validate= validate)
            outfiles.append(encrypted_file)

        return outfiles
    
    def remove_secrets_templates(self) -> None:
        """
        Deletes all unencrypted secrets template files in the secrets templates directory.

        Returns:
            list[str]: List of paths to the deleted files.
        """
        utils.clear_direcroty(dir_path= STATIONS_SECRETS_TEMPLATES_DIR)
    
    def load_encrypted_secret_file(self, station_name: str) -> dict[str, str]:
        """
        Loads and decrypts secrets for the given station name.

        Args:
            station_name (str): Station whose secrets will be loaded.

        Returns:
            dict[str, str]: station secrets dictionary ({"ip": "password"}).
        """      
        filepath = os.path.join(STATIONS_SECRETS_ENCRYPTED_DIR, f"{station_name}{self.ENCRYPTED_TEMPLATES_SUFFIX}")
        decrypted_data = self.load_encrypted_json(filepath)

        return decrypted_data[station_name]
    
    def get_station_secrets(self, station_name: str) -> dict[str, str]:
        """
        Returns cached secrets if available, otherwise loads from file and caches them.
        """
        return self.load_encrypted_secret_file(station_name= station_name)

