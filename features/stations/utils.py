import utils as general_utils


def verify_stations_xls_file_checksum(xls_file: str, json_checksum_file: str) -> bool:
    """
    Verifies that the checksum of an Excel file matches the stored value in a JSON metadata file.

    Args:
        xls_file (str): Path to the Excel file.
        josn_checksum_file (str): Path to the JSON metadata file containing the expected checksum.

    Returns:
        bool: True if the actual checksum matches the expected value; False otherwise.

    Raises:
        KeyError: If the 'xls_checksum' key is missing from the JSON file.
    """
    data = general_utils.load_json_file(json_checksum_file)

    expected_checksum = data.get("xls_checksum")
    if expected_checksum is None:
        raise KeyError(f"'xls_checksum' key not found in {json_checksum_file}")

    actual_checksum = general_utils.file_sha256sum(xls_file)

    return actual_checksum == expected_checksum