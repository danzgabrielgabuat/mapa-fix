# 🗺 MapaFix: Geo Fuzzy Matcher

*Because "Muñoz City" and "Science City of Muñoz" shouldn't be strangers.*

A Streamlit app that fuzzy-matches messy location names against a clean reference map file, using province-scoped matching so a name never accidentally matches to the wrong parent province.

**Live demo:** [[ai-study-buddy-0.streamlit.app](https://mapa-fix.streamlit.app/)]

## Background

Location data is rarely clean. Names get typed inconsistently, diacritics like ñ get dropped, casing varies, and extra whitespace sneaks in — "Muñoz" becomes "Munoz" or "Science City of Muñoz". These small inconsistencies are enough to break a join between a dataset and a map file, which is a problem when you're trying to get a spreadsheet of locations to line up with a GeoJSON/TopoJSON file for mapping tools like Power BI's Shape Map.

A naive fuzzy match isn't enough either, since it can confidently match a location to the wrong region entirely if two places share a similar name across different provinces or states. MapaFix solves this by scoping the fuzzy match to only compare a location against candidates within its stated parent region, so accuracy and correctness are never traded off against each other.

## What it does

- **Region-scoped fuzzy matching** — a location is only matched against
  candidates within its stated parent region, so names never cross-match
  into the wrong province, state, or district
- **Upload CSV/Excel + GeoJSON/TopoJSON** — match a tabular dataset directly
  against a map file
- **Side-by-side preview** — inspect both the uploaded data and the reference
  map before running the match
- **Match scoring** — see the confidence score behind every match, not just
  the result
- **Clean CSV export** — download a corrected file with standardized location
  names, ready to join with mapping tools like Power BI's Shape Map

## Requirements

- Python 3.8+

## Installation

```bash
pip install streamlit pandas geopandas rapidfuzz
```

## Usage

```bash
streamlit run mapa-fix.py
```

1. Upload a CSV/Excel file with location and region columns
2. Upload a GeoJSON/TopoJSON file to match against
3. Select the relevant columns in both files
4. Click **Run Fuzzy Matching**
5. Preview the results and download the corrected CSV

## Project structure

```
mapa-fix/
├── mapa-fix.py     # Main Streamlit app
└── README.md
```

## Tech stack

- [Streamlit](https://streamlit.io) — web app framework
- [GeoPandas](https://geopandas.org) — reading and handling GeoJSON/TopoJSON
- [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) — fuzzy string matching
  (`WRatio` scorer)
- [pandas](https://pandas.pydata.org) — tabular data handling

## Next steps

- **Adjustable match threshold** — expose the fuzzy match cutoff as a UI
  control instead of a fixed value, so users can tune precision vs. recall
- **Unmatched-row review** — a dedicated view for locations that failed to
  match, with the closest candidates shown for manual resolution
- **Multi-level matching** — support more than two hierarchy levels (e.g.
  region → province → municipality) instead of a single parent/child pair
- **Batch file support** — match multiple CSV files against the same
  reference map in one run
- **Match history/session persistence** — keep previous runs available
  without re-uploading files each time

## Author

**Danz Gabriel S. Gabuat**  
BS Mathematics with Specialization in Computer Applications  
Central Luzon State University
