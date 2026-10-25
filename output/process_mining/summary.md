# Initial process-mining analysis

## Scope and suitability

- Input columns: `Case_ID`, `Activity_Name`, `Timestamp`, `Source_Table`, `Source_Record_ID`, `Event_Type`
- Events: 5328; distinct ED visits: 222; activities: 5.
- Events per visit: minimum 2, median 21.0, mean 24.0, maximum 76.
- PM4Py directly-follows graph discovered from recorded activity sequences. It is an exploratory model, not a validated clinical pathway.

## Activity counts

| Activity | Events |
|---|---:|
| Medication Reconciliation Recorded | 2764 |
| Pyxis Medication Record | 1082 |
| Vitals Recorded | 1038 |
| ED Arrival | 222 |
| ED Departure | 222 |

## Common observed variants

There are 216 distinct ordered activity sequences in this extract. Consecutive identical labels are shown as `N x Activity` for readability. Variants summarize recorded labels only.

| Visits | Events in sequence | Observed sequence |
|---:|---:|---|
| 6 | 2 | ED Arrival -> ED Departure |
| 2 | 12 | ED Arrival -> 9x Medication Reconciliation Recorded -> Vitals Recorded -> ED Departure |
| 1 | 7 | ED Arrival -> ED Departure -> 5x Pyxis Medication Record |
| 1 | 21 | ED Arrival -> 19x Medication Reconciliation Recorded -> ED Departure |
| 1 | 32 | ED Arrival -> 25x Medication Reconciliation Recorded -> 2x Pyxis Medication Record -> Vitals Recorded -> Pyxis Medication Record -> Vitals Recorded -> ED Departure |
| 1 | 32 | ED Arrival -> 23x Medication Reconciliation Recorded -> Vitals Recorded -> Pyxis Medication Record -> Vitals Recorded -> 2x Pyxis Medication Record -> 2x Vitals Recorded -> ED Departure |
| 1 | 28 | ED Arrival -> 22x Medication Reconciliation Recorded -> 4x Vitals Recorded -> ED Departure |
| 1 | 25 | ED Arrival -> 21x Medication Reconciliation Recorded -> 2x Vitals Recorded -> ED Departure |
| 1 | 31 | ED Arrival -> 18x Medication Reconciliation Recorded -> Pyxis Medication Record -> Vitals Recorded -> Pyxis Medication Record -> 8x Vitals Recorded -> ED Departure |
| 1 | 27 | ED Arrival -> 18x Medication Reconciliation Recorded -> Vitals Recorded -> 5x Pyxis Medication Record -> Vitals Recorded -> ED Departure |

## Directly-follows graph

Counts below are adjacent activity pairs in the timestamp-sorted recorded traces, not clinical causality.

| From | To | Recorded transitions |
|---|---|---:|
| Medication Reconciliation Recorded | Medication Reconciliation Recorded | 2575 |
| Pyxis Medication Record | Pyxis Medication Record | 676 |
| Vitals Recorded | Vitals Recorded | 430 |
| Pyxis Medication Record | Vitals Recorded | 324 |
| Vitals Recorded | Pyxis Medication Record | 300 |
| Vitals Recorded | ED Departure | 159 |
| ED Arrival | Vitals Recorded | 150 |
| Vitals Recorded | Medication Reconciliation Recorded | 121 |
| Medication Reconciliation Recorded | Vitals Recorded | 108 |
| Medication Reconciliation Recorded | Pyxis Medication Record | 71 |
| Pyxis Medication Record | ED Departure | 46 |
| ED Arrival | Medication Reconciliation Recorded | 38 |
| Pyxis Medication Record | Medication Reconciliation Recorded | 29 |
| ED Arrival | Pyxis Medication Record | 27 |
| ED Departure | Vitals Recorded | 24 |

## Recorded-event gaps

There are 5106 consecutive-record gaps. Median: 0.0 minutes; 90th percentile: 74.5 minutes; maximum: 1274.0 minutes. 2858 transitions have the same timestamp (zero-minute gap). These are recorded-event gaps, not confirmed clinical waiting times.

## Events recorded after ED departure

123 non-departure events across 31 visits have timestamps strictly later than the latest recorded ED departure. These are source-record timestamp patterns and do not by themselves establish clinical delay or error.

### By source table

| Source table | Events |
|---|---:|
| medrecon | 7 |
| pyxis | 49 |
| vitalsign | 67 |

### By activity

| Activity | Events |
|---|---:|
| Medication Reconciliation Recorded | 7 |
| Pyxis Medication Record | 49 |
| Vitals Recorded | 67 |

### Time after recorded departure

Minimum: 0.0011 hours; median: 1.85 hours; mean: 4.30 hours; 75th percentile: 4.47 hours; maximum: 35.32 hours.
These are timestamp differences, not confirmed patient waiting times.

## Repeated activities and sequences to review

215 visits have at least one activity recorded more than once. See `repeated_activities.csv` for visit/activity counts. 215 visits have one or more ordering/data-review flags; see `sequence_review_flags.csv`.

Repeated records are not automatically errors. Multiple activities at the same timestamp have ambiguous within-time order; the pipeline uses activity name and source-row reference only to make results repeatable.

Recorded arrival appears in 222 visits and recorded departure appears in 222 visits. 31 visits contain a non-departure record with a timestamp strictly later than departure, and 1 have a non-departure record tied to the departure timestamp. Both patterns merit source-semantics review. 0 visits have a recorded arrival later than the latest recorded departure.

Directly-follows self-loops (the same recorded activity label repeated consecutively) often reflect repeated source rows/observations and do not by themselves prove a clinical loop.

## Limitations

- All time differences are gaps between recorded events, not confirmed clinical waiting times.
- Records sharing a timestamp have no defensible within-timestamp order; deterministic activity sorting is only for repeatability.
- Activity labels describe source records. Pyxis records do not prove medication administration.
- Triage and diagnosis are not timestamped in the source archive and are absent from this event log.
- Observed variants and the directly-follows graph describe this demo extract only and do not establish clinical bottlenecks or causal pathways.

No bottleneck, care delay, or clinical outcome conclusion is made by this descriptive analysis.

## Output files

- `summary.json`: machine-readable headline measures.
- `activity_counts.csv`: activity frequencies and visit counts.
- `process_variants.csv`: full ordered observed sequences and counts.
- `events_per_visit.csv`: per-visit event totals and observed time span.
- `recorded_event_gaps.csv`: consecutive event pairs and time differences.
- `repeated_activities.csv`: repeated activity counts by visit.
- `sequence_review_flags.csv`: visits requiring ordering/data review.
- `directly_follows_edges.csv`: PM4Py directly-follows model transitions.
