from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ZIP_PATH = PROJECT_ROOT / "data" / "mimic-iv-ed-demo-2.2.zip"


def load_archive_tables(zip_path: Path = ZIP_PATH) -> ZipFile:
    if not zip_path.is_file():
        raise FileNotFoundError(
            f"Dataset ZIP not found: {zip_path}. Put "
            "'mimic-iv-ed-demo-2.2.zip' in the project's data folder."
        )
    try:
        return ZipFile(zip_path)
    except BadZipFile as exc:
        raise ValueError(f"Dataset is not a valid ZIP archive: {zip_path}") from exc


def read_source_tables(archive: ZipFile) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for member in archive.namelist():
        if not member.lower().endswith(".csv.gz"):
            continue
        table_name = Path(member).name[:-7]
        if table_name in tables:
            raise ValueError(
                f"Archive contains multiple CSV files named {table_name}.csv.gz; "
                "the source table name would be ambiguous."
            )
        try:
            with archive.open(member) as compressed_file:
                tables[table_name] = pd.read_csv(
                    compressed_file,
                    compression="gzip",
                )
        except (
            BadZipFile,
            OSError,
            EOFError,
            UnicodeDecodeError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ) as exc:
            raise ValueError(f"Could not read source table {member}: {exc}") from exc
    if not tables:
        raise ValueError(f"No compressed CSV tables were found in {archive.filename}.")
    return tables
