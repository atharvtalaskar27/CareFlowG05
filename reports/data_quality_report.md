# Data quality report

Generated from the local MIMIC-IV-ED demo ZIP. Source files were read
without changing or extracting them.

## Summary

- Source rows inspected across all tables: 5873
- Event rows created: 5328
- Candidate event rows excluded for missing/invalid required fields: 0
- Distinct ED visits represented: 222
- Arrival/departure intervals with departure before arrival: 0

## Source-row to event-row reconciliation

- Source rows in the four event-generating tables: 5106.
- Distinct source rows that contributed at least one event: 5106.
- Candidate event rows from those tables: 5328.
- Triage and diagnosis supporting rows not used as event candidates: 767 (diagnosis: 545, triage: 222).
- Each `edstays` row produces two candidate event rows (arrival and departure); each `vitalsign`, `pyxis`, and `medrecon` row produces one.
- Triage and diagnosis have no suitable event timestamp in these files. They are supporting tables, not rejected timestamped-event candidates.
- A candidate event row is excluded only if its visit ID is missing, its timestamp is missing, or its timestamp cannot be parsed.

## Source table completeness and exact duplicates

| Table | Source rows | Exact duplicate source rows | Fields with missing values |
|---|---:|---:|---|
| `diagnosis` | 545 | 0 | none |
| `edstays` | 222 | 0 | `hadm_id` (50) |
| `medrecon` | 2764 | 0 | `etccode` (4), `etcdescription` (4) |
| `pyxis` | 1082 | 0 | `gsn` (32) |
| `triage` | 222 | 0 | `temperature` (26), `heartrate` (24), `resprate` (23), `o2sat` (24), `sbp` (23), `dbp` (23), `pain` (21), `acuity` (15) |
| `vitalsign` | 1038 | 0 | `temperature` (459), `heartrate` (30), `resprate` (48), `o2sat` (67), `sbp` (40), `dbp` (40), `rhythm` (1005), `pain` (302) |

## Repeated event keys

- 590 repeated `Case_ID`/`Activity_Name`/`Timestamp` groups contain 3392 event rows.
- Every event row in all 590 groups with a repeated key has a distinct CSV source-row locator.
- Repeated-group event rows by source table: medrecon: 2648, pyxis: 744.
- Exact full-row duplicate counts are zero in all six source tables. The repeated event keys therefore refer to distinct source rows, but the available columns cannot determine whether any records are clinically equivalent or whether the repetition is intentional.
- No rows are deleted for repeated keys or duplicate-looking events.

## Event-generation counts

| Activity | Source table/time field | Candidate event rows | Created | Missing case ID | Missing timestamp | Invalid timestamp | Excluded |
|---|---|---:|---:|---:|---:|---:|---:|
| ED Arrival | `edstays.intime` | 222 | 222 | 0 | 0 | 0 | 0 |
| ED Departure | `edstays.outtime` | 222 | 222 | 0 | 0 | 0 | 0 |
| Vitals Recorded | `vitalsign.charttime` | 1038 | 1038 | 0 | 0 | 0 | 0 |
| Pyxis Medication Record | `pyxis.charttime` | 1082 | 1082 | 0 | 0 | 0 | 0 |
| Medication Reconciliation Recorded | `medrecon.charttime` | 2764 | 2764 | 0 | 0 | 0 | 0 |

## Provenance and cleaning decisions

- Source_Record_ID uses a 1-based data-row position in the relevant CSV inside this exact archive. It is a reproducible locator, not a source-provided unique record key.
- Case_ID comes from the source ED visit `stay_id`; source reconciliation checks every output row against its corresponding source row.
- Source timestamps are parsed from the named source field. No timestamps are filled or invented.
- Event rows are sorted by Case_ID, Timestamp, Activity_Name, then Source_Record_ID for deterministic ordering.
- Pyxis records are cabinet records, not proof of medication administration.
- Medication reconciliation records are not medication administration events.
- Triage and diagnosis remain supporting information because they do not contain a suitable event timestamp.
- Recorded event gaps are not established clinical waiting times.

## Other data-quality limitations

- A Pyxis record documents a medication-cabinet record, not confirmed administration.
- Medication reconciliation is represented as a recorded reconciliation entry, not medication administration.
- Triage and diagnosis tables have no event timestamp in this archive and are not assigned invented event times.
- Recorded event gaps are not necessarily clinical waiting times.
- Source_Record_ID is a row-position locator within this exact archived CSV, not a clinical identifier.
