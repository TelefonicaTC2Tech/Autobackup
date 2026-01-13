import typer
from settings import DEFAULT_CLI_NAME


def hint_load_data_from_excel() -> None:
    """
    Print a short instruction telling the user how to load stations
    data from the Excel source.
    """
    name = DEFAULT_CLI_NAME
    typer.echo("Run the following command to load the stations data from the Excel file:")
    typer.echo(f"{' '*4}{name} sheets load-data")


def hint_crete_dotenv_file() -> None:
    typer.echo("Create a .env file at the same level of the executable file.")
    typer.echo("Then add the filepath to the excel file that holds the sations data. Example:")
    typer.echo(f"{' '*3} STATION_MACHINES_DATA_SHEET=C:\\Users\\my-user\\documents\\my-excel-file.xlsx")

def hint_generate_secret_templates() -> None:
    typer.echo("Run the following command to generate the stations secret templates.")
    typer.echo(f"{' '*4}{DEFAULT_CLI_NAME} secrets generate-templates")

def hint_encrypt_secret_templates() -> None:
    typer.echo("Run the following command to encrypt the existing secret templates.")
    typer.echo(f"{' '*4}{DEFAULT_CLI_NAME} secrets encrypt-templates")

def hint_close_excel_on_windows(err: bool = True) -> None:
    """
    Tell the user to close the Excel file first (Windows-specific tip).
    """
    typer.echo(
        "Tip: On Windows, please make sure the file is not open in Excel "
        "or any other application, and try again.",
        err=err,
    )