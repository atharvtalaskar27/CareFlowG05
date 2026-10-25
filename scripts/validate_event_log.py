from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.careflow.io import load_archive_tables, read_source_tables
from src.careflow.validation import validate_event_log


def main() -> None:
    event_path = PROJECT_ROOT / "output" / "clean_event_log.csv"
    if not event_path.is_file():
        raise FileNotFoundError(
            f"Event log not found: {event_path}. Run "
            "'python scripts/create_event_log.py' first."
        )
    event_log = pd.read_csv(event_path, dtype={"Case_ID": "string"})
    with load_archive_tables() as archive:
        source_tables = read_source_tables(archive)
    validate_event_log(event_log, source_tables)
    print(
        f"Validation passed: {len(event_log)} events in "
        f"{event_log['Case_ID'].nunique()} visits."
    )
    print("Event rows reconcile exactly to source rows, timestamps, and labels.")


if __name__ == "__main__":
    main()
