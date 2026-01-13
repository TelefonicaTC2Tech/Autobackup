import typer
from pathlib import Path
import pyfiglet

from rich import box
from rich.console import Console, Group
from rich.columns import Columns
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich.panel import Panel

from settings import VERSION, DEFAULT_CLI_NAME


def welcome_banner() -> None:
    welcome = f"***** WELCOME TO {DEFAULT_CLI_NAME.upper()}!!! *****"
    typer.echo(welcome)
    typer.echo("Nozomi Automated Recursive Backups And Load-down")
    typer.echo("*" * len(welcome))


def display_general_info_banner() -> None:
    """
    Load your ANSI-colored logo from disk and render it
    side-by-side with porgram info.
    """
    console = Console()

    # adjust this path if you rename 'static' → 'ascii_art' or similar
    logo_path = Path(__file__).parent 
    logo_path = logo_path.joinpath("ascii_art", "telefonica_logo.txt")
    logo = logo_path.read_text(encoding="utf-8")

    program_name_tittle = Align.center(
        Text.from_ansi(pyfiglet.figlet_format("Narbal", font="standard")),
        # vertical="top",
    )

    blue_letter = "[bold cyan]{}[/]"
    acronim = " ".join([
        f"{blue_letter.format('N')}ozomi",
        f"{blue_letter.format('A')}utomated",
        f"{blue_letter.format('R')}ecursive",
        f"{blue_letter.format('B')}ackups",
        f"{blue_letter.format('A')}nd",
        f"{blue_letter.format('L')}oad-down",
    ])
    name_acronim = Align.center(
        Text.from_markup(acronim),
        # vertical="top",
    )

    row_format = "[bold dodger_blue2]{key}:[/] [bold bright_white]{value}[/]"
    # build the info panel
    info = Table.grid(padding=1)
    info.add_column(justify="center", style="bold dodger_blue2", max_width=50)
    info.add_row(row_format.format(key="Created by", value="Colombia SOC-OT Development Team"))
    info.add_row(row_format.format(key="Version", value=VERSION))
    info.add_row(row_format.format(key="License", value="Only for internal use of Telefonica Tech"))
    info.add_row(row_format.format(
        key="Description",
        value="Automates generating, retrieving, and archiving Nozomi Guardian backups."
        )
    )
    info.add_row("For feature requests or bug reports, contact the Colombia SOC-OT team.")


    info_panel = Panel(
        # Group(program_name_tittle, info),
        Align(info, align="left", vertical="middle"),
        box= box.SQUARE, # box style: SQUARE, ROUNDED, DOUBLE, etc.
        border_style="cyan", # line color
        padding=(0, 1), # (top & bottom, left & right)
    )

    right_column = Group(program_name_tittle, name_acronim, info_panel)

    # print them side by side
    console.print(
        Columns(
            [
                Text.from_ansi(logo),
                right_column
                # Align(info_panel, align="left", vertical="middle"),
            ],
            expand=False
        )
    )


