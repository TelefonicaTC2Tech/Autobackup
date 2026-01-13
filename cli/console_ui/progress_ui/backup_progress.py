import os
import typer
from typing import NamedTuple
from rich.progress import (
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TaskID
)

from settings import (
    BACKUPS_DESTINATION_DIRECTORY,
)
from features.backups.runner import BackupResult, BackupsRunner
from features.stations.exceptions import MachinePasswordMissingError

from .columns import SpinnerCheckXColumn


class BackupSummary(NamedTuple):
    successes: list[tuple[str, str, str]]
    failures:  list[tuple[str, str, str]]


class BackupsProgress:
    def __init__(self, backups_runner: BackupsRunner, station_name: str, verbose: bool) -> None:
        self.backups_runner = backups_runner
        self.station_name = station_name
        self.verbose = verbose
        self.prog = Progress(
            TextColumn("{task.fields[num_position]}."),
            SpinnerCheckXColumn(finished_text="✅"),
            TextColumn("[progress.description]{task.fields[machine_name]}({task.fields[machine_ext_ip]}):"),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            transient=False,
            disable=verbose,
        )

        self.failures: list[tuple[str, str, str]] = [] # [(machine_name, machine_ip, error_message)]
        self.successes: list[tuple[str, str, str]] = []  # [(machine_name, machine_ip, success_message)]

    def _fail_task(self, task_id: TaskID, description: str) -> None:
        self.prog.update(
            task_id= task_id,
            description= description,
            total= 100,
            completed= 100,
            error_happened= True,
        )
        self.prog.stop_task(task_id)

        t = self.prog.tasks[task_id]
        self.failures.append((t.fields['machine_name'], t.fields['machine_ext_ip'], description))

    def _succeed_task(self, task_id: TaskID, description: str) -> None:
        self.prog.update(
            task_id= task_id,
            description= description,
            total= 100,
            completed= 100,
            error_happened= False,
        )
        self.prog.stop_task(task_id= task_id)

        t = self.prog.tasks[task_id]
        self.successes.append((t.fields['machine_name'], t.fields['machine_ext_ip'], description))

    def _handle_backup_result(self, task_id: TaskID, backup_result: BackupResult) -> bool:
        if not backup_result.execution_result.success:
            result_error = backup_result.execution_result.error
            error_msg = str(result_error)
            if len(error_msg) > 70:
                error_msg = type(result_error).__name__

            self._fail_task(task_id= task_id, description= error_msg)
            return False
        
        if not backup_result.remote_backup_filepath:
            msg= "No backup filepath could be found, file transfer CAN NOT be done."
            self._fail_task(task_id= task_id, description= msg)          
            return False
        
        return True
        
    def _handle_file_copy(self, task_id: TaskID, backup_result: BackupResult, station_backups_dir: str) -> bool:
        # Prefer internal_host; fall back to public SSH host if the internal is unset
        ssh_host = backup_result.gateway.internal_host or backup_result.gateway.host

        self.prog.update(
            task_id= task_id,
            description= "copying backup file from the CMC to local machine... ",            
        )

        remote_filepath = backup_result.remote_backup_filepath
        if not remote_filepath:
            # the handle_backup_result method should be call befote this method
            raise ValueError(
                "Internal bug: _handle_file_copy called with a missing remote backup filepath"
            )

        cp_result = self.backups_runner.copy_remote_file_to_local_machine(
            remote_filepath= remote_filepath,
            local_destination= station_backups_dir,
            ssh_host= ssh_host,
            ssh_user= backup_result.gateway.user,
            ssh_password= backup_result.gateway.password.get_secret_value(),
        )

        if not cp_result.success:
            self._fail_task(task_id= task_id, description= f"{cp_result.error}")
            return False
        
        return True

    def run(self) -> BackupSummary:
        """
        Executes the progress bar over all targets,
        then returns (successes, failures), each a list of
        (station_name, ip_external, message) tuples.
        """
        target_machines = self.backups_runner.get_target_machines()
        backups_iterator = self.backups_runner.backup_generator()

        station_backups_dir = os.path.join(BACKUPS_DESTINATION_DIRECTORY, self.station_name, "")
        os.makedirs(name= station_backups_dir, exist_ok=True)

        with self.prog:
            for idx, machine_data in enumerate(target_machines, start=1):
                machine_name = machine_data["machine_name"]
                machine_ext_ip = machine_data["ip_external"]

                task_id = self.prog.add_task(
                    description= "Processing... ",
                    total= None,
                    num_position= idx,
                    machine_name= machine_name,
                    machine_ext_ip = machine_ext_ip,
                )

                if self.verbose:
                    typer.echo(f"\n##{'*'*10}  Backup {machine_name}({machine_ext_ip})  {'*'*10}##\n")

                try:
                    backup_result = next(backups_iterator)
                except MachinePasswordMissingError as e:
                    self.prog.stop_task(task_id= task_id)
                    self.prog.remove_task(task_id= task_id)
                    self.prog.stop()
                    typer.echo(f"ERROR: {e}", err=True)
                    
                    raise typer.Exit(1)
                
                except StopIteration:
                    # This exception in theory should never be reach, since the for loop
                    # goes over all the target machines we should be try to connect to
                    # if this exception is raise then a mismach happened(internal bug)
                    self._fail_task(task_id= task_id, description= "Backup generator ended early.")
                    # self.prog.remove_task(task_id= task_id)
                    break

                succeed = self._handle_backup_result(task_id= task_id, backup_result= backup_result)
                if not succeed:
                    continue

                cp_succeed = self._handle_file_copy(
                    task_id= task_id,
                    backup_result= backup_result,
                    station_backups_dir= station_backups_dir
                )
                if not cp_succeed:
                    continue

                msg = "Backup file succesfully copied from the CMC"
                self._succeed_task(task_id= task_id, description= msg)


        return BackupSummary(successes=self.successes, failures=self.failures)