# [EN FASE DE DESARROLLO]

# 🌀 NARBAL (Nozomi Automated Recursive Backups And Load-down)

NARBAL automates the end-to-end process of generating station metadata, managing SSH credentials, and performing recursive backups of Nozomi Guardian devices via a CMC jump host. By defining station configurations in an Excel workbook and securely storing device secrets, you can orchestrate backups across multiple sites with built-in retry logic.


## 📖 Documentation

All user-facing guides and references live in the `docs/` folder:

* **[Getting Started](docs/getting_started.md)** — Install, unzip, and initialize your environment
* **[Stations Excel Schema](docs/stations_excel_schema.md)** — Excel workbook layout & required headers
* **[Data Directory Structure](docs/data_dir_structure.md)** — Layout of the `data/` directory and naming conventions
* **[Usage Guide](docs/usage_guide.md)** — Detailed workflows, prompts, and examples
* **[Commands Reference](docs/commands_reference.md)** — List of all commands and subcommands


## 📄 License

This tool is intended for internal use by Telefónica Tech
