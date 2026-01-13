import os
import fnmatch
import hashlib
import json
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Iterable

from log_utils import log_info, log_warning

logger = logging.getLogger(__name__)


## ────────── JSON Utilities ────────── ##

def load_json_file(filepath: str) -> dict:
    """Loads a JSON file and returns its contents as a dictionary."""
    text = Path(filepath).read_text(encoding="utf-8")

    return json.loads(text)

def write_json_file(filepath: str, data: dict, indent: int | None = 4) -> None:
    """
    Writes a dictionary to a JSON file.

    Args:
        filepath (str): Path to the output JSON file.
        data (dict): Dictionary to serialize.
        indent (int | None): Indentation level for pretty-printing. Use None for compact output.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii= False, indent= indent)

def prettify_json(data: dict, indent: int | None = 4) -> str:
    """
    Converts a dictionary to a formatted JSON string.

    Args:
        data (dict): Dictionary to format.
        indent (int | None): Indentation level. Use None for compact output.

    Returns:
        str: JSON string.
    """
    return json.dumps(data, indent= indent)


## ────────── Directory Utilities ────────── ##

def list_directory(
        directory: str,
        include_patterns: Iterable[str] = (),
        exclude_patterns: Iterable[str] = (),
        full_path: bool = True,
        recursive: bool = False,
        include_hidden: bool = False,
    ) -> list[str]:
    """
    Lists files in the given directory that match include patterns,
    excluding any that match the exclude patterns.

    Args:
        directory (str): The directory to search in.
        include_patterns (Iterable[str]): Glob patterns to include (e.g., ['*.json']).
        exclude_patterns (Iterable[str]): Glob patterns to exclude (e.g., ['*_backup.json']).
        full_path (bool): If True, return full file paths. If False, return only file names.
        recursive (bool): If True, search recursively through subdirectories.
        include_hidden (bool): If True, include hidden files.

    Returns:
        list[str]: list of file paths.
    """
    base = Path(directory)
    if not base.is_dir():
        print("perros")
        return []

    # choose the right glob method
    walker = base.rglob("*") if recursive else base.glob("*")

    results = []
    for path in walker:
        name = path.name

        # skip directories, and hidden files if requested
        if not path.is_file() or (not include_hidden and name.startswith(".")):
            continue

        # must match at least one include pattern (or include everything if none given)
        if include_patterns:
            if not any(fnmatch.fnmatch(name, pat) for pat in include_patterns):
                continue

        # must not match any exclude pattern
        if exclude_patterns and any(fnmatch.fnmatch(name, pat) for pat in exclude_patterns):
            continue

        results.append(str(path) if full_path else name)

    return results


    # included = set()
    # for pattern in include_patterns:
    #     included.update(glob.glob(
    #         pathname= os.path.join(directory, pattern),
    #         recursive= recursive,
    #         include_hidden= include_hidden
    #         )
    #     )

    # excluded = set()
    # for pattern in exclude_patterns:
    #     excluded.update(glob.glob(
    #         pathname= os.path.join(directory, pattern),
    #         recursive= recursive,
    #         include_hidden= include_hidden
    #         )
    #     )

    # filenames = [
    #     f if full_path else os.path.basename(f)
    #     for f in included
    #     if f not in excluded and os.path.isfile(f)
    # ]
    
    # return filenames


def clear_direcroty(dir_path: str) -> None:
    """
    Deletes all files in the given directory, but does not delete the directory itself.

    Args:
        dir_path (str): Path to the directory to clear.

    Raises:
        FileNotFoundError: If the directory does not exist.
        NotADirectoryError: If the path is not a directory.
    """
    if not os.path.exists(dir_path):
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")
    if not os.path.isdir(dir_path):
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")

    for filename in os.listdir(dir_path):
        file_path = os.path.join(dir_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)


## ────────── Checksum Utilities ────────── ##

def file_sha256sum(filepath: str) -> str:
    """
    Calculates the SHA-256 checksum of a file.

    Args:
        filepath (str): Path to the file.

    Returns:
        str: Hexadecimal SHA-256 checksum string.
    """
    with open(filepath, "rb") as f:
        digest = hashlib.file_digest(f, "sha256")

    return digest.hexdigest()

def generate_sha256_checksum_file(
        file_list: list[str],
        output_file: str,
    ) -> None:
    """
    Generates a SHA-256 checksum file for a list of files.

    Each line in the output file is formatted as: <hash><space><space><filepath>

    Args:
        file_list (list[str]): List of file paths to hash.
        output_file (str): Path to the checksum output file.

    Notes:
        Invalid or non-existent files will be skipped with a warning.
    """
    if not file_list:
        logger.warning("No files to hash. SHA256 Checksum file will not be created.")
        return

    with open(output_file, 'w') as out:
        for filename in file_list:
            if os.path.isfile(filename):
                hash_val = file_sha256sum(filename)
                # Format: <hash><space><space><filepath>
                out.write(f"{hash_val}  {filename}\n")
            else:
                logger.warning(f"'{filename}' is not a valid file and will be skipped.")

def checksum_verfication_sha256(checksum_file: str) -> bool:
    """
    Verifies the integrity of files listed in a checksum file using SHA-256.
    The checksum file should contain lines in the format: <hash><space><space><filepath>

    Args:
        checksum_file (str): Path to the SHA-256 checksum file.

    Returns:
        bool: True if all file hashes match, False if any mismatch or file is missing.
    """
    if not os.path.isfile(checksum_file):
        raise FileNotFoundError(f"Checksum file not found: {checksum_file}")
    
    all_valid = True
    mismatch_cnt = 0
    
    with open(checksum_file, "r", encoding="utf-8") as f:
        for cnt, line in enumerate(f, start=1):
            parts = line.strip().split()
            if len(parts) != 2:
                log_warning(f"line {cnt} is improperly formatted", logger)
                continue

            expected_hash, filepath = parts
            if not os.path.isfile(filepath):
                log_warning(f"Missing file: {filepath}", logger)
                all_valid = False
                continue

            actual_hash = file_sha256sum(filepath)
            if actual_hash != expected_hash:
                log_info(f"{filepath}: FAILED", logger)
                all_valid = False
                mismatch_cnt += 1
            else:
                log_info(f"{filepath}: OK", logger)

    if mismatch_cnt > 0:
        log_warning(
            f"{mismatch_cnt} computed checksums did NOT match",
            logger
        )
    
    return all_valid


## ────────── Encryption Utilities ────────── ##

def is_valid_fernet_key(key: str | bytes) -> bool:
    """
    Validates whether a given key is a valid Fernet encryption key.

    Args:
        key (str | bytes): The key to validate.

    Returns:
        bool: True if the key is valid for Fernet, False otherwise.
    """
    try:
        Fernet(key= key)
        return True
    except ValueError:
        return False