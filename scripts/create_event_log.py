from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.careflow.io import load_archive_tables, read_source_tables
from src.careflow.transformations import build_event_log
from src.careflow.validation import validate_event_log
from src.careflow.reports import write_quality_reports


def main() -> None:
    with load_archive_tables() as archive:
        tables = read_source_tables(archive)
    event_log, quality = build_event_log(tables)
    validate_event_log(event_log, tables)

    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "clean_event_log.csv"
    event_log.to_csv(output_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    write_quality_reports(quality, PROJECT_ROOT / "reports")

    reconciliation = quality["source_reconciliation"]
    print(f"Event log created: {output_path}")
    print(f"Source rows inspected: {quality['source_rows_inspected']}")
    print(
        "Source rows in event-generating tables: "
        f"{reconciliation['source_rows_in_event_generating_tables']}"
    )
    print(
        "Supporting-only rows not used as event candidates: "
        f"{reconciliation['supporting_only_source_rows_not_used_as_event_candidates']}"
    )
    print(f"Candidate event rows: {reconciliation['candidate_event_rows']}")
    print(f"Event rows created: {quality['event_rows_created']}")
    print(
        "Candidate event rows excluded: "
        f"{quality['candidate_event_rows_excluded']}"
    )
    print(f"Unique ED visits: {quality['unique_ed_visits']}")
    print(f"Quality reports: {PROJECT_ROOT / 'reports'}")
    print("\nActivity counts:")
    for activity, count in quality["activity_counts"].items():
        print(f"  {activity}: {count}")


if __name__ == "__main__":
    main()
