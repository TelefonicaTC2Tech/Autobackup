# Usage Guide

This guide explains how to run the main workflows of the program after you’ve completed the initial setup.


## Before You Begin

1. Follow the [Getting Started guide](./getting_started.md) if you haven’t already—**do not** deactivate your environment afterward.
2. Create your Excel file according to the [Stations Excel schema](./stations_excel_schema.md).
3. (**Optinal**) Refer to the [Commands Reference](./commands_reference.md) for a full list of commands and subcommands.

Next, create a `.env` file at the root of your project directory with the following variable:

```env
STATION_MACHINES_DATA_SHEET=/full/path/to/your/stations-excel-file.xlsx
```

### Optional: Generate Fernet Key
If you don't already have a Fernet key, generate one now:

```bash
python main.py secrets generate-key
```

This command outputs a Fernet key, **save and store it securely**, as you'll need it to encrypt and decrypt files.


## Interective Selection prompts

### Numbered menu

When the program asks you to choose from a numbered menu, it presents a numbered list and waits for your input.

Examples:

```bash
Available Stations:
  1. ecopetrol-test
  2. cenit-test
Select stations by numbers (e.g. 1,3-5): 2
```

```bash
Available secrets templates:
  1. data/stations_secrets/templates/station-A_secrets.json
  2. data/stations_secrets/templates/station-B_secrets.json
  3. data/stations_secrets/templates/station-C_secrets.json
  4. data/stations_secrets/templates/station-D_secrets.json
Select station tamplates by numbers (e.g. 1,3-5): 1,4
```

You can select one or more items by specifying numbers or ranges, separated by commas. For example:

* `1` (only station 1)
* `1,3` (stations 1 and 3)
* `3-6` (stations 3 through 6)
* `1,4-7,13` (stations 1, 4, 5, 6, 7, and 13)



## Main Workflow

At this point you should alredy had set up you enviroment and creted you sations data Excel file and your `.env` file.

### 1. Load Station Data

Import station sheets from your Excel file into JSON metadata:

```bash
python main.py sheets load-data
```

The genreated metadata files can be found in `data/stations_metadata/`


### 2. Generate Secret Templates

Create secrets templates for the selected stations:

```bash
python main.py secrets generate-templates
```

Once the command runs, you will see a numbered menu of stations. Select the stations you want (see [numbered-menu](#numbered-menu)) to generate templates for.

After you selected the stations, the template files for the stations are going to be creted. The templates can be found in `data/stations_secrets/templates/`.

Now, go and open a template, you should see somthing liek this:

```json
{
  "<STATION_NAME>": {
    "<external_ip_of_machine_1>": "",
    "<external_ip_of_machine_2>": "",
    "<external_ip_of_machine_3>": "",
    …
  }
}
```

Fill in each machine’s SSH password in place of the empty strings and save the file.

```json
{
  "<STATION_NAME>": {
    "<external_ip_of_machine_1>": "password-1",
    "<external_ip_of_machine_2>": "password-2",
    "<external_ip_of_machine_3>": "password-3",
    …
  }
}
```


### 3. Encrypt Secret Templates

Encrypt your filled templates to secure them.

```bash
python main.py secrets encrypt-templates
```

* **Prompts:**

  1. You will be ask to enter your Fernet key. 
  **The same key should be use to encrypt all the templates** (key is used for both encryption and decryption).

  2. After entering the key, a numbered menu of template files appears. Select ones you want (see [numbered-menu](#numbered-menu)).

* **Output:** Encrypted files appear in `data/stations_secrets/encrypted/`.
* **Cleanup:** The selected plain-text templates are deleted automatically after encryption.


### 4. Run Backups

Perform backups for selected stations and machines.

```bash
python main.py backup run
```

When you run this command:

1. You'll be prompted to enter your Fernet key to decrypt the station secrets (the key you used to encrypt you templates).

2. A numbered list of stations is display, select the sations you want to perform backups for (see [numbered-menu](#numbered-menu)).

3. Unless you used the `--yes` flag, the program will ask if you want to back up all machines for each station. If you answer **no**, it will display another menu so you can pick individual machines.

    > **Note:**
    > To view options/flags and their default values:
    > ```bash
    > python main.py backup run --help
    > ```


During execution, status lines show progress:

```bash
Backups for CENIT:
1. ❌ alban(1.1.1.1): TargetSSHConnectionError  0:00:40
2. ✅ pozo-azul(2.2.2.2): Backup successfully copied  0:01:09
3. ⠏ laguna-verde(3.3.3.3): Processing...  0:00:07
```

***Output:*** `.nozomi_backup` files in `data/nozomi_backups/<station_name>/`


## 5. Re-try Failed Backups (Optional)

This command works very similarly to the `backup run` command.

> **Note:**
> This will retry only the backups that failed during the last execution of `backup run` or `backup retry-failures`.

If any backups failed previously, re-attempt them with:

```bash
python main.py backup retry-failures
```

When you run this command:

1. The program reads `data/backup_failures/backup_failures.json` to identify failed backups.

2. It displays a numbered menu of stations with recorded failures (see [numbered-menu](#numbered-menu)).

3. After selecting stations, you'll be prompted for your Fernet key to decrypt secrets.

4. Next, you'll be asked if you want to retry **all** failed machines for each station.

   * If you answer **no**, a numbered menu of the machines that previously failed is shown so you can select specific machines to retry.
   * Use the `--yes` flag to skip all prompts and retry every failure automatically.


***Output:*** New `.nozomi_backup` files in `data/nozomi_backups/<station_name>/`.

