# 🗺 MapaFix: Geographic Name Matcher

*Because "Muñoz" and "Munoz" shouldn't be strangers.*

A Streamlit app that matches messy location names against a clean GeoJSON or TopoJSON reference file. Matching is province-scoped, and deterministic checks run before fuzzy matching so obvious variants are resolved without silently accepting close-but-wrong names.

**Live demo:** [mapa-fix.streamlit.app](https://mapa-fix.streamlit.app/)

## Background

Location data is rarely clean. Names get typed inconsistently, diacritics like ñ get dropped, casing varies, and extra whitespace sneaks in — "Muñoz" becomes "Munoz" or "Science City of Muñoz". These small inconsistencies are enough to break a join between a dataset and a map file, which is a problem when you're trying to get a spreadsheet of locations to line up with a GeoJSON/TopoJSON file for mapping tools like Power BI's Shape Map.

A naive fuzzy match isn't enough either. It can miss obvious naming variants, and it can also confidently match a location to the wrong place when two names are similar. MapaFix tries exact and normalized matches first, then common geographic naming variants, then abbreviations. Fuzzy matching is a last step, and close scores are marked **Needs Review**.

If an input province is incomplete (for example `Ilocos` instead of `Ilocos Norte` or `Ilocos Sur`), municipality matching still runs across the plausible provinces. The municipality can resolve the location when it is unique. Competing municipalities stay in **Needs Review**.

## What it does

- **Deterministic-first matching** — exact, normalized exact, city/municipality naming variants, then abbreviations
- **Province-aware municipality matching** — a confirmed province restricts the search; an ambiguous province becomes a candidate set
- **Ambiguity detection** — similar top scores are sent to review instead of auto-accepted
- **Upload CSV/Excel + GeoJSON/TopoJSON** — match a tabular dataset directly against a map file
- **Audit output** — every row records method, status, candidates, search scope, score, and score margin
- **Clean CSV export** — download original columns plus matching results

## Requirements

- Python 3.9+

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

`streamlit run mapa-fix.py` still works as a compatibility entry point.

1. Upload a CSV/Excel file with location and parent/province columns
2. Upload a GeoJSON/TopoJSON file to match against
3. Select the relevant columns in the sidebar
4. Set the minimum fuzzy score and score-margin thresholds if needed
5. Click **Run Matching**
6. Review the summary, needs-review, and unmatched tables
7. Download the corrected dataset and the audit dataset

## Project structure

```
mapa-fix/
├── app.py              # Streamlit UI
├── mapa-fix.py         # Compatibility entry point
├── matcher.py          # Matching pipeline
├── normalizer.py       # Name cleaning and variants
├── geo_loader.py       # GeoJSON / TopoJSON loading
├── tests/              # Normalization and matching tests
└── README.md
```

## Tech stack

- [Streamlit](https://streamlit.io) — web app framework
- [GeoPandas](https://geopandas.org) — reading and handling GeoJSON/TopoJSON
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) — fuzzy string matching
- [pandas](https://pandas.org) — tabular data handling

## Tests

```bash
pytest
```

## Next steps

- **Multi-level matching** — support more than two hierarchy levels (e.g. region → province → municipality)
- **Batch file support** — match multiple CSV files against the same reference map in one run
- **Interactive review** — let users pick among close candidates from the UI

## Author

**Danz Gabriel S. Gabuat**  
BS Mathematics with Specialization in Computer Applications  
Central Luzon State University
