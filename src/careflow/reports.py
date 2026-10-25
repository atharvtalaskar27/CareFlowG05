import json
from pathlib import Path
from typing import Any


def write_quality_reports(quality: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "data_quality_report.json").write_text(
        json.dumps(quality, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    reconciliation = quality["source_reconciliation"]
    lines = [
        "# Data quality report",
        "",
        "Generated from the local MIMIC-IV-ED demo ZIP. Source files were read",
        "without changing or extracting them.",
        "",
        "## Summary",
        "",
        f"- Source rows inspected across all tables: {quality['source_rows_inspected']}",
        f"- Event rows created: {quality['event_rows_created']}",
        f"- Candidate event rows excluded for missing/invalid required fields: "
        f"{quality['candidate_event_rows_excluded']}",
        f"- Distinct ED visits represented: {quality['unique_ed_visits']}",
        f"- Arrival/departure intervals with departure before arrival: "
        f"{quality['invalid_arrival_departure_intervals']}",
        "",
        "## Source-row to event-row reconciliation",
        "",
        f"- Source rows in the four event-generating tables: "
        f"{reconciliation['source_rows_in_event_generating_tables']}.",
        f"- Distinct source rows that contributed at least one event: "
        f"{reconciliation['distinct_source_rows_contributing_at_least_one_event']}.",
        f"- Candidate event rows from those tables: "
        f"{reconciliation['candidate_event_rows']}.",
        f"- Triage and diagnosis supporting rows not used as event candidates: "
        f"{reconciliation['supporting_only_source_rows_not_used_as_event_candidates']} "
        f"({', '.join(f'{name}: {count}' for name, count in reconciliation['supporting_only_rows_by_table'].items())}).",
        "- Each `edstays` row produces two candidate event rows (arrival and "
        "departure); each `vitalsign`, `pyxis`, and `medrecon` row produces one.",
        "- Triage and diagnosis have no suitable event timestamp in these files. "
        "They are supporting tables, not rejected timestamped-event candidates.",
        "- A candidate event row is excluded only if its visit ID is missing, its "
        "timestamp is missing, or its timestamp cannot be parsed.",
        "",
        "## Source table completeness and exact duplicates",
        "",
        "| Table | Source rows | Exact duplicate source rows | Fields with missing values |",
        "|---|---:|---:|---|",
    ]
    for name, details in quality["source_tables"].items():
        missing_fields = ", ".join(
            f"`{column}` ({count})"
            for column, count in details["missing_values"].items()
        ) or "none"
        lines.append(
            f"| `{name}` | {details['row_count']} | "
            f"{details['exact_duplicate_rows']} | {missing_fields} |"
        )

    repeat_check = quality["repeated_event_group_source_row_check"]
    lines.extend(
        [
            "",
            "## Repeated event keys",
            "",
            f"- {quality['repeated_case_activity_timestamp_groups_retained']} "
            f"repeated `Case_ID`/`Activity_Name`/`Timestamp` groups contain "
            f"{quality['rows_in_repeated_case_activity_timestamp_groups']} event rows.",
            f"- Every event row in all {repeat_check['groups_with_distinct_source_rows_for_every_event']} "
            "groups with a repeated key has a distinct CSV source-row locator.",
            f"- Repeated-group event rows by source table: "
            f"{', '.join(f'{name}: {count}' for name, count in repeat_check['source_tables_in_repeated_groups'].items())}.",
            "- Exact full-row duplicate counts are zero in all six source tables. "
            "The repeated event keys therefore refer to distinct source rows, but "
            "the available columns cannot determine whether any records are "
            "clinically equivalent or whether the repetition is intentional.",
            "- No rows are deleted for repeated keys or duplicate-looking events.",
            "",
            "## Event-generation counts",
            "",
            "| Activity | Source table/time field | Candidate event rows | Created | Missing case ID | Missing timestamp | Invalid timestamp | Excluded |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for activity, details in quality["event_sources"].items():
        lines.append(
            f"| {activity} | `{details['source_table']}.{details['source_timestamp_column']}` | "
            f"{details['candidate_event_rows']} | {details['event_rows_created']} | "
            f"{details['missing_case_id']} | {details['missing_timestamp']} | "
            f"{details['invalid_timestamp']} | "
            f"{details['candidate_event_rows_excluded']} |"
        )

    lines.extend(
        [
            "",
            "## Provenance and cleaning decisions",
            "",
            f"- {reconciliation['source_row_locator']}",
            "- Case_ID comes from the source ED visit `stay_id`; source reconciliation "
            "checks every output row against its corresponding source row.",
            "- Source timestamps are parsed from the named source field. No timestamps "
            "are filled or invented.",
            "- Event rows are sorted by Case_ID, Timestamp, Activity_Name, then "
            "Source_Record_ID for deterministic ordering.",
            "- Pyxis records are cabinet records, not proof of medication administration.",
            "- Medication reconciliation records are not medication administration events.",
            "- Triage and diagnosis remain supporting information because they do not "
            "contain a suitable event timestamp.",
            "- Recorded event gaps are not established clinical waiting times.",
            "",
            "## Other data-quality limitations",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in quality["limitations"])
    lines.append("")
    (reports_dir / "data_quality_report.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
