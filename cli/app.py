import typer

from settings import (
    VERSION,
    DEFAULT_CLI_NAME,
)

from cli.commands.backup import backup_app
from cli.commands.secrets import secrets_app
from cli.commands.sheets import sheets_app
from cli.console_ui import banners

app = typer.Typer(
    name= f"{DEFAULT_CLI_NAME}",
    help= f"{DEFAULT_CLI_NAME} — Automates generating, retrieving, and archiving Nozomi Guardian backups across the selected stations.",
)

app.add_typer(backup_app, name="backup", help="Backup related operations")
app.add_typer(secrets_app, name="secrets", help="Secrets related operations")
app.add_typer(sheets_app, name="sheets", help="Excel sheet related operations")


@app.command("about", help="Show program information and company logo")
def about() -> None:
    banners.display_general_info_banner()


@app.callback(invoke_without_command=True)
def global_options(ctx: typer.Context, version: bool = False):
    if version:
        typer.echo(f"{DEFAULT_CLI_NAME} version {VERSION}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        # If they ran just `mycli` with no command, print the top-level help
        typer.echo(ctx.get_help())