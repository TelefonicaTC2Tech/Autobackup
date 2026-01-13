# Stations Excel Data File Structure

This document describes the required structure for the Excel workbook used by the program. Follow this layout so your file can be properly use by the program.

## Workbook Layout

* The workbook should contain **one sheet per logical station** (e.g., `ecopetrol-test`, `ocensa-main`).
* Each sheet lists all devices (Guardians and CMC) for that station.

## Sheet Naming

* **Sheet name**: Preferably match the station code/name exactly. The program uses the sheet name as the top-level key in the generated JSON metadata.

## Sheet Columns

Each sheet must have exactly the following columns in the first (header) row:

| Column Name    | Description                                                                                 |
| -------------- | ------------------------------------------------------------------------------------------- |
| `type`         | Device type. Valid values: `GUARDIAN` or `CMC`.                                             |
| `machine_name` | Name of the device/machine. we recommend you to use unique names for every machine to avoid confusion or posible collisions.            |
| `ip_external`  | External IP address used to reach the device from outside the network.                      |
| `ip_internal`  | Internal IP address used within the network (often the same as external).                   |
| `state`        | Operational state (case insensitive). Valid values: `Instalada`, `Monitoreando`, `Aprendizaje`, `Pendiente` `Monitoreando`. If `Pendiente`, IP fields may be left empty. |


## CMC Constraint

Each sheet/page must have **one and only one** machine marked as `CMC`. All other rows should be marked as `GUARDIAN`.


## Example

**Sheet:** `ecopetrol-test`

| type     | machine\_name | ip\_external  | ip\_internal  | state        |
| -------- | ------------- | ------------- | ------------- | ------------ |
| GUARDIAN | cantagallo    | 1.2.3.4 | 1.2.3.4 | monitoreando |
| GUARDIAN | cartagena     | 9.8.7.6   | 10.20.4.1   | monitoreando |
| GUARDIAN | pozo verde     |  |  | pendiente |
| CMC      | ecopetrol-cmc | 20.160.39.1   | 100.27.256.7   | instalada |

## Tips

* **Exact headers**: Column names are case-sensitive.
* **File format**: Save the workbook as `.xlsx`.
* **Updating sheet names**: If you rename a station sheet or change any row value, rerun the command that loads the Excel data
