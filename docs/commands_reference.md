# Commands Reference

This document lists all available top-level commands and subcommands for the program.

## List All Commands

```bash
python main.py --help
```

## Top-Level Commands and Subcommands

* `sheets`

    * `sheets load-data`

* `backup`

    * `backup run`
    * `backup retry-failures`

* `secrets`

    * `secrets generate-key`
    * `secrets generate-templates`
    * `secrets encrypt-templates`

## Viewing Command and Subcommand Options

For detailed options and descriptions for a specific command or subcommand:

```bash
# For a command:
python main.py <command> --help

# For a subcommand:
python main.py <command> <subcommand> --help
```
