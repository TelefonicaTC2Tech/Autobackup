from cli.app import app
from data_dirs import ensure_data_dirs


def main():
    ensure_data_dirs()
    app()


if __name__ == "__main__":
    main()