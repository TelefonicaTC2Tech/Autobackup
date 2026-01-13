import typer
from features.stations.repository import StationDataRepository
from features.stations.secrets_handler import StationSecretsHandler
from features.stations.exceptions import CorruptedDataFileError
from features.backups.failures_store import FailuresStore

from cli.console_ui import (
    usage_hints,
    parsers,
)


def display_list(items: list[str], header: str = "Available items:") -> None:
        """
        Prints a numbered list with an optional header.
        """
        typer.echo(header)
        for i, name in enumerate(items, start=1):
            typer.echo(f"  {i}. {name}")

def prompt_list_selection(
    items: list[str],
    header: str,
    prompt: str = "Enter numbers (e.g. 1,3-5): "
) -> list[tuple[int, str]]:
    """
        Displays numbered `items`, asks for a selection string, and returns
        the chosen items (1-based indices).
    """
    display_list(items= items, header= header)
    sel = input(f"{prompt}").strip()

    try:
        nums = parsers.parse_number_selection(sel)
    except ValueError as e:
        raise e
    
    # filter out-of-range and convert to zero-based
    chosen: list[tuple[int, str]] = []
    for n in sorted(nums):
        if 1 <= n <= len(items):
            chosen.append((n, items[n-1]))
        else:
            raise ValueError(f"invalid choice: {n}")

    return chosen

def display_avalible_stations_menu(
        stations_data_repo: StationDataRepository,
        header: str = "Available Stations: ",
        prompt: str = "Select stations by numbers (e.g. 1,3-5): "
    ) -> list[tuple[int, str]]:
    try:
        station_names = stations_data_repo.get_station_names()
    except CorruptedDataFileError as e:
        typer.echo(f"Error: {e}", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(1)

    try:
        selected_stations = prompt_list_selection(items= station_names, header= header, prompt= prompt)
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)

    return selected_stations


def display_avalible_secrets_templates_menu(
        header: str = "Available secrets templates: ",
        prompt: str = "Select station tamplates by numbers (e.g. 1,3-5): "
    ) -> list[tuple[int, str]]:
   
    template_files = StationSecretsHandler.get_template_paths()
    if not template_files:
        typer.secho("⚠️ No secrets templates found")
        usage_hints.hint_generate_secret_templates()
        raise typer.Exit(1)

    try:
        selected_templates = prompt_list_selection(items= template_files, header= header, prompt= prompt)
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)

    return selected_templates


def display_available_machines_menu(
        station_data: list[dict],
        header: str = "Available machines:",
        prompt: str = "Select machines by numbers (e.g. 1,3-5): "
    ) -> list[tuple[int, str, str]]:
    """
    Given station_data, show only the GUARDIAN machines (excluding 'pendiente'),
    prompt for a numbered selection, and return a list of
    (1-based index, display_label, ip_external) tuples.
    """
    # Build the list of IPs we care about:
    machines_data = [
        (m["machine_name"], m["ip_external"])
        for m in station_data
        if m.get("type") == "GUARDIAN" and m.get("state") != "pendiente"
    ]
    if not machines_data:
        typer.secho("⚠️ No eligible machines found in this station", err=True)
        raise typer.Exit(1)

    items = [
        f"{m[0]} ({m[1]})"
        for m in machines_data
    ]

    # Prompt for selection:
    try:
        selections = prompt_list_selection(
            items= items,
            header= header,
            prompt= prompt,
        )
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)
    
    result = []
    for idx, _ in selections:
        name, ip = machines_data[idx - 1]
        result.append((idx, name, ip))

    return result


def display_stations_with_failed_backups_menu(
        fails_store: FailuresStore,
        header: str = "Stations with stored failures:",
        prompt: str = "Select stations by numbers (e.g. 1,3-5): ",
    ) -> list[tuple[int, str]] | None:
    """
    Display a numbered list of stations that currently have recorded
    backup failures and prompt the user to select which ones to retry.

    Returns
    -------
    list[tuple[int, str]] | None
        • A list of `(index, station_name)` tuples in the same order the
          user selected them, or  
        • `None` if *no* stations have stored failures (helper prints a
          warning and lets the caller decide how to proceed).
    """
    # pick stations that actually have failures
    candidate_stations = [
        st for st, data in fails_store.data.stations.items() if data.failures
    ]

    if not candidate_stations:
        typer.echo("⚠️  No stations have stored failures", err=True)
        return None

    try:
        return prompt_list_selection(
            items= candidate_stations,
            header= header,
            prompt= prompt,
        )
    except ValueError as e:
        typer.echo(f"ERROR: {e}", err=True)
        raise typer.Exit(1)