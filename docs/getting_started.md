# Getting Started

This guide will help you prepare your environment and run the program for the first time.

## 📦 Requirements

* Python 3.11+

---

## ⚙️ Setup Instructions

1. Create a new project folder and move into it:

   ```bash
   mkdir my_project && cd my_project
   ```
2. Unzip the provided archive:

   ```bash
   unzip Narbal.zip
   ```
3. Set up your Python environment (see **Environment Setup** below).

    > **Note:** If you already have an existing virtual environment and have installed dependencies, you can skip directly to the activation commands in the **Environment Setup** section.


## Environment Setup

Follow the instructions for your operating system to create & activate a virtual environment and install dependencies.

### 🐧 Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

### 🪟 Windows (PowerShell)

```powershell
py -m venv venv
.\venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```


## 🚀 Usage

* **List commands and options:**

  ```bash
  python main.py --help
  ```

* **View general information about the program:**

  ```bash
  python main.py about
  ```


## Exiting the Virtual Environment

Once you're done using the program, exit the virtual environment by running:

```bash
deactivate
```
