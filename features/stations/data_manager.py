import os
from typing import Iterator
import pandas as pd
from pydantic import ValidationError

import utils
import log_utils

from features.stations.schemas import StationRow
from features.stations.exceptions import InvalidExcelFormatError, InvalidExcelRowError


logger = log_utils.logging.getLogger(__name__)


class StationDataManager:
    """
    Manages the loading, validation, normalization, and export of station data
    from an Excel file.

    Responsibilities:
    - Validates Excel sheet structure and columns.
    - Normalizes each row using a Pydantic schema.
    - Exports each sheet's data to separate JSON files.
    - Generates a metadata file (general_info.json) and a checksum file.
    """
    JSON_FILENAME_SUFFIX = "_data.json"
    
    COLUMN_NAMES = (
        "type",
        "machine_name",
        "ip_external",
        "ip_internal",
        "state",
    )

    STATE_VALUES = (
        "instalada",
        "monitoreando",
        "aprendizaje",
        "pendiente",
    )

    def __init__(
            self,
            xls_file: str,
            stations_data_dir: str,
        ) -> None:
        """
        Initializes the StationDataManager with the given Excel file and output directory.

        Args:
            xls_file (str): Path to the input Excel file containing station data.
            stations_data_dir (str): Directory where the exported JSON and metadata files will be saved.

        Raises:
            FileNotFoundError: If the Excel file or the output directory does not exist.
        """    
        self.xls_path = xls_file
        if not os.path.isfile(xls_file):
            raise FileNotFoundError(f"File not found: {xls_file}")

        self.stations_data_dir = stations_data_dir
        if not os.path.isdir(stations_data_dir):
            raise NotADirectoryError(f"Directory not found: {stations_data_dir}")

        self._xls = pd.ExcelFile(xls_file)
        self.normalized_data: dict[str, pd.DataFrame] = {}

    def get_sheet_names(self) -> list[str]:
        """
        Retrieves the names of all sheets in the Excel file.

        Returns:
            list[str]: List of sheet names as strings.
        """
        # Convert all sheet names to str
        return [str(name) for name in self._xls.sheet_names]
        
    def validate_columns(self) -> None:
        """
        Validates that each sheet in the Excel file contains only the expected columns.

        Raises:
            InvalidExcelFormatError: If there are missing or unexpected columns in any sheet.
        """
        for sheet in self.get_sheet_names():
            df = self._xls.parse(sheet, nrows=0)  # only read headers

            if len(df.columns) > len(self.COLUMN_NAMES):
                raise InvalidExcelFormatError(
                    f"Sheet '{sheet}' has {len(df.columns)} columns, only {len(self.COLUMN_NAMES)} are allow.\
                    The only allow columns are: {self.COLUMN_NAMES}"
                )

            actual = df.columns.tolist()

            missing = [col for col in self.COLUMN_NAMES if col not in actual]
            unexpected = [col for col in actual if col not in self.COLUMN_NAMES]

            if missing or unexpected:
                error_msg = f"Sheet '{sheet}' mismatch:"
                if missing:
                    error_msg += f" Missing columns {missing}."
                if unexpected:
                    error_msg += f" Unexpected columns {unexpected}."

                raise InvalidExcelFormatError(f"Columns names validation error. {error_msg}")

    def _normalize_rows(self, records: list[dict]) -> Iterator[dict]:
        """
        Normalizes and validates each row in a list of station records.

        Args:
            records (list[dict]): List of dicts representing Excel rows.

        Yields:
            dict: Validated and normalized row data.

        Raises:
            ValueError: If a row fails Pydantic validation.
        """
        for i, record in enumerate(records, start=1):
            try:
                row = StationRow(**record)
                data = row.model_dump() # return dict, not pydantic model

                if data["ip_internal"] is not None:
                    data["ip_internal"] = str(data["ip_internal"])
                if data["ip_external"] is not None:
                    data["ip_external"] = str(data["ip_external"])

                yield data

            except ValidationError as e:
                raise InvalidExcelRowError(
                    row_index= i,
                    validation_error= e,
                    sheet_name= None,
                )
    
    def load_sheet_data(self, sheet_names: list[str]) -> dict[str, pd.DataFrame]:
        """
        Loads and normalizes data from specified Excel sheets.

        Args:
            sheet_names (list[str]): Sheet names to load and validate.

        Returns:
            dict[str, pd.DataFrame]: Normalized data indexed by sheet name.

        Raises:
            ValueError: If validation fails for any row in any sheet.
            InvalidExcelFormatError: If there are missing or unexpected columns in any sheet.
        """
        self.validate_columns()

        for sheet in sheet_names:
            df = self._xls.parse(sheet)
            # Replace NaN with None
            df = df.where(pd.notnull(df), None)
            records = df.to_dict(orient='records')
            
            try:
                normalized_iter = self._normalize_rows(records)
                normalized_df = pd.DataFrame(normalized_iter)
            except InvalidExcelRowError as e:
                e.sheet_name = sheet
                raise e
                # raise ValueError(
                #     f"Validation error while normalizing data from sheet '{sheet}'"
                #     ) from e            

            self.normalized_data[sheet] = normalized_df

        return self.normalized_data
    
    def get_data_as_dict(self, sheet_names: list[str]) -> dict[str, list[dict]]:
        """
        Converts normalized data into JSON-serializable format.

        Args:
            sheet_names (list[str]): List of sheet names to include in output.

        Returns:
            dict[str, list[dict]]: Dictionary of lists of row dictionaries.
        """
        return {
            sheet_name: df.to_dict(orient="records")
            for sheet_name, df in self.normalized_data.items()
            if sheet_name in sheet_names
        }

    def export_sheet_to_json_files(
            self,
            sheet_names: list[str],
            indent: int | None = 4
        ) -> list[str]:
        """
        Export data from specified sheets to individual JSON files.
        Each sheet's data is saved as a separate JSON file named
        '<sheet_name>_data.json' inside the given output directory.

        Args:
            sheet_names: List of sheet names to export.
            indent: Number of spaces for JSON indentation.
                    Defaults to 4 for pretty printing. Use None for compact output.

        Returns:
            list[str]: Paths to the created JSON files.

        Notes:
            - If the stations data directory does not exist, it will be created (only the last-level).
            - If none of the specified sheets are found, no files will be written.
        """
        if not os.path.exists(self.stations_data_dir):
            os.mkdir(self.stations_data_dir)  # Only create the last-level directory
        
        records = self.get_data_as_dict(sheet_names)
        # check for empty dict, no sheets found
        if not records: 
            log_utils.log_info(
                "Nothing to write: no matching sheets found in normalized_data",
                logger
            )
            return []

        json_filespaths = []
        for sheet, data in records.items():
            filename = f"{sheet}{self.JSON_FILENAME_SUFFIX}"
            filepath = os.path.join(self.stations_data_dir, filename)
            utils.write_json_file(filepath, {sheet: data}, indent= indent)
            json_filespaths.append(filepath)

        return json_filespaths

    def create_checksum_file(self, file_list: list[str], output_file: str) -> None:
        """
        Generates a SHA256 checksum file for the given list of files.

        Args:
            file_list (list[str]): Paths of files to include in the checksum.
            output_file (str): Path to the output checksum file.
        """
        utils.generate_sha256_checksum_file(file_list, output_file)

    def _create_general_info_json(self) -> str:
        """
        Creates a general_info.json file containing metadata about the Excel processing.

        The JSON includes:
        - A mapping of station names to their corresponding JSON file names.
        - A SHA256 checksum of the original Excel file.

        Returns:
            str: Path to the created general_info.json file.

        Raises:
            RuntimeError: If no normalized data is present (i.e., load_sheet_data not called).
        """
        if not self.normalized_data:
            raise RuntimeError("No normalized data available. Call load_sheet_data() first.")
        
        if not os.path.exists(self.stations_data_dir):
            os.mkdir(self.stations_data_dir)  # Only create the last-level directory
        
        stations_data = {
            station_name: f"{station_name}{self.JSON_FILENAME_SUFFIX}"
            for station_name in self.normalized_data.keys()
        }

        data = {
            "stations_data": stations_data,
            "xls_checksum": utils.file_sha256sum(self.xls_path)
        }

        filename = "general_info.json"
        filepath = os.path.join(self.stations_data_dir, filename)
        utils.write_json_file(filepath, data)

        return filepath

    def generate_stations_data_files(
            self,
            sheet_names: list[str],
            checksum_file: str,
            clear_directory: bool = True
        ) -> list[str]:
        """
        Orchestrates the full process of exporting sheet data to JSON, generating
        metadata, and creating a checksum file.

        Args:
            sheet_names (list[str]): List of sheets to process.
            checksum_file (str): Path to the checksum file to create.
            clear_directory (bool): Whether to clear the output directory before writing.

        Returns:
            list[str]: List of all created file paths (JSONs, metadata, checksum).
        """
        if not self.normalized_data:
            raise RuntimeError("No normalized data available. Call load_sheet_data() first.")

        if clear_directory:
            utils.clear_direcroty(self.stations_data_dir)

        json_files = self.export_sheet_to_json_files(sheet_names)
        genaral_info_file = self._create_general_info_json()

        json_files.append(genaral_info_file)

        self.create_checksum_file(json_files, checksum_file)
        
        return json_files + [checksum_file]
    
