"""MapaFix Streamlit UI."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from geo_loader import load_geodata
from matcher import (
    AUDIT_COLUMNS,
    STATUS_REVIEW,
    STATUS_UNMATCHED,
    match_dataset,
    results_to_records,
    summarize,
)

st.set_page_config(page_title="MapaFix", layout="wide")

if "match_results" not in st.session_state:
    st.session_state.match_results = None


def read_input_table(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    uploaded_file.seek(0)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file)
    raise ValueError("Unsupported input file type. Upload a CSV or Excel file.")


with st.sidebar:
    st.title("Matching Parameters")
    file1 = st.file_uploader("Input CSV / Excel file", type=["xlsx", "xls", "csv"])
    file2 = st.file_uploader(
        "Reference GeoJSON / TopoJSON file",
        type=["geojson", "topojson", "json"],
    )

    if file1 is not None:
        st.success("Input file uploaded.")
    if file2 is not None:
        st.success("Reference file uploaded.")

    sheet = None
    gdf = None
    location_sheet = province_sheet = location_gdf = province_gdf = None

    if file1 is not None:
        try:
            sheet = read_input_table(file1)
            location_sheet = st.selectbox(
                "Location column (input)",
                options=list(sheet.columns),
                key="input_location_col",
            )
            province_sheet = st.selectbox(
                "Parent / province column (input)",
                options=list(sheet.columns),
                key="input_parent_col",
            )
        except Exception as exc:
            st.error(f"Error reading input file: {exc}")

    if file2 is not None:
        try:
            gdf = load_geodata(file2)
            ref_columns = [col for col in gdf.columns if col != "geometry"]
            if not ref_columns:
                st.error("The reference file has no attribute columns to match against.")
            else:
                location_gdf = st.selectbox(
                    "Location column (reference)",
                    options=ref_columns,
                    key="ref_location_col",
                )
                province_gdf = st.selectbox(
                    "Parent / province column (reference)",
                    options=ref_columns,
                    key="ref_parent_col",
                )
        except Exception as exc:
            st.error(f"Error reading reference file: {exc}")
            gdf = None

    st.divider()
    min_score = st.slider(
        "Minimum fuzzy score",
        min_value=0,
        max_value=100,
        value=80,
        help="Fuzzy matches below this score are unmatched.",
    )
    min_margin = st.slider(
        "Minimum score margin",
        min_value=0,
        max_value=30,
        value=5,
        help="If the best and second-best scores are closer than this, the row needs review.",
    )
    run_button = st.button("Run Matching", use_container_width=True)

st.header("🗺 MapaFix")
st.write('Because "Muñoz" and "Munoz" shouldn\'t be strangers.')
st.write(
    "Match messy location names against a clean geographic reference dataset. "
    "MapaFix tries exact, normalized, naming-variant, and abbreviation matches first. "
    "Fuzzy matching is used only after those deterministic checks fail. "
    "If a province name is incomplete or ambiguous, municipality matching still runs "
    "across the plausible provinces instead of stopping. Close scores are marked for "
    "review instead of being accepted automatically."
)

st.divider()
col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Input preview")
    if sheet is not None:
        st.caption(file1.name)
        st.dataframe(sheet.head(50), use_container_width=True)
    else:
        st.info("Upload a CSV or Excel file in the sidebar.")

with col_b:
    st.subheader("Reference preview")
    if gdf is not None:
        st.caption(file2.name)
        preview = gdf.drop(columns=["geometry"], errors="ignore")
        st.dataframe(preview.head(50), use_container_width=True)
    else:
        st.info("Upload a GeoJSON or TopoJSON file in the sidebar.")

if run_button:
    ready = (
        file1 is not None
        and file2 is not None
        and sheet is not None
        and gdf is not None
        and location_sheet
        and province_sheet
        and location_gdf
        and province_gdf
    )
    if not ready:
        st.warning("Please upload both files and select the location and parent columns.")
    else:
        with st.spinner("Matching location names..."):
            input_rows = list(zip(sheet[location_sheet], sheet[province_sheet]))
            reference_rows = list(zip(gdf[location_gdf], gdf[province_gdf]))
            matches = match_dataset(
                input_rows,
                reference_rows,
                min_score=float(min_score),
                min_margin=float(min_margin),
            )
            audit_df = pd.DataFrame(results_to_records(matches), columns=AUDIT_COLUMNS)
            output_df = pd.concat(
                [sheet.reset_index(drop=True), audit_df.reset_index(drop=True)],
                axis=1,
            )
            st.session_state.match_results = {
                "audit_df": audit_df,
                "output_df": output_df,
                "summary": summarize(matches),
            }

results = st.session_state.match_results
if results is not None:
    summary = results["summary"]
    audit_df = results["audit_df"]
    output_df = results["output_df"]

    st.divider()
    st.subheader("Matching summary")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Total rows", summary["total_rows"])
    metric_cols[1].metric("Automatic match rate", f"{summary['automatic_matching_rate']}%")
    metric_cols[2].metric("Needs review", summary["needs_review_rows"])
    metric_cols[3].metric("Unmatched", summary["unmatched_rows"])

    detail_cols = st.columns(4)
    detail_cols[0].metric("Exact", summary["exact_matches"])
    detail_cols[1].metric("Normalized exact", summary["normalized_matches"])
    detail_cols[2].metric("Naming variant", summary["naming_variant_matches"])
    detail_cols[3].metric("Fuzzy high confidence", summary["fuzzy_matches"])

    st.subheader("Matching results")
    st.dataframe(audit_df, use_container_width=True)

    st.subheader("Matching audit")
    st.caption(
        "Every row keeps its original input values. Status, method, candidates, "
        "search scope, and score margin explain why a match was accepted or sent to review."
    )
    st.dataframe(output_df, use_container_width=True)

    needs_review_df = audit_df[audit_df["Match Status"] == STATUS_REVIEW]
    unmatched_df = audit_df[audit_df["Match Status"] == STATUS_UNMATCHED]

    st.subheader(f"Needs review ({len(needs_review_df)})")
    if needs_review_df.empty:
        st.success("No rows need review.")
    else:
        st.dataframe(needs_review_df, use_container_width=True)

    st.subheader(f"Unmatched ({len(unmatched_df)})")
    if unmatched_df.empty:
        st.success("No unmatched rows.")
    else:
        st.dataframe(unmatched_df, use_container_width=True)

    st.subheader("Downloads")
    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "Download corrected dataset (CSV)",
            data=output_df.to_csv(index=False).encode("utf-8"),
            file_name="mapafix_corrected.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with download_cols[1]:
        st.download_button(
            "Download audit dataset (CSV)",
            data=audit_df.to_csv(index=False).encode("utf-8"),
            file_name="mapafix_audit.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.success("Matching completed. Original input columns are preserved in the corrected file.")
