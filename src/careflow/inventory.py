from pathlib import Path
from typing import Any

import pandas as pd

from src.careflow.transformations import EVENT_SOURCES

EVENT_TIMESTAMP_COLUMNS = {
    "edstays": ["intime", "outtime"],
    "vitalsign": ["charttime"],
    "pyxis": ["charttime"],
    "medrecon": ["charttime"],
}
EVENT_LOG_SUITABILITY = {
    "edstays": "Timestamped visit-boundary events: arrival and departure.",
    "vitalsign": "Timestamped observation-record events, not a full clinical action log.",
    "pyxis": "Timestamped medication-cabinet record; does not confirm administration.",
    "medrecon": "Timestamped medication reconciliation entry; not administration.",
    "triage": "Supporting visit context; no event timestamp is present.",
    "diagnosis": "Supporting visit context; no event timestamp is present.",
}


def create_inventory(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    stay_ids = set()
    if "edstays" in tables and "stay_id" in tables["edstays"]:
        stay_ids = set(tables["edstays"]["stay_id"].dropna().astype(str))

    event_table_names = set(EVENT_SOURCES)
    event_source_rows = sum(
        len(tables[name]) for name in event_table_names if name in tables
    )
    candidate_event_rows = sum(
        len(tables[name]) * len(spec["events"])
        for name, spec in EVENT_SOURCES.items()
        if name in tables
    )
    supporting_rows = {
        name: int(len(frame))
        for name, frame in tables.items()
        if name not in event_table_names
    }
    result: dict[str, Any] = {
        "total_source_rows": int(sum(len(frame) for frame in tables.values())),
        "event_source_rows": int(event_source_rows),
        "candidate_event_rows": int(candidate_event_rows),
        "supporting_only_rows": supporting_rows,
        "tables": {},
    }
    for name, frame in tables.items():
        identifier_roles = {
            column: role
            for column, role in {
                "stay_id": "ED visit identifier",
                "hadm_id": "hospital admission identifier",
                "subject_id": "person-level identifier",
            }.items()
            if column in frame.columns
        }
        relationships = {}
        if stay_ids and "stay_id" in frame.columns:
            ids = frame["stay_id"].dropna().astype(str)
            relationships["stay_id_matching_edstays"] = int(ids.isin(stay_ids).sum())
            relationships["stay_id_not_matching_edstays"] = int((~ids.isin(stay_ids)).sum())

        timestamp_stats = {}
        for column in EVENT_TIMESTAMP_COLUMNS.get(name, []):
            if column not in frame.columns:
                continue
            parsed = pd.to_datetime(
                frame[column],
                format="mixed",
                errors="coerce",
            )
            timestamp_stats[column] = {
                "valid": int(parsed.notna().sum()),
                "missing": int(frame[column].isna().sum()),
                "invalid_non_missing": int((frame[column].notna() & parsed.isna()).sum()),
                "earliest": None if parsed.notna().sum() == 0 else str(parsed.min()),
                "latest": None if parsed.notna().sum() == 0 else str(parsed.max()),
            }
        result["tables"][name] = {
            "row_count": int(len(frame)),
            "columns": [
                {"name": str(column), "dtype": str(dtype)}
                for column, dtype in frame.dtypes.items()
            ],
            "missing_values": {
                str(column): int(count)
                for column, count in frame.isna().sum().items()
                if count
            },
            "exact_duplicate_rows": int(frame.duplicated().sum()),
            "identifier_roles": identifier_roles,
            "timestamp_columns": timestamp_stats,
            "relationships": relationships,
            "event_log_suitability": EVENT_LOG_SUITABILITY.get(
                name,
                "Supporting information; inspect its meaning before creating events.",
            ),
        }
    return result


def write_inventory(inventory: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Source data inventory",
        "",
        "## Archive overview",
        "",
        "The local ZIP contains gzip-compressed CSV tables. The archive itself is",
        "read in place; no files are extracted or modified. No separate data",
        "documentation file was present in the archive beyond its license and",
        "checksum manifest.",
        "",
        "Tables are related through `stay_id` where present. `subject_id` is a",
        "person-level identifier and is intentionally not exported to the event log.",
        "",
        f"Total rows across inspected tables: {inventory['total_source_rows']}. "
        f"Rows in event-generating tables: {inventory['event_source_rows']}; "
        f"candidate event rows based on the pipeline mapping: "
        f"{inventory['candidate_event_rows']}.",
        f"Supporting-only rows without timestamped event generation: "
        f"{sum(inventory['supporting_only_rows'].values())} "
        f"({', '.join(f'{name}: {count}' for name, count in inventory['supporting_only_rows'].items())}).",
        "One ED stay source row maps to two event candidates (arrival and departure); "
        "each vitalsign, pyxis, and medrecon row maps to one.",
        "",
    ]
    for name, details in inventory["tables"].items():
        lines.extend(
            [
                f"## `{name}.csv.gz`",
                "",
                f"- Rows: {details['row_count']}",
                f"- Exact duplicate rows: {details['exact_duplicate_rows']}",
                f"- Identifiers and roles: "
                f"{', '.join(f'`{column}` ({role})' for column, role in details['identifier_roles'].items()) or 'none'}",
                f"- Event-log suitability: {details['event_log_suitability']}",
                "",
                "| Column | Inferred type | Missing values |",
                "|---|---|---:|",
            ]
        )
        missing = details["missing_values"]
        for column in details["columns"]:
            lines.append(
                f"| `{column['name']}` | {column['dtype']} | "
                f"{missing.get(column['name'], 0)} |"
            )
        lines.extend(["", "### Timestamp ranges", ""])
        if not details["timestamp_columns"]:
            lines.append("No candidate event timestamp columns were identified.")
        else:
            lines.extend(
                [
                    "| Column | Valid | Missing | Invalid non-missing | Earliest | Latest |",
                    "|---|---:|---:|---:|---|---|",
                ]
            )
            for column, stats in details["timestamp_columns"].items():
                lines.append(
                    f"| `{column}` | {stats['valid']} | {stats['missing']} | "
                    f"{stats['invalid_non_missing']} | {stats['earliest'] or 'N/A'} | "
                    f"{stats['latest'] or 'N/A'} |"
                )
        if details["relationships"]:
            rel = details["relationships"]
            lines.extend(
                [
                    "",
                    f"Rows with a `stay_id` matching `edstays`: "
                    f"{rel['stay_id_matching_edstays']}; non-matching non-null "
                    f"`stay_id` rows: {rel['stay_id_not_matching_edstays']}.",
                ]
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
