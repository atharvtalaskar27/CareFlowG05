# CareFlow: Clinical Pathway Process Mining

An Emergency Department (ED) event-log dashboard built with Power BI.
Project of the Infotact Solutions Data Analytics Internship (Team Group No. 5, Ref. ITS/DA/1135).

## About
Hospital administrators usually see one average ED wait time, which hides the sequence of events behind each visit. CareFlow turns ED event records into an event log, shows how recorded activities follow each other, and presents the results in an interactive Power BI dashboard.

The analysis uses a de-identified ED demonstration extract: 222 visits, 5,328 recorded events and 5 activities (ED Arrival, Vitals Recorded, Medication Reconciliation Recorded, Pyxis Medication Record, ED Departure).

## Dashboard pages
1. **Overview:** visits, length of stay, arrivals by hour and shift, longest recorded stays
2. **Activities and flow:** which activities were recorded and how they follow each other
3. **Recorded event gaps:** time between recorded events
4. **Data quality and limitations:** data checks and what the analysis cannot show

## Folder structure
```
dashboard/      Power BI file (careflow.pbix)
report/         Project report: main.pdf, LaTeX source (main.tex), images/
screenshots/    The four dashboard pages
presentation/   CareFlow_Presentation.pptx
```

## How to open the dashboard
1. Install Power BI Desktop (free from Microsoft).
2. Open `dashboard/careflow.pbix`.
3. Use the slicers on each page to filter the visuals.

## Tools used
- Python and the PM4Py library for process discovery
- Microsoft Power BI Desktop and DAX for the dashboard
- LaTeX (Overleaf) for the report

## Important limitation
All time values are gaps between recorded events, not confirmed patient waiting times. Triage and diagnosis are not in the source data, so this project makes no claim about bottlenecks or clinical delays.

## Team
- Piyusha Sanjay Patil: data engineering and preparation
- Atharv Rajendra Talaskar: process mining and analysis
- Gorige Sravani: BI and dashboard development
