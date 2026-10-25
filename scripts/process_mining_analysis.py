from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.careflow.process_mining import analyze_event_log, write_analysis


def main() -> None:
    input_path = PROJECT_ROOT / "output" / "clean_event_log.csv"
    if not input_path.is_file():
        raise FileNotFoundError(
            f"Event log not found: {input_path}. Run "
            "'python scripts/create_event_log.py' first."
        )
    event_log = pd.read_csv(input_path, dtype={"Case_ID": "string"})
    analysis = analyze_event_log(event_log)
    output_dir = PROJECT_ROOT / "output" / "process_mining"
    write_analysis(analysis, output_dir)

    summary = analysis["summary"]
    print(f"Process-mining results: {output_dir}")
    print(f"Events: {summary['total_events']}")
    print(f"ED visits: {summary['unique_ed_visits']}")
    print(f"Distinct variants: {summary['distinct_variants']}")
    print(
        "Recorded-event gap median / p90 / max (minutes): "
        f"{summary['event_gap_minutes']['median_minutes']:.1f} / "
        f"{summary['event_gap_minutes']['p90_minutes']:.1f} / "
        f"{summary['event_gap_minutes']['maximum_minutes']:.1f}"
    )
    print(summary["model_status"])


if __name__ == "__main__":
    main()
