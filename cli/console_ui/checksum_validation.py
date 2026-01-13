import typer

from settings import (
    STATION_MACHINES_DATA_SHEET,
)
from exceptions import ChecksumVerificationError

from features.stations.repository import StationDataRepository
from features.ops import checksums_ops

from cli.console_ui import usage_hints


def stations_json_data_files_integrity_check(stations_repo: StationDataRepository) -> None:
    """
    Run the JSON-data integrity check or exit with an error message.
    """
    typer.echo("🔍 Performing station data files integrity check…")
    try:
        checksums_ops.verify_station_json_data_files_checksums(
            stations_data_repo= stations_repo
        )
        typer.secho("✅ Stations data files integrity check passed")
    except (FileNotFoundError, ChecksumVerificationError) as e:
        typer.secho(f"ERROR: {e}", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(code=1)
    

def xls_data_file_integrity_check() -> None:
    """
    Verify the XLS checksum or exit with instructions if it fails or is missing.
    """
    typer.echo(f"🔍 Verifying checksum for: {STATION_MACHINES_DATA_SHEET}")
    try:
        match = checksums_ops.verify_xls_checksum()
    except FileNotFoundError as e:
        typer.echo("Stations data Excel file could NOT be found." , err=True)
        typer.secho(f"ERROR: {e}.", err=True)
        usage_hints.hint_load_data_from_excel()

        raise typer.Exit(code=1)
    
    except PermissionError as e:
        typer.echo(f"ERROR: {e}", err=True)
        usage_hints.hint_close_excel_on_windows()
        raise typer.Exit(1)

    if match:
        typer.secho("✅ Checksum match: Excel file is valid.")
    else:
        typer.secho("❌ Checksum mismatch: Excel file has changed!", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(code=1)