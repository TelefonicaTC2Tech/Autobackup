import typer
from pydantic import ValidationError
from pathlib import Path

from settings import (
    DEBUG,
)

from features.stations.repository import StationDataRepository
from features.stations.secrets_handler import StationSecretsHandler
from features.ops import secrets_ops

from cli.console_ui import (
    banners,
    menus,
    checksum_validation,
    secrets_ui,
    usage_hints,
)

secrets_app = typer.Typer()


@secrets_app.command("generate-key")
def generate_key() -> None:
    """
    Generate a new Fernet key and print it to the terminal.
    """
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    typer.echo("🔐 Fernet key generated:")
    typer.echo(key)
    typer.echo("⚠️ Save this key securely. It will not be stored.")


@secrets_app.command("generate-templates")
def generate_templates():
    """
    Create a new secrets template file.
    """
    banners.welcome_banner()
    
    try:
        stations_repo = StationDataRepository()
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(1)
    
    checksum_validation.stations_json_data_files_integrity_check(stations_repo= stations_repo)

    typer.echo()
    selected_stations = menus.display_avalible_stations_menu(
        stations_data_repo= stations_repo,
    )

    station_names = [name for _, name in selected_stations]
    templates = secrets_ops.generate_secret_templates(
        station_names= station_names,
        station_data_repo= stations_repo,
    )

    for t in templates:
        typer.echo(t)

    
@secrets_app.command("encrypt-templates")
def encrypt_templates() -> None:
    """
    Encrypt all station‐secret templates in
      data/stations_secrets/templates/
    into
      data/stations_secrets/encrypted/
    """
    banners.welcome_banner()
    
    key = secrets_ui.prompt_and_validate_fernet_key()
    
    secrets_handler = StationSecretsHandler(
        key= key,
    )

    typer.echo()
    selected_tamplates = menus.display_avalible_secrets_templates_menu()
    template_files = [f for _, f in selected_tamplates]

    typer.confirm("Are you sure you want to encrypt the selected templates?", abort=True)

    for f in template_files:
        try:
            secrets_handler.validate_template_file(filepath= f)
        except ValidationError as e:
            typer.echo()
            typer.echo(f"Template {f} validation error", err=True)
            typer.echo(e, err=True)
            raise typer.Exit(1)
            
    
    # we alredy validated the files content in the previous for loop
    encrypted_files = secrets_handler.encrypt_multiple_secrets_templates(
        template_files= template_files,
        validate= False
    )

    typer.echo("Generated files:")
    for i, path in enumerate(encrypted_files, start=1):
        typer.echo(f"{i}. {path}")

    delete_raw_tempaltes = True
    if DEBUG:
        delete_raw_tempaltes = typer.confirm("Do you want to delete the previously selected raw template files?", abort=False)

    if not delete_raw_tempaltes:
        return
    
    typer.echo("\nDeleting raw template files. Deleted:")
    for i, f in enumerate(template_files, start=1):
        try:
            Path(f).unlink()
            typer.echo(f"{i}. {f}")
        except FileNotFoundError:
            typer.echo(f"WARNING: File not found: {f}", err=True)
            continue
        
