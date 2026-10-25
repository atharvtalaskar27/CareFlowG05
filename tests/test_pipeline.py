from pathlib import Path

import pandas as pd
import pytest

from src.careflow.io import load_archive_tables, read_source_tables
from src.careflow.transformations import build_event_log
from src.careflow.validation import validate_event_log


def sample_tables():
    return {
        "edstays": pd.DataFrame(
            {
                "stay_id": [101],
                "intime": ["2024-01-01 08:00:00"],
                "outtime": ["2024-01-01 10:00:00"],
            }
        ),
        "vitalsign": pd.DataFrame(
            {
                "stay_id": [101, 101],
                "charttime": ["2024-01-01 08:30:00", "2024-01-01 08:30:00"],
            }
        ),
        "pyxis": pd.DataFrame(
            {"stay_id": [101], "charttime": ["2024-01-01 09:00:00"]}
        ),
        "medrecon": pd.DataFrame(
            {"stay_id": [101], "charttime": ["2024-01-01 08:15:00"]}
        ),
    }


def test_event_log_schema_sorting_and_provenance():
    tables = sample_tables()
    event_log, _ = build_event_log(tables)
    validate_event_log(event_log)
    assert list(event_log.columns) == [
        "Case_ID",
        "Activity_Name",
        "Timestamp",
        "Source_Table",
        "Source_Record_ID",
        "Event_Type",
    ]
    assert event_log["Case_ID"].tolist() == ["101"] * 6
    assert event_log["Source_Record_ID"].notna().all()


def test_repeated_events_and_repeated_source_rows_are_preserved():
    event_log, quality = build_event_log(sample_tables())
    repeated_vitals = event_log[event_log["Activity_Name"] == "Vitals Recorded"]
    assert len(repeated_vitals) == 2
    assert repeated_vitals["Source_Record_ID"].nunique() == 2
    assert quality["event_rows_retained_without_deduplication"] == 6
    assert quality["source_tables"]["vitalsign"]["exact_duplicate_rows"] == 1
    assert quality["repeated_case_activity_timestamp_groups_retained"] == 1
    assert quality["repeated_event_group_source_row_check"][
        "groups_with_distinct_source_rows_for_every_event"
    ] == 1


def test_source_to_event_row_reconciliation_is_explicit():
    event_log, quality = build_event_log(sample_tables())
    reconciliation = quality["source_reconciliation"]
    assert reconciliation["source_rows_in_event_generating_tables"] == 5
    assert reconciliation["candidate_event_rows"] == 6
    assert reconciliation["event_rows_created"] == len(event_log) == 6
    assert reconciliation["candidate_event_rows_excluded"] == 0


def test_invalid_required_rows_are_counted_and_excluded():
    tables = sample_tables()
    tables["vitalsign"] = pd.DataFrame(
        {
            "stay_id": [101, None, 101],
            "charttime": ["2024-01-01 08:30:00", "2024-01-01 08:40:00", "not-a-time"],
        }
    )
    event_log, quality = build_event_log(tables)
    vitals = quality["event_sources"]["Vitals Recorded"]
    assert len(event_log[event_log["Activity_Name"] == "Vitals Recorded"]) == 1
    assert vitals["missing_case_id"] == 1
    assert vitals["invalid_timestamp"] == 1
    assert vitals["candidate_event_rows_excluded"] == 2


def test_missing_source_table_has_actionable_error():
    tables = sample_tables()
    del tables["pyxis"]
    with pytest.raises(ValueError, match="pyxis.csv.gz.*missing"):
        build_event_log(tables)


def test_duplicate_edstay_case_identifier_fails_clearly():
    tables = sample_tables()
    tables["edstays"] = pd.concat(
        [tables["edstays"], tables["edstays"]],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="duplicate stay_id"):
        build_event_log(tables)


def test_missing_required_column_has_actionable_error():
    tables = sample_tables()
    tables["vitalsign"] = pd.DataFrame({"stay_id": [101]})
    with pytest.raises(ValueError, match="charttime"):
        build_event_log(tables)


def test_arrival_departure_order_is_reported():
    tables = sample_tables()
    tables["edstays"].loc[0, "outtime"] = "2024-01-01 07:00:00"
    _, quality = build_event_log(tables)
    assert quality["invalid_arrival_departure_intervals"] == 1


def test_float_form_case_identifiers_are_normalized_to_integer_text():
    tables = sample_tables()
    tables["vitalsign"] = pd.DataFrame(
        {"stay_id": [101.0], "charttime": ["2024-01-01 08:30:00"]}
    )
    event_log, _ = build_event_log(tables)
    assert event_log["Case_ID"].unique().tolist() == ["101"]


def test_validator_rejects_missing_timestamp():
    event_log, _ = build_event_log(sample_tables())
    event_log.loc[0, "Timestamp"] = pd.NaT
    with pytest.raises(ValueError, match="missing required values"):
        validate_event_log(event_log)


def test_validator_reconciles_every_event_to_its_source_row():
    tables = sample_tables()
    event_log, _ = build_event_log(tables)
    validate_event_log(event_log, tables)

    event_log.loc[0, "Source_Record_ID"] = "edstays:999"
    with pytest.raises(ValueError, match="does not exactly reconcile"):
        validate_event_log(event_log, tables)


def test_validator_rejects_arrival_after_departure():
    tables = sample_tables()
    event_log, _ = build_event_log(tables)
    event_log.loc[event_log["Activity_Name"].eq("ED Arrival"), "Timestamp"] = pd.Timestamp(
        "2024-01-01 11:00:00"
    )
    event_log = event_log.sort_values(
        ["Case_ID", "Timestamp", "Activity_Name", "Source_Record_ID"],
        kind="mergesort",
    ).reset_index(drop=True)
    with pytest.raises(ValueError, match="ED Arrival occurs after ED Departure"):
        validate_event_log(event_log)


def test_missing_zip_reports_expected_location(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="data folder"):
        load_archive_tables(tmp_path / "missing.zip")


def test_empty_source_file_is_reported_clearly(tmp_path: Path):
    import gzip
    from zipfile import ZipFile

    path = tmp_path / "empty.csv.gz.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(
            "mimic-iv-ed-demo-2.2/ed/edstays.csv.gz",
            gzip.compress(b""),
        )
    with load_archive_tables(path) as archive:
        with pytest.raises(ValueError, match="Could not read source table"):
            read_source_tables(archive)
