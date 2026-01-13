import typer

from features.stations.exceptions import InvalidExcelRowError, InvalidExcelFormatError
from features.ops import excel_ops
from features.backups.failures_store import FailuresStore

from cli.console_ui import (
    banners,
    usage_hints,
)

sheets_app = typer.Typer()


@sheets_app.command("load-data")
def load_data() -> None:
    """
    Loads stations data from the data excel file, then verifies and normalices the data.
    """  
    banners.welcome_banner()
    
    try:
        json_data_filesa = excel_ops.generate_station_data_files()
    except (InvalidExcelRowError, InvalidExcelFormatError) as e:
        typer.echo(f"{e}", err=True)
        raise typer.Exit(1)
    except FileNotFoundError as e:
        typer.echo(f"{e}", err=True)
        usage_hints.hint_crete_dotenv_file()
        raise typer.Exit(1)
    except PermissionError as e:
        typer.echo(f"ERROR: {e}", err=True)
        usage_hints.hint_close_excel_on_windows()
        raise typer.Exit(1)

    typer.echo("Created JSON data files: ")
    for f in json_data_filesa:
        typer.echo(f)
        
    FailuresStore.clear()
