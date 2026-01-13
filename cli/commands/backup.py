import typer
from pydantic import ValidationError

from features.stations.repository import StationDataRepository
from features.stations.secrets_handler import StationSecretsHandler
from features.backups.runner import BackupsRunner
from features.backups.failures_store import FailuresStore, BackupFailureRecord

from cli.console_ui import (
    banners,
    checksum_validation,
    menus,
    secrets_ui,
    usage_hints,
)
from cli.console_ui.progress_ui.backup_progress import BackupsProgress


backup_app = typer.Typer()


@backup_app.command("run")
def backup_run(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    backup_script_timeout: int = typer.Option(
        180,
        "--backup-script-timeout",
        help="Maximum seconds to let the backup script run on the target "
             "(default: 180 s ≈ 3 min).",
        show_default=False,
    ),
    connection_timeout: int = typer.Option(
        60,
        "--connection-timeout",
        help="SSH connection timeout in seconds (default: 60 s).",
        show_default=False,
    ),
    shell_prompt_timeout: int = typer.Option(
        90,
        "--shell-prompt-timeout",
        help="How long to wait for each shell prompt in seconds "
             "(default: 90 s).",
        show_default=False,
    ),
    yes_all: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically back up all Guardian machines; skips any confirmation or selection.",
    ),
    machines: list[str] = typer.Option(
        None,
        "--machine",
        "-m",
        help="External IP(s) of machine(s) to back up; if omitted you will be prompted (unless -y is set)",
    ),
) -> None:
    """
    Run the backup process for all configured targets.
    """
    banners.welcome_banner()
    
    key = secrets_ui.prompt_and_validate_fernet_key()

    fails_store = FailuresStore()
    try:
        fails_store.load()
    except ValidationError as e:
        typer.echo(f"ERROR: {e}", err= True)
        raise typer.Exit(1)
    except FileNotFoundError:
        pass
    
    station_secrets_handler = StationSecretsHandler(key= key)

    try:
        stations_repo = StationDataRepository()
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(1)

    checksum_validation.stations_json_data_files_integrity_check(stations_repo= stations_repo)
    checksum_validation.xls_data_file_integrity_check()

    typer.echo()
    selected_stations = menus.display_avalible_stations_menu(
        stations_data_repo= stations_repo,
    )

    for _, station_name in selected_stations:
        station_data = stations_repo.get_station_data(station_name= station_name)
        
        _run_station_backup(
            station_name= station_name,
            station_data= station_data,
            station_secrets_handler = station_secrets_handler,
            stations_repo = stations_repo,
            fails_store = fails_store,
            machines = machines,
            yes_all = yes_all,
            backup_all_confirmation_prompt_msg = f"Back up ALL Guardian machines in {station_name}?",
            section_title = "Backups",
            backup_script_timeout = backup_script_timeout,
            connection_timeout = connection_timeout,
            shell_prompt_timeout = shell_prompt_timeout,
            verbose = verbose,
        )
        

@backup_app.command("retry-failures")
def backup_retry_failures(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    backup_script_timeout: int = typer.Option(
        180,
        "--backup-script-timeout",
        help="Maximum seconds to let the backup script run on the target "
             "(default: 180 s ≈ 3 min).",
        show_default=False,
    ),
    connection_timeout: int = typer.Option(
        60,
        "--connection-timeout",
        help="SSH connection timeout in seconds (default: 60 s).",
        show_default=False,
    ),
    shell_prompt_timeout: int = typer.Option(
        90,
        "--shell-prompt-timeout",
        help="How long to wait for each shell prompt in seconds "
             "(default: 90 s).",
        show_default=False,
    ),
    yes_all: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Automatically Re-Try to back up all the previous fail backups; skips any confirmation or selection.",
    ),
    machines: list[str] = typer.Option(
        None,
        "--machine",
        "-m",
        help="External IP(s) of machine(s) to back up; if omitted you will be prompted (unless -y is set)",
    ),
) -> None:
    """
    Re-run backups **only** for machines that failed in the last run.
    """
    banners.welcome_banner()

    fails_store = FailuresStore()
    try:
        fails_store.load()
    except ValidationError as e:
        typer.echo(f"ERROR: {e}", err= True)
        raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("No failure log file found, nothing to retry.")
        raise typer.Exit()

    selected_stations = menus.display_stations_with_failed_backups_menu(
        fails_store= fails_store,
    )
    if selected_stations is None:
        raise typer.Exit(0)
    
    key = secrets_ui.prompt_and_validate_fernet_key()
    station_secrets_handler = StationSecretsHandler(key= key)

    try:
        stations_repo = StationDataRepository()
    except FileNotFoundError as e:
        typer.echo(f"ERROR: {e}", err=True)
        usage_hints.hint_load_data_from_excel()
        raise typer.Exit(1)

    checksum_validation.stations_json_data_files_integrity_check(stations_repo= stations_repo)
    checksum_validation.xls_data_file_integrity_check()
    
    for _, station_name in selected_stations:
        # build index of GUARDIANs by external IP
        ext_ip_index = stations_repo.build_station_index(
            station_name, by="ip_external", skip_missing=True
        )
        station_data = []      
        failed_ips = [str(d.ip) for d in fails_store.data.stations[station_name].failures]

        for m_ip, m_data in ext_ip_index.items():
            if m_data["type"] == "CMC":
                station_data.append(m_data)
                continue
            if m_ip in failed_ips:
                station_data.append(m_data)

        _run_station_backup(
            station_name= station_name,
            station_data= station_data,
            station_secrets_handler = station_secrets_handler,
            stations_repo = stations_repo,
            fails_store = fails_store,
            machines = machines,
            yes_all = yes_all,
            backup_all_confirmation_prompt_msg = "Re-try ALL backups for previously failed machines?",
            section_title = "Backup retries",
            backup_script_timeout = backup_script_timeout,
            connection_timeout = connection_timeout,
            shell_prompt_timeout = shell_prompt_timeout,
            verbose = verbose,
        )


def _prepare_station_data_for_runner(
        station_data: list[dict],
        station_name: str,
        machines: list[str] | None,
        yes_all: bool,
        stations_repo: StationDataRepository,
        confrimation_prmpt: str = "Backup all machines?",
    ) -> list[dict]:
    """
    Given full station_data and optional --machine flags or --yes,
    return the exact list to feed into BackupsRunner:
      - --yes:           station_data unchanged (CMC + all guardians)
      - flags:           [CMC] + only those IPs
      - menu-subset:     [CMC] + the user-picked subset
    """
    # If they passed -y/--yes, skip everything and back up all machines:
    if yes_all:
        return station_data
    
    # isolate the single CMC
    try:
        cmc = next(m for m in station_data if m["type"] == "CMC")
    except StopIteration:
        typer.echo(f"ERROR: no CMC entry in data for station {station_name}", err=True)
        raise typer.Exit(1)

    # build index of GUARDIANs by external IP
    ext_ip_index = stations_repo.build_station_index(
        station_name, by="ip_external", skip_missing=True
    )

    # cli flag-based selection
    if machines: 
        try:
            cmc_ext_ip = cmc["ip_external"]
            guardians = [
                ext_ip_index[ip] 
                for ip in machines
                if ip != cmc_ext_ip
            ]    
            return [cmc] + guardians
        
        except KeyError as e:
            typer.echo(f"ERROR: unknown machine IP {e.args[0]}", err=True)
            raise typer.Exit(1)

    # interactive fallback
    backup_all_machines = typer.confirm(confrimation_prmpt, abort=False)
    if backup_all_machines:
        # user wants everything: just return station_data unchanged
        return station_data
    
    # User wants to choose just a sub-set of machines from the station
    selected = menus.display_available_machines_menu(
        station_data= station_data,
        header= f"Available machines in {station_name}:",
    )
    ips = [ip for _, _, ip in selected]
    guardians = [ext_ip_index[ip] for ip in ips]

    return [cmc] + guardians


def _run_station_backup(
        station_name: str,
        station_data: list[dict],
        station_secrets_handler: StationSecretsHandler,
        stations_repo: StationDataRepository,
        fails_store: FailuresStore,
        machines: list[str] | None,
        yes_all: bool,
        backup_all_confirmation_prompt_msg: str,
        section_title: str,
        backup_script_timeout: int,
        connection_timeout: int,
        shell_prompt_timeout: int,
        verbose: bool,
    ) -> None:
    """Common code used by both *run* and *retry-failures* commands."""
    station_secrets = secrets_ui.load_station_secrets_or_exit(
        secrets_handler= station_secrets_handler,
        station_name= station_name
    )

    runner_stations_data = _prepare_station_data_for_runner(
        station_data=station_data,
        station_name=station_name,
        machines=machines,
        yes_all=yes_all,
        stations_repo=stations_repo,
        confrimation_prmpt= backup_all_confirmation_prompt_msg,
    )

    if verbose:
        typer.echo(f"\n{'#'*10}  {section_title} for {station_name}  {'#'*10}\n")
    else:
        typer.echo(f"\n{section_title} for {station_name}:")

    runner = BackupsRunner(
        station_data= runner_stations_data,
        station_secrets= station_secrets,
        script_timeout= backup_script_timeout,
        connection_timeout= connection_timeout,
        shell_prompt_timeout= shell_prompt_timeout,
        verbose= verbose,
    )

    summary = BackupsProgress(runner, station_name, verbose).run()

    # clear any old ones        
    fails_store.clear_station(station_name)
    # Update failure store
    for m_name, ext_ip, err_msg in summary.failures:
        fails_store.add_failure(
            station_name,
            BackupFailureRecord(machine=m_name, ip=ext_ip, error=err_msg),  # type: ignore[arg-type]
        )

    fails_store.save()
