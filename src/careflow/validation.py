import pandas as pd

from src.careflow.transformations import EVENT_COLUMNS, build_event_log


def validate_event_log(
    event_log: pd.DataFrame,
    source_tables: dict[str, pd.DataFrame] | None = None,
) -> None:
    missing_columns = [column for column in EVENT_COLUMNS if column not in event_log]
    if missing_columns:
        raise ValueError(
            f"Event log is missing required columns: {', '.join(missing_columns)}."
        )

    required = [
        "Case_ID",
        "Activity_Name",
        "Timestamp",
        "Source_Table",
        "Source_Record_ID",
        "Event_Type",
    ]
    null_counts = event_log[required].isna().sum()
    null_fields = [name for name, count in null_counts.items() if count]
    if null_fields:
        detail = ", ".join(f"{name}={int(null_counts[name])}" for name in null_fields)
        raise ValueError(f"Event log contains missing required values: {detail}.")

    if event_log.empty:
        raise ValueError("Event log is empty; no events are available to validate.")

    if not event_log.empty:
        timestamps = pd.to_datetime(
            event_log["Timestamp"],
            format="mixed",
            errors="coerce",
        )
        if timestamps.isna().any():
            raise ValueError(
                f"Event log contains {int(timestamps.isna().sum())} unparseable timestamps."
            )
        event_log = event_log.copy()
        event_log["Timestamp"] = timestamps
        if not event_log["Case_ID"].map(lambda value: isinstance(value, str)).all():
            raise ValueError("All Case_ID values must be strings.")
        sort_columns = ["Case_ID", "Timestamp", "Activity_Name", "Source_Record_ID"]
        expected = event_log.sort_values(sort_columns, kind="mergesort").index
        if not expected.equals(event_log.index):
            raise ValueError("Event log is not sorted by case, time, and event.")
        if event_log["Case_ID"].astype("string").str.strip().eq("").any():
            raise ValueError("Event log contains blank Case_ID values.")
        if event_log["Activity_Name"].astype("string").str.strip().eq("").any():
            raise ValueError("Event log contains blank Activity_Name values.")

        boundaries = event_log.loc[
            event_log["Activity_Name"].isin(["ED Arrival", "ED Departure"]),
            ["Case_ID", "Activity_Name", "Timestamp"],
        ]
        for case_id, visit in boundaries.groupby("Case_ID", sort=False):
            arrivals = visit.loc[
                visit["Activity_Name"].eq("ED Arrival"), "Timestamp"
            ]
            departures = visit.loc[
                visit["Activity_Name"].eq("ED Departure"), "Timestamp"
            ]
            if not arrivals.empty and not departures.empty:
                if arrivals.max() > departures.min():
                    raise ValueError(
                        f"ED Arrival occurs after ED Departure for Case_ID {case_id}."
                    )

    if source_tables is not None:
        expected_event_log, _ = build_event_log(source_tables)
        expected_rows = expected_event_log[EVENT_COLUMNS].copy()
        actual_rows = event_log[EVENT_COLUMNS].copy()
        for column in ("Case_ID", "Activity_Name", "Source_Table", "Source_Record_ID", "Event_Type"):
            expected_rows[column] = expected_rows[column].astype("string")
            actual_rows[column] = actual_rows[column].astype("string")
        expected_rows["Timestamp"] = pd.to_datetime(
            expected_rows["Timestamp"],
            format="mixed",
            errors="raise",
        )
        actual_rows["Timestamp"] = pd.to_datetime(
            actual_rows["Timestamp"],
            format="mixed",
            errors="raise",
        )
        expected_rows = expected_rows.reset_index(drop=True)
        actual_rows = actual_rows.reset_index(drop=True)
        if not expected_rows.equals(actual_rows):
            raise ValueError(
                "Event log does not exactly reconcile to the source tables by "
                "case, activity, timestamp, source table, source row locator, "
                "and event type. Regenerate the event log and inspect changes."
            )
