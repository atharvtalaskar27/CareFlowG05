import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import pm4py

REQUIRED_COLUMNS = ["Case_ID", "Activity_Name", "Timestamp"]
ORDER_COLUMNS = ["Case_ID", "Timestamp", "Activity_Name", "Source_Record_ID"]


def prepare_event_log(event_log: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in event_log]
    if missing_columns:
        raise ValueError(
            f"Event log is missing required columns: {', '.join(missing_columns)}."
        )
    prepared = event_log.copy()
    required_nulls = prepared[REQUIRED_COLUMNS].isna().sum()
    bad = {column: int(count) for column, count in required_nulls.items() if count}
    if bad:
        detail = ", ".join(f"{column}={count}" for column, count in bad.items())
        raise ValueError(f"Required event-log fields contain missing values: {detail}.")
    prepared["Case_ID"] = prepared["Case_ID"].astype("string").str.strip()
    prepared["Activity_Name"] = prepared["Activity_Name"].astype("string").str.strip()
    empty = prepared["Case_ID"].eq("") | prepared["Activity_Name"].eq("")
    if empty.any():
        raise ValueError(f"Event log contains {int(empty.sum())} blank case/activity values.")
    parsed = pd.to_datetime(
        prepared["Timestamp"],
        format="mixed",
        errors="coerce",
    )
    if parsed.isna().any():
        raise ValueError(
            f"Event log contains {int(parsed.isna().sum())} missing or invalid timestamps."
        )
    prepared["Timestamp"] = parsed
    if "Source_Record_ID" not in prepared.columns:
        prepared["Source_Record_ID"] = ""
    prepared = prepared.sort_values(ORDER_COLUMNS, kind="mergesort").reset_index(drop=True)
    return prepared


def _activity_counts(event_log: pd.DataFrame) -> pd.DataFrame:
    counts = (
        event_log.groupby("Activity_Name", dropna=False)
        .size()
        .rename("Event_Count")
        .reset_index()
    )
    counts["Visit_Count"] = counts["Activity_Name"].map(
        event_log.groupby("Activity_Name")["Case_ID"].nunique()
    )
    return counts.sort_values(
        ["Event_Count", "Activity_Name"], ascending=[False, True]
    ).reset_index(drop=True)


def _variant_table(event_log: pd.DataFrame) -> pd.DataFrame:
    sequences = event_log.groupby("Case_ID", sort=False)["Activity_Name"].agg(tuple)
    counts = Counter(sequences.tolist())
    rows = [
        {
            "Variant": _format_sequence(sequence),
            "Trace_Count": int(count),
            "Share_of_Visits": float(count / len(sequences)),
            "Activity_Count": len(sequence),
        }
        for sequence, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    return pd.DataFrame(
        rows,
        columns=["Variant", "Trace_Count", "Share_of_Visits", "Activity_Count"],
    )


def _format_sequence(sequence: tuple[str, ...]) -> str:
    parts = []
    for activity in sequence:
        if parts and parts[-1][1] == activity:
            parts[-1] = (parts[-1][0] + 1, activity)
        else:
            parts.append((1, activity))
    return " -> ".join(
        f"{count}x {activity}" if count > 1 else activity
        for count, activity in parts
    )


def _visit_metrics(event_log: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    gap_frames = []
    repeated_rows = []
    review_rows = []
    for case_id, visit in event_log.groupby("Case_ID", sort=False):
        visit = visit.reset_index(drop=True)
        activity_counts = visit["Activity_Name"].value_counts()
        repeated = activity_counts[activity_counts > 1]
        for activity, count in repeated.items():
            repeated_rows.append(
                {
                    "Case_ID": str(case_id),
                    "Activity_Name": str(activity),
                    "Occurrence_Count": int(count),
                }
            )

        if len(visit) > 1:
            previous = visit.iloc[:-1].reset_index(drop=True)
            following = visit.iloc[1:].reset_index(drop=True)
            gap_minutes = (
                following["Timestamp"] - previous["Timestamp"]
            ).dt.total_seconds() / 60
            gap_frames.append(
                pd.DataFrame(
                    {
                        "Case_ID": str(case_id),
                        "Previous_Activity": previous["Activity_Name"].astype(str),
                        "Next_Activity": following["Activity_Name"].astype(str),
                        "Previous_Timestamp": previous["Timestamp"],
                        "Next_Timestamp": following["Timestamp"],
                        "Recorded_Event_Gap_Minutes": gap_minutes,
                        "Same_Timestamp": gap_minutes.eq(0),
                    }
                )
            )

        activities = visit["Activity_Name"].tolist()
        timestamps = visit["Timestamp"]
        flags = []
        if "ED Arrival" not in activities:
            flags.append("Missing recorded ED Arrival")
        if "ED Departure" not in activities:
            flags.append("Missing recorded ED Departure")
        if "ED Departure" in activities and activities[-1] != "ED Departure":
            flags.append("ED Departure is not the final sorted activity")
        if any(
            earlier == later
            for earlier, later in zip(activities, activities[1:])
        ):
            flags.append("Consecutive repeated activity; review timestamp/source ordering")
        if timestamps.duplicated(keep=False).any():
            flags.append("Multiple records share a timestamp; within-time order is ambiguous")
        if flags:
            review_rows.append(
                {
                    "Case_ID": str(case_id),
                    "Review_Flags": "; ".join(flags),
                    "Event_Count": len(visit),
                }
            )

    gaps = (
        pd.concat(gap_frames, ignore_index=True)
        if gap_frames
        else pd.DataFrame(
            columns=[
                "Case_ID",
                "Previous_Activity",
                "Next_Activity",
                "Previous_Timestamp",
                "Next_Timestamp",
                "Recorded_Event_Gap_Minutes",
                "Same_Timestamp",
            ]
        )
    )
    repeats = pd.DataFrame(
        repeated_rows,
        columns=["Case_ID", "Activity_Name", "Occurrence_Count"],
    )
    flags = pd.DataFrame(
        review_rows,
        columns=["Case_ID", "Review_Flags", "Event_Count"],
    )
    return gaps, repeats, flags


def _discover_dfg(
    event_log: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int], dict[str, int]]:
    formatted = pm4py.format_dataframe(
        event_log,
        case_id="Case_ID",
        activity_key="Activity_Name",
        timestamp_key="Timestamp",
    )
    dfg, starts, ends = pm4py.discover_dfg(formatted)
    edges = pd.DataFrame(
        [
            {
                "From_Activity": str(source),
                "To_Activity": str(target),
                "Trace_Transition_Count": int(count),
            }
            for (source, target), count in dfg.items()
        ],
        columns=["From_Activity", "To_Activity", "Trace_Transition_Count"],
    )
    if not edges.empty:
        edges = edges.sort_values(
            ["Trace_Transition_Count", "From_Activity", "To_Activity"],
            ascending=[False, True, True],
        ).reset_index(drop=True)
    return (
        edges,
        {str(activity): int(count) for activity, count in starts.items()},
        {str(activity): int(count) for activity, count in ends.items()},
    )


def analyze_event_log(event_log: pd.DataFrame) -> dict[str, Any]:
    prepared = prepare_event_log(event_log)
    if prepared.empty:
        raise ValueError("Event log is empty; process analysis requires event records.")

    activity_counts = _activity_counts(prepared)
    variants = _variant_table(prepared)
    gaps, repeated_activities, review_flags = _visit_metrics(prepared)
    visits = (
        prepared.groupby("Case_ID", sort=False)
        .agg(
            Event_Count=("Activity_Name", "size"),
            Distinct_Activity_Count=("Activity_Name", "nunique"),
            First_Recorded_Timestamp=("Timestamp", "min"),
            Last_Recorded_Timestamp=("Timestamp", "max"),
        )
        .reset_index()
    )
    visits = visits.sort_values(
        ["Event_Count", "Case_ID"], ascending=[False, True]
    ).reset_index(drop=True)
    departure_order_checks = {
        "visits_with_arrival": 0,
        "visits_with_departure": 0,
        "visits_with_departure_not_last": 0,
        "visits_with_non_departure_event_after_departure_time": 0,
        "visits_with_non_departure_event_tied_with_departure": 0,
        "visits_with_arrival_after_departure": 0,
    }
    for _, visit in prepared.groupby("Case_ID", sort=False):
        arrivals = visit.loc[
            visit["Activity_Name"].eq("ED Arrival"), "Timestamp"
        ]
        departures = visit.loc[
            visit["Activity_Name"].eq("ED Departure"), "Timestamp"
        ]
        departure_order_checks["visits_with_arrival"] += int(not arrivals.empty)
        departure_order_checks["visits_with_departure"] += int(not departures.empty)
        if departures.empty:
            continue
        departure_time = departures.max()
        non_departure = visit.loc[~visit["Activity_Name"].eq("ED Departure")]
        after_departure = non_departure["Timestamp"].gt(departure_time)
        tied_with_departure = non_departure["Timestamp"].eq(departure_time)
        departure_order_checks[
            "visits_with_non_departure_event_after_departure_time"
        ] += int(after_departure.any())
        departure_order_checks[
            "visits_with_non_departure_event_tied_with_departure"
        ] += int(tied_with_departure.any())
        departure_order_checks["visits_with_departure_not_last"] += int(
            visit.iloc[-1]["Activity_Name"] != "ED Departure"
        )
        if not arrivals.empty:
            departure_order_checks["visits_with_arrival_after_departure"] += int(
                arrivals.max() > departure_time
            )

    # Summarize non-departure events recorded after the latest ED departure.
    late_event_frames = []
    for _, visit in prepared.groupby("Case_ID", sort=False):
        departures = visit.loc[
            visit["Activity_Name"].eq("ED Departure"), "Timestamp"
        ]
        if departures.empty:
            continue
        departure_time = departures.max()
        late_events = visit.loc[
            ~visit["Activity_Name"].eq("ED Departure")
            & visit["Timestamp"].gt(departure_time)
        ].copy()
        if not late_events.empty:
            late_events["Hours_After_Departure"] = (
                late_events["Timestamp"] - departure_time
            ).dt.total_seconds() / 3600
            late_event_frames.append(late_events)

    if late_event_frames:
        late_events = pd.concat(late_event_frames, ignore_index=True)
        late_hours = late_events["Hours_After_Departure"]
        post_departure_summary = {
            "event_count": int(len(late_events)),
            "visit_count": int(late_events["Case_ID"].nunique()),
            "by_activity": {
                str(key): int(value)
                for key, value in late_events["Activity_Name"]
                .value_counts().sort_index().items()
            },
            "by_source_table": (
                {
                    str(key): int(value)
                    for key, value in late_events["Source_Table"]
                    .fillna("Unknown")
                    .value_counts().sort_index().items()
                }
                if "Source_Table" in late_events.columns
                else {}
            ),
            "hours_after_departure": {
                "minimum": float(late_hours.min()),
                "median": float(late_hours.median()),
                "mean": float(late_hours.mean()),
                "p75": float(late_hours.quantile(0.75)),
                "maximum": float(late_hours.max()),
            },
        }
    else:
        post_departure_summary = {
            "event_count": 0,
            "visit_count": 0,
            "by_activity": {},
            "by_source_table": {},
            "hours_after_departure": None,
        }

    if len(prepared) > prepared["Case_ID"].nunique():
        dfg_edges, start_activities, end_activities = _discover_dfg(prepared)
        model_status = (
            "PM4Py directly-follows graph discovered from recorded activity "
            "sequences. It is an exploratory model, not a validated clinical pathway."
        )
    else:
        dfg_edges = pd.DataFrame(
            columns=["From_Activity", "To_Activity", "Trace_Transition_Count"]
        )
        start_activities = {}
        end_activities = {}
        model_status = "No multi-event trace exists; a directly-follows model was not discovered."

    gap_values = gaps["Recorded_Event_Gap_Minutes"].astype(float)
    gap_stats = {
        "transition_count": int(len(gap_values)),
        "same_timestamp_transition_count": int(gaps["Same_Timestamp"].sum()),
        "positive_gap_count": int((gap_values > 0).sum()),
        "minimum_minutes": None if gap_values.empty else float(gap_values.min()),
        "median_minutes": None if gap_values.empty else float(gap_values.median()),
        "p90_minutes": None if gap_values.empty else float(gap_values.quantile(0.9)),
        "maximum_minutes": None if gap_values.empty else float(gap_values.max()),
    }
    summary = {
        "input_file": "output/clean_event_log.csv",
        "schema": list(event_log.columns),
        "required_columns_used": REQUIRED_COLUMNS,
        "total_events": int(len(prepared)),
        "unique_ed_visits": int(prepared["Case_ID"].nunique()),
        "unique_activities": int(prepared["Activity_Name"].nunique()),
        "events_per_visit": {
            "minimum": int(visits["Event_Count"].min()),
            "median": float(visits["Event_Count"].median()),
            "mean": float(visits["Event_Count"].mean()),
            "maximum": int(visits["Event_Count"].max()),
        },
        "activity_counts": {
            str(row.Activity_Name): int(row.Event_Count)
            for row in activity_counts.itertuples(index=False)
        },
        "distinct_variants": int(len(variants)),
        "top_variants": variants.head(10).to_dict(orient="records"),
        "visits_with_repeated_activities": int(
            repeated_activities["Case_ID"].nunique()
        ),
        "repeated_activity_visit_pairs": int(len(repeated_activities)),
        "event_gap_minutes": gap_stats,
        "arrival_departure_checks": departure_order_checks,
        "post_departure_events": post_departure_summary,
        "sequence_review_flagged_visits": int(review_flags["Case_ID"].nunique()),
        "directly_follows_edges": int(len(dfg_edges)),
        "start_activities": start_activities,
        "end_activities": end_activities,
        "model_status": model_status,
        "interpretation_limitations": [
            "All time differences are gaps between recorded events, not confirmed clinical waiting times.",
            "Records sharing a timestamp have no defensible within-timestamp order; deterministic activity sorting is only for repeatability.",
            "Activity labels describe source records. Pyxis records do not prove medication administration.",
            "Triage and diagnosis are not timestamped in the source archive and are absent from this event log.",
            "Observed variants and the directly-follows graph describe this demo extract only and do not establish clinical bottlenecks or causal pathways.",
        ],
    }
    return {
        "summary": summary,
        "prepared_event_log": prepared,
        "activity_counts": activity_counts,
        "variants": variants,
        "events_per_visit": visits,
        "recorded_event_gaps": gaps,
        "repeated_activities": repeated_activities,
        "sequence_review_flags": review_flags,
        "directly_follows_edges": dfg_edges,
    }


def write_analysis(analysis: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = analysis["summary"]
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for key, filename in [
        ("activity_counts", "activity_counts.csv"),
        ("variants", "process_variants.csv"),
        ("events_per_visit", "events_per_visit.csv"),
        ("recorded_event_gaps", "recorded_event_gaps.csv"),
        ("repeated_activities", "repeated_activities.csv"),
        ("sequence_review_flags", "sequence_review_flags.csv"),
        ("directly_follows_edges", "directly_follows_edges.csv"),
    ]:
        analysis[key].to_csv(output_dir / filename, index=False)
    _write_summary_markdown(summary, analysis, output_dir / "summary.md")


def _write_summary_markdown(
    summary: dict[str, Any],
    analysis: dict[str, Any],
    path: Path,
) -> None:
    activity_lines = [
        f"| {activity} | {count} |"
        for activity, count in summary["activity_counts"].items()
    ]
    variant_lines = [
        f"| {row['Trace_Count']} | {row['Activity_Count']} | "
        f"{row['Variant']} |"
        for row in summary["top_variants"]
    ]
    edges = analysis["directly_follows_edges"].head(15)
    edge_lines = [
        f"| {row.From_Activity} | {row.To_Activity} | "
        f"{row.Trace_Transition_Count} |"
        for row in edges.itertuples(index=False)
    ]
    gaps = summary["event_gap_minutes"]
    post_departure = summary["post_departure_events"]
    late_source_lines = [
        f"| {source} | {count} |"
        for source, count in post_departure["by_source_table"].items()
    ] or ["| None recorded | 0 |"]
    late_activity_lines = [
        f"| {activity} | {count} |"
        for activity, count in post_departure["by_activity"].items()
    ] or ["| None recorded | 0 |"]
    late_hours = post_departure["hours_after_departure"]
    lines = [
        "# Initial process-mining analysis",
        "",
        "## Scope and suitability",
        "",
        f"- Input columns: {', '.join(f'`{column}`' for column in summary['schema'])}",
        f"- Events: {summary['total_events']}; distinct ED visits: {summary['unique_ed_visits']}; "
        f"activities: {summary['unique_activities']}.",
        f"- Events per visit: minimum {summary['events_per_visit']['minimum']}, "
        f"median {summary['events_per_visit']['median']:.1f}, mean "
        f"{summary['events_per_visit']['mean']:.1f}, maximum "
        f"{summary['events_per_visit']['maximum']}.",
        f"- {summary['model_status']}",
        "",
        "## Activity counts",
        "",
        "| Activity | Events |",
        "|---|---:|",
        *activity_lines,
        "",
        "## Common observed variants",
        "",
        f"There are {summary['distinct_variants']} distinct ordered activity "
        "sequences in this extract. Consecutive identical labels are shown as "
        "`N x Activity` for readability. Variants summarize recorded labels only.",
        "",
        "| Visits | Events in sequence | Observed sequence |",
        "|---:|---:|---|",
        *variant_lines,
        "",
        "## Directly-follows graph",
        "",
        "Counts below are adjacent activity pairs in the timestamp-sorted "
        "recorded traces, not clinical causality.",
        "",
        "| From | To | Recorded transitions |",
        "|---|---|---:|",
        *edge_lines,
        "",
        "## Recorded-event gaps",
        "",
        f"There are {gaps['transition_count']} consecutive-record gaps. "
        f"Median: {gaps['median_minutes']:.1f} minutes; 90th percentile: "
        f"{gaps['p90_minutes']:.1f} minutes; maximum: "
        f"{gaps['maximum_minutes']:.1f} minutes. "
        f"{gaps['same_timestamp_transition_count']} transitions have the same "
        "timestamp (zero-minute gap). These are recorded-event gaps, not "
        "confirmed clinical waiting times.",
        "",
        "## Events recorded after ED departure",
        "",
        f"{post_departure['event_count']} non-departure events across "
        f"{post_departure['visit_count']} visits have timestamps strictly later "
        "than the latest recorded ED departure. These are source-record timestamp "
        "patterns and do not by themselves establish clinical delay or error.",
        "",
        "### By source table",
        "",
        "| Source table | Events |",
        "|---|---:|",
        *late_source_lines,
        "",
        "### By activity",
        "",
        "| Activity | Events |",
        "|---|---:|",
        *late_activity_lines,
        "",
        "### Time after recorded departure",
        "",
        (
            "No post-departure events were found."
            if late_hours is None
            else (
                f"Minimum: {late_hours['minimum']:.4f} hours; median: "
                f"{late_hours['median']:.2f} hours; mean: "
                f"{late_hours['mean']:.2f} hours; 75th percentile: "
                f"{late_hours['p75']:.2f} hours; maximum: "
                f"{late_hours['maximum']:.2f} hours."
            )
        ),
        "These are timestamp differences, not confirmed patient waiting times.",
        "",
        "## Repeated activities and sequences to review",
        "",
        f"{summary['visits_with_repeated_activities']} visits have at least one "
        "activity recorded more than once. See `repeated_activities.csv` for "
        f"visit/activity counts. {summary['sequence_review_flagged_visits']} "
        "visits have one or more ordering/data-review flags; see "
        "`sequence_review_flags.csv`.",
        "",
        "Repeated records are not automatically errors. Multiple activities at "
        "the same timestamp have ambiguous within-time order; the pipeline uses "
        "activity name and source-row reference only to make results repeatable.",
        "",
        f"Recorded arrival appears in {summary['arrival_departure_checks']['visits_with_arrival']} "
        f"visits and recorded departure appears in "
        f"{summary['arrival_departure_checks']['visits_with_departure']} visits. "
        f"{summary['arrival_departure_checks']['visits_with_non_departure_event_after_departure_time']} "
        "visits contain a non-departure record with a timestamp strictly later "
        "than departure, and "
        f"{summary['arrival_departure_checks']['visits_with_non_departure_event_tied_with_departure']} "
        "have a non-departure record tied to the departure timestamp. Both "
        "patterns merit source-semantics review. "
        f"{summary['arrival_departure_checks']['visits_with_arrival_after_departure']} "
        "visits have a recorded arrival later than the latest recorded departure.",
        "",
        "Directly-follows self-loops (the same recorded activity label repeated "
        "consecutively) often reflect repeated source rows/observations and do "
        "not by themselves prove a clinical loop.",
        "",
        "## Limitations",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["interpretation_limitations"])
    lines.extend(
        [
            "",
            "No bottleneck, care delay, or clinical outcome conclusion is made by "
            "this descriptive analysis.",
            "",
            "## Output files",
            "",
            "- `summary.json`: machine-readable headline measures.",
            "- `activity_counts.csv`: activity frequencies and visit counts.",
            "- `process_variants.csv`: full ordered observed sequences and counts.",
            "- `events_per_visit.csv`: per-visit event totals and observed time span.",
            "- `recorded_event_gaps.csv`: consecutive event pairs and time differences.",
            "- `repeated_activities.csv`: repeated activity counts by visit.",
            "- `sequence_review_flags.csv`: visits requiring ordering/data review.",
            "- `directly_follows_edges.csv`: PM4Py directly-follows model transitions.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
