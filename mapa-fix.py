import streamlit as st
import pandas as pd
import geopandas as gpd
from rapidfuzz import process, fuzz

st.set_page_config(layout="wide")

with st.sidebar:
    st.title("Matching Parameters")
    file1 = st.file_uploader("Upload csv/excel file", type=["xlsx", "xls", "csv"])
    file2 = st.file_uploader("Upload geoJSON/topoJSON file", type=["geojson", "topojson", "json"])

    if file1 is not None:
        st.badge(label="CSV/Excel file uploaded successfully.", icon="✅", color="green")
        
    if file2 is not None:
        st.badge(label="Spatial data file uploaded successfully.", icon="✅", color="green")

    st.divider()
    run_button = st.button("Run Fuzzy Matching", use_container_width=True, )

st.header("🗺 MapaFix")
st.write(
    "Because \"Muñoz\" and \"Munoz\" shouldn't be strangers."
)
st.write(
    "Match messy location names against a clean reference dataset. It resolves "
    "typos, formatting differences, and naming inconsistencies using region-scoped "
    "fuzzy matching, so a name never accidentally matches to the wrong parent region."
)
st.write(
    "Upload a CSV/Excel file with location and region columns, plus a GeoJSON or "
    "TopoJSON map file to match against. Preview both side by side, run the match, "
    "and download a corrected CSV with clean, standardized location names, ready to "
    "join with mapping tools like Power BI's Shape Map."
)
st.divider()

col_a, col_b = st.columns(2)

with col_a:

    sheet = None
    if file1 is not None:

        if file1.name.endswith(".csv"):
            try:
                sheet = pd.read_csv(file1)
                with st.expander("CSV File Preview"):
                    st.subheader("CSV File Preview")
                    with st.spinner("Reading CSV file...", show_time=True):
                        st.write(file1.name)
                        st.dataframe(sheet)

            except Exception as e:
                st.error(f"Error reading CSV file: {e}")
        if file1.name.endswith(".xlsx") or file1.name.endswith(".xls"):
            try:
                sheet = pd.read_excel(file1)
                with st.expander("Excel File Preview"):
                    st.subheader("Excel File Preview")
                    with st.spinner("Reading Excel file...", show_time=True):
                        st.write(file1.name)
                        st.dataframe(sheet)
            except Exception as e:
                st.error(f"Error reading Excel file: {e}")

        if sheet is not None:
            col1, col2 = st.columns(2)
            with col1:
                location_sheet = st.selectbox("Select the column containing location names", options=sheet.columns)
            with col2:
                province_sheet = st.selectbox("Select the column containing province names", options=sheet.columns)

    gdf = None
    if file2 is not None:

        try:
            gdf = gpd.read_file(file2)
            with st.expander("geoJSON/topoJSON File Preview"):
                st.subheader("geoJSON/topoJSON File Preview")
                with st.spinner("Reading geoJSON/topoJSON file...", show_time=True):
                    st.write(file2.name)
                    st.dataframe(gdf)

        except Exception as e:
            st.error(f"Error reading geoJSON file: {e}")
        pass

        if gdf is not None:
                col3, col4 = st.columns(2)
                with col3:
                    location_gdf = st.selectbox("Select the column containing location names", options=gdf.columns)
                with col4:
                    province_gdf = st.selectbox("Select the column containing province names", options=gdf.columns)

def get_province_candidates(gdf, province_name, province_col):
    return gdf[gdf[province_col] == province_name]

SCORERS = [
    ("token_set_ratio", fuzz.token_set_ratio),
    ("token_sort_ratio", fuzz.token_sort_ratio),
    ("WRatio", fuzz.WRatio),
]

def match_municipality(gdf, location_name, province_name, location_col, province_col, threshold=60.0):
    candidates = get_province_candidates(gdf, province_name, province_col)
    if candidates.empty:
        return None, None, None
    names = candidates[location_col].tolist()

    for scorer_name, scorer_func in SCORERS:
        match = process.extractOne(location_name, names, scorer=scorer_func, score_cutoff=threshold)
        if match is not None:
            _, score, idx = match
            return candidates.iloc[idx], score, scorer_name

    return None, None, None

if run_button:
    if file1 is not None and file2 is not None and sheet is not None and gdf is not None:
        matched_locations = []
        matched_provinces = []
        results = []
        unmatched_rows = []
        for loc, prov in zip(sheet[location_sheet], sheet[province_sheet]):
            matched_row, score, scorer_used = match_municipality(gdf, loc, prov, location_gdf, province_gdf, threshold=60.0)

            if matched_row is not None:
                matched_locations.append(matched_row[location_gdf])
                matched_provinces.append(matched_row[province_gdf])
            else:
                # if no match found, keep the original values instead of overwriting with None
                matched_locations.append(loc)
                matched_provinces.append(prov)
                unmatched_rows.append({
                    "Input Location": loc,
                    "Input Province": prov,
                })

            results.append({
                "Input Location": loc,
                "Input Province": prov,
                "Matched Location": matched_row[location_gdf] if matched_row is not None else None,
                "Matched Province": matched_row[province_gdf] if matched_row is not None else None,
                "Match Score": score,
                "Match Method": scorer_used if scorer_used is not None else "No match"
            })
        with col_b:
            with st.spinner("Performing fuzzy matching...", show_time=True):
                results_df = pd.DataFrame(results)
                with st.expander("View Matching Results"):
                    st.subheader("Matching Results")
                    st.dataframe(results_df)

                output_sheet = sheet.copy()
                output_sheet[location_sheet] = matched_locations
                output_sheet[province_sheet] = matched_provinces

                with st.expander("Download New Matched CSV File"):
                    st.subheader("New Matched CSV File")
                    st.dataframe(output_sheet)

                    csv = output_sheet.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download the new CSV file here!",
                        data=csv,
                        file_name='matched_results.csv',
                        mime='text/csv',
                    )

                if unmatched_rows:
                    unmatched_df = pd.DataFrame(unmatched_rows)
                    with st.expander(f"⚠️ Unmatched Rows ({len(unmatched_df)})"):
                        st.subheader("Unmatched Rows")
                        st.write(
                            "These rows had no match above the score threshold within their "
                            "stated region, so their original values were kept as-is in the "
                            "output file. Review them for typos or provinces/regions missing "
                            "from the map file."
                        )
                        st.dataframe(unmatched_df)

                        unmatched_csv = unmatched_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Download unmatched rows as CSV",
                            data=unmatched_csv,
                            file_name='unmatched_rows.csv',
                            mime='text/csv',
                        )

                st.success("Fuzzy matching completed successfully.", icon="✅")

    else:
        st.warning("Please check the sidebar and upload files first.")