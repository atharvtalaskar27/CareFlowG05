import pandas as pd
import pytest

from src.careflow.process_mining import analyze_event_log


def sample_event_log():
    return pd.DataFrame(
        {
            "Case_ID": ["A", "A", "A", "B", "B"],
            "Activity_Name": [
                "ED Arrival",
                "Vitals Recorded",
                "ED Departure",
                "ED Arrival",
                "ED Departure",
            ],
            "Timestamp": [
                "2024-01-01 08:00:00",
                "2024-01-01 08:10:00",
                "2024-01-01 08:30:00",
                "2024-01-02 09:00:00",
                "2024-01-02 09:30:00",
            ],
            "Source_Record_ID": ["1", "2", "3", "4", "5"],
        }
    )


def test_analysis_counts_visits_variants_gaps_and_dfg():
    analysis = analyze_event_log(sample_event_log())
    summary = analysis["summary"]
    assert summary["total_events"] == 5
    assert summary["unique_ed_visits"] == 2
    assert summary["distinct_variants"] == 2
    assert summary["event_gap_minutes"]["transition_count"] == 3
    assert summary["event_gap_minutes"]["median_minutes"] == 20
    assert not analysis["directly_follows_edges"].empty
    assert summary["start_activities"] == {"ED Arrival": 2}
    assert summary["end_activities"] == {"ED Departure": 2}


def test_tied_timestamps_are_reported_not_treated_as_ordered_time():
    events = sample_event_log()
    events.loc[1, "Timestamp"] = "2024-01-01 08:00:00"
    analysis = analyze_event_log(events)
    assert analysis["summary"]["event_gap_minutes"]["same_timestamp_transition_count"] == 1
    assert any(
        "within-time order is ambiguous" in flag
        for flag in analysis["sequence_review_flags"]["Review_Flags"]
    )


def test_departure_order_flags_distinguish_later_from_tied_event_times():
    events = sample_event_log()
    events.loc[1, "Timestamp"] = "2024-01-01 08:30:00"
    events.loc[len(events)] = [
        "B",
        "Vitals Recorded",
        "2024-01-02 09:31:00",
        "6",
    ]
    checks = analyze_event_log(events)["summary"]["arrival_departure_checks"]
    assert checks["visits_with_non_departure_event_after_departure_time"] == 1
    assert checks["visits_with_non_departure_event_tied_with_departure"] == 1
    assert checks["visits_with_departure_not_last"] == 2


def test_missing_required_columns_fail_clearly():
    with pytest.raises(ValueError, match="Activity_Name"):
        analyze_event_log(pd.DataFrame({"Case_ID": ["A"], "Timestamp": ["2024-01-01"]}))


def test_invalid_timestamp_fails_clearly():
    events = sample_event_log()
    events.loc[0, "Timestamp"] = "not-a-time"
    with pytest.raises(ValueError, match="invalid timestamps"):
        analyze_event_log(events)
