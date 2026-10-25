from typing import Any

import pandas as pd

EVENT_COLUMNS = [
    "Case_ID",
    "Activity_Name",
    "Timestamp",
    "Source_Table",
    "Source_Record_ID",
    "Event_Type",
]

EVENT_SOURCES = {
    "edstays": {
        "case_column": "stay_id",
        "events": [
            ("intime", "ED Arrival", "stay_boundary"),
            ("outtime", "ED Departure", "stay_boundary"),
        ],
    },
    "vitalsign": {
        "case_column": "stay_id",
        "events": [("charttime", "Vitals Recorded", "clinical_observation")],
    },
    "pyxis": {
        "case_column": "stay_id",
        "events": [
            (
                "charttime",
                "Pyxis Medication Record",
                "medication_cabinet_record",
            )
        ],
    },
    "medrecon": {
        "case_column": "stay_id",
        "events": [
            (
                "charttime",
                "Medication Reconciliation Recorded",
                "medication_reconciliation_record",
            )
        ],
    },
}


def _source_event_rows(
    table_name: str,
    frame: pd.DataFrame,
    case_column: str,
    time_column: str,
    activity: str,
    event_type: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    required = [case_column, time_column]
    missing_columns = [column for column in required if column not in frame.columns]
    if missing_columns:
        raise ValueError(
            f"Source table '{table_name}' is missing required columns: "
            f"{', '.join(missing_columns)}."
        )

    parsed_times = pd.to_datetime(
        frame[time_column],
        format="mixed",
        errors="coerce",
    )
    case_values = (
        frame[case_column]
        .astype("string")
        .str.strip()
        .str.replace(r"^([+-]?\d+)\.0+$", r"\1", regex=True)
    )
    missing_case = frame[case_column].isna() | case_values.eq("").fillna(False)
    missing_time = frame[time_column].isna()
    invalid_time = ~missing_time & parsed_times.isna()
    excluded = missing_case | missing_time | invalid_time

    records = []
    for row_position in range(len(frame)):
        if excluded.iloc[row_position]:
            continue
        records.append(
            {
                "Case_ID": str(case_values.iloc[row_position]),
                "Activity_Name": activity,
                "Timestamp": parsed_times.iloc[row_position],
                "Source_Table": table_name,
                "Source_Record_ID": f"{table_name}:{row_position + 1}",
                "Event_Type": event_type,
            }
        )

    stats = {
        "source_table": table_name,
        "source_timestamp_column": time_column,
        "candidate_event_rows": int(len(frame)),
        "missing_case_id": int(missing_case.sum()),
        "missing_timestamp": int(missing_time.sum()),
        "invalid_timestamp": int(invalid_time.sum()),
        "event_rows_created": len(records),
        "candidate_event_rows_excluded": int(excluded.sum()),
    }
    return records, stats


def build_event_log(
    tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    for table_name in ("edstays", "vitalsign", "pyxis", "medrecon"):
        if table_name not in tables:
            raise ValueError(
                f"Required source table '{table_name}.csv.gz' is missing from the ZIP."
            )

    stays = tables["edstays"]
    if "stay_id" not in stays.columns:
        raise ValueError("Source table 'edstays' is missing required column 'stay_id'.")
    if stays["stay_id"].isna().any():
        raise ValueError("Source table 'edstays' contains missing stay_id values.")
    if stays["stay_id"].duplicated().any():
        raise ValueError(
            "Source table 'edstays' contains duplicate stay_id values; "
            "ED visit mapping would be ambiguous."
        )

    event_records: list[dict[str, Any]] = []
    source_stats: dict[str, dict[str, int]] = {}
    for table_name, spec in EVENT_SOURCES.items():
        frame = tables[table_name]
        case_column = spec["case_column"]
        for time_column, activity, event_type in spec["events"]:
            records, stats = _source_event_rows(
                table_name,
                frame,
                case_column,
                time_column,
                activity,
                event_type,
            )
            event_records.extend(records)
            key = activity
            source_stats[key] = stats

    event_log = pd.DataFrame(event_records, columns=EVENT_COLUMNS)
    valid_cases = (
        stays["stay_id"]
        .astype("string")
        .str.strip()
        .str.replace(r"^([+-]?\d+)\.0+$", r"\1", regex=True)
    )
    unmatched_cases = ~event_log["Case_ID"].isin(set(valid_cases))
    if unmatched_cases.any():
        unmatched = (
            event_log.loc[unmatched_cases]
            .groupby("Source_Table")["Case_ID"]
            .agg(["size", "nunique"])
            .to_dict(orient="index")
        )
        raise ValueError(
            f"{int(unmatched_cases.sum())} candidate event rows have a stay_id "
            f"that does not map to edstays: {unmatched}."
        )
    if not event_log.empty:
        event_log = event_log.sort_values(
            ["Case_ID", "Timestamp", "Activity_Name", "Source_Record_ID"],
            kind="mergesort",
        ).reset_index(drop=True)
        event_key_counts = event_log.groupby(
            ["Case_ID", "Activity_Name", "Timestamp"],
            dropna=False,
        ).size()
        repeated_event_key_groups = int((event_key_counts > 1).sum())
        rows_in_repeated_event_key_groups = int(
            event_key_counts[event_key_counts > 1].sum()
        )
    else:
        repeated_event_key_groups = 0
        rows_in_repeated_event_key_groups = 0

    if "intime" not in stays.columns or "outtime" not in stays.columns:
        raise ValueError("Source table 'edstays' needs both 'intime' and 'outtime'.")
    arrival = pd.to_datetime(stays["intime"], format="mixed", errors="coerce")
    departure = pd.to_datetime(stays["outtime"], format="mixed", errors="coerce")
    invalid_stay_intervals = int(
        (arrival.notna() & departure.notna() & departure.lt(arrival)).sum()
    )

    source_rows = sum(len(frame) for frame in tables.values())
    event_table_names = set(EVENT_SOURCES)
    source_rows_used_for_events = sum(
        len(tables[name]) for name in event_table_names
    )
    supporting_only_source_rows = {
        name: int(len(frame))
        for name, frame in tables.items()
        if name not in event_table_names
    }
    missing_values_by_table = {
        name: {
            str(column): int(count)
            for column, count in frame.isna().sum().items()
            if count
        }
        for name, frame in tables.items()
    }
    exact_duplicate_source_rows = {
        name: int(frame.duplicated().sum()) for name, frame in tables.items()
    }
    duplicate_group_sizes = event_log.groupby(
        ["Case_ID", "Activity_Name", "Timestamp"],
        dropna=False,
    ).size()
    repeated_groups = duplicate_group_sizes[duplicate_group_sizes > 1]
    repeated_group_details = (
        event_log.groupby(["Case_ID", "Activity_Name", "Timestamp"], dropna=False)
        .agg(
            event_count=("Source_Record_ID", "size"),
            distinct_source_rows=("Source_Record_ID", "nunique"),
        )
    )
    repeated_group_details = repeated_group_details.loc[repeated_groups.index]
    exclusion_totals = {
        "missing_case_id": sum(stat["missing_case_id"] for stat in source_stats.values()),
        "missing_timestamp": sum(
            stat["missing_timestamp"] for stat in source_stats.values()
        ),
        "invalid_timestamp": sum(
            stat["invalid_timestamp"] for stat in source_stats.values()
        ),
    }
    quality = {
        "source_rows_inspected": int(source_rows),
        "source_reconciliation": {
            "total_source_rows": int(source_rows),
            "source_rows_in_event_generating_tables": int(source_rows_used_for_events),
            "distinct_source_rows_contributing_at_least_one_event": int(
                event_log[["Source_Table", "Source_Record_ID"]]
                .drop_duplicates()
                .shape[0]
            ),
            "supporting_only_source_rows_not_used_as_event_candidates": int(
                sum(supporting_only_source_rows.values())
            ),
            "supporting_only_rows_by_table": supporting_only_source_rows,
            "candidate_event_rows": int(
                sum(stat["candidate_event_rows"] for stat in source_stats.values())
            ),
            "event_rows_created": int(
                sum(stat["event_rows_created"] for stat in source_stats.values())
            ),
            "candidate_event_rows_excluded": int(
                sum(
                    stat["candidate_event_rows_excluded"]
                    for stat in source_stats.values()
                )
            ),
            "stay_rows_emit_two_boundary_events": int(len(stays)),
            "source_row_locator": (
                "Source_Record_ID uses a 1-based data-row position in the relevant "
                "CSV inside this exact archive. It is a reproducible locator, not "
                "a source-provided unique record key."
            ),
        },
        "source_tables": {
            name: {
                "row_count": int(len(frame)),
                "exact_duplicate_rows": exact_duplicate_source_rows[name],
                "missing_values": missing_values_by_table[name],
            }
            for name, frame in tables.items()
        },
        "event_sources": source_stats,
        "event_rows_created": int(
            sum(stat["event_rows_created"] for stat in source_stats.values())
        ),
        "candidate_event_rows_excluded": int(
            sum(
                stat["candidate_event_rows_excluded"]
                for stat in source_stats.values()
            )
        ),
        "exclusions_by_reason": exclusion_totals,
        "event_rows_retained_without_deduplication": int(len(event_log)),
        "repeated_case_activity_timestamp_groups_retained": repeated_event_key_groups,
        "rows_in_repeated_case_activity_timestamp_groups": rows_in_repeated_event_key_groups,
        "repeated_event_group_source_row_check": {
            "groups": int(len(repeated_group_details)),
            "groups_with_distinct_source_rows_for_every_event": int(
                repeated_group_details["event_count"]
                .eq(repeated_group_details["distinct_source_rows"])
                .sum()
            ),
            "rows_with_distinct_source_record_locators": int(
                repeated_group_details.loc[
                    repeated_group_details["event_count"]
                    .eq(repeated_group_details["distinct_source_rows"]),
                    "event_count",
                ].sum()
            ),
            "source_tables_in_repeated_groups": {
                str(name): int(count)
                for name, count in (
                    event_log.loc[
                        event_log.set_index(
                            ["Case_ID", "Activity_Name", "Timestamp"]
                        ).index.isin(repeated_groups.index)
                    ]["Source_Table"]
                    .value_counts()
                    .items()
                )
            },
            "interpretation": (
                "Each event in a repeated case/activity/timestamp group points "
                "to a distinct CSV row locator. No source table has exact "
                "duplicate full rows. This establishes distinct source rows, "
                "but cannot determine clinical equivalence or intent."
            ),
        },
        "unique_ed_visits": int(event_log["Case_ID"].nunique()),
        "activity_counts": {
            str(key): int(value)
            for key, value in event_log["Activity_Name"].value_counts().items()
        },
        "invalid_arrival_departure_intervals": invalid_stay_intervals,
        "deduplication_policy": (
            "No event-level deduplication is performed. Every source row with a "
            "valid case ID and timestamp is retained, including repeated events. "
            "Exact duplicate source rows are reported separately."
        ),
        "limitations": [
            "A Pyxis record documents a medication-cabinet record, not confirmed administration.",
            "Medication reconciliation is represented as a recorded reconciliation entry, not medication administration.",
            "Triage and diagnosis tables have no event timestamp in this archive and are not assigned invented event times.",
            "Recorded event gaps are not necessarily clinical waiting times.",
            "Source_Record_ID is a row-position locator within this exact archived CSV, not a clinical identifier.",
        ],
    }
    return event_log, quality
