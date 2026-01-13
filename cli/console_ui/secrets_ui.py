import getpass
import typer
from cryptography.fernet import InvalidToken

from utils import is_valid_fernet_key
from features.stations.secrets_handler import StationSecretsHandler

from cli.console_ui import usage_hints


def get_password(prompt: str) -> str:
    return getpass.getpass(prompt=prompt)


def prompt_and_validate_fernet_key() -> str:
    """
    Ask the user for a Fernet key, validate it, or exit with an error.
    """
    key = get_password(prompt="Input your encryption key: ")
    if not is_valid_fernet_key(key=key):
        typer.secho("Invalid Fernet key", err=True)
        raise typer.Exit(code=1)
    
    return key


def load_station_secrets_or_exit(secrets_handler: StationSecretsHandler, station_name: str) -> dict[str, str]:
    """
    Return decrypted secrets or abort with a helpful message.
    """
    try:
        return secrets_handler.get_station_secrets(station_name= station_name)
    except InvalidToken as e:
        typer.echo(f"{e}", err=True)
        typer.echo(f"Invalid decryption key for {station_name} secrets file.", err=True)
        raise typer.Exit(1)
    except FileNotFoundError as e:
        typer.echo(f"Secrets file for {station_name} NOT found", err=True)
        typer.echo(f"{e}", err=True)
        usage_hints.hint_encrypt_secret_templates()
        raise typer.Exit(1)
