import json
from datetime import datetime, UTC
from pathlib import Path

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

# ----------------------
# Files
# ----------------------

DATA_FILE = Path("gm_sota_data.json")
MUNROS_FILE = Path("munros.json")
NON_SOTA_MUNROS_FILE = Path("non-sota-munros.json")
CORBETTS_FILE = Path("corbetts.csv")
CAIRNGORMS_FILE = Path("cairngorms_summits.csv")

# ----------------------
# Page config
# ----------------------

st.set_page_config(
    page_title="GM SOTA Activations",
    page_icon="🏔️",
    layout="wide"
)

st.title("🏔️ GM SOTA Activations")
st.caption("👈 Change filters in the sidebar to see different years and hills")
# ----------------------
# Data loading
# ----------------------

@st.cache_data
def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

@st.cache_data
def load_csv(path: Path):
    return pd.read_csv(path)

# ----------------------
# Build activation dataframe
# ----------------------

@st.cache_data
def build_activation_dataframe(data):
    rows = []

    for region in data["regions"].values():
        for summit_entry in region["summits"].values():
            summit = summit_entry["summit"]

            for act in summit_entry["activations"]:
                rows.append({
                    "userId": act["userId"],
                    "Callsign": act.get("Callsign"),
                    "activationDate": act["activationDate"],
                    "year": int(act["activationDate"][:4]),
                    "summitCode": summit["summitCode"],
                    "name": summit["name"],
                    "points": summit["points"],
                    "latitude": summit["latitude"],
                    "longitude": summit["longitude"],
                })

    return pd.DataFrame(rows)

# ----------------------
# Load all data
# ----------------------

raw_data = load_json(DATA_FILE)
df = build_activation_dataframe(raw_data)

munros = pd.DataFrame(load_json(MUNROS_FILE))
non_sota_munros = pd.DataFrame(load_json(NON_SOTA_MUNROS_FILE))
corbetts = load_csv(CORBETTS_FILE)
cairngorms = load_csv(CAIRNGORMS_FILE)

# ----------------------
# Canonical summit datasets
# ----------------------

# All SOTA GM summits
all_sota_summits = (
    df[["summitCode", "name", "latitude", "longitude", "points"]]
    .drop_duplicates(subset=["summitCode"])
)

# Munros (SOTA)
sota_munros = (
    munros
    .rename(columns={
        "reference": "summitCode",
        "lat": "latitude",
        "lon": "longitude",
        "Points": "points"
    })[["summitCode", "name", "latitude", "longitude", "points"]]
)

# Corbetts (all SOTA)
corbetts = (
    corbetts
    .rename(columns={
        "SummitCode": "summitCode",
        "SummitName": "name",
        "Latitude": "latitude",
        "Longitude": "longitude",
        "Points": "points"
    })[["summitCode", "name", "latitude", "longitude", "points"]]
)

# Cairngorms NP
cairngorms = (
    cairngorms
    .rename(columns={
        "summitCode": "summitCode",
        "name": "name",
        "latitude": "latitude",
        "longitude": "longitude",
        "points": "points"
    })[["summitCode", "name", "latitude", "longitude", "points"]]
)

# ----------------------
# Filters
# ----------------------

current_year = datetime.now(UTC).year
years = sorted(df["year"].unique(), reverse=True)
year_options = ["ALL"] + years

# Work out default index
if current_year in years:
    default_year_index = year_options.index(current_year)
else:
    default_year_index = 0  # ALL

with st.sidebar:
    st.header("Filters")
    st.caption("Changes apply instantly")

    selected_year = st.selectbox(
        "Year",
        year_options,
        index=default_year_index
    )

    hillset = st.selectbox(
        "Hill set",
        [
            "All Scotland",
            "Region GM/ES",
            "Region GM/WS",
            "Region GM/NS",
            "Region GM/CS",
            "Region GM/SS",
            "Region GM/SI",
            "Munros",
            "Corbetts",
            "Cairngorms National Park"
        ]
    )


# ----------------------
# Year filter
# ----------------------

if selected_year == "ALL":
    df_year = df.copy()
else:
    df_year = df[df["year"] == selected_year]

# ----------------------
# Hillset summit catalogue
# ----------------------

if hillset == "All Scotland":
    summits_df = all_sota_summits.copy()

elif hillset.startswith("Region"):
    code = hillset.split("/")[-1]
    summits_df = all_sota_summits[
        all_sota_summits["summitCode"].str.startswith(f"GM/{code}")
    ]

elif hillset == "Munros":
    summits_df = sota_munros.copy()

elif hillset == "Corbetts":
    summits_df = corbetts.copy()

elif hillset == "Cairngorms National Park":
    summits_df = cairngorms.copy()

hillset_codes = set(summits_df["summitCode"].dropna())

df_hillset = df[df["summitCode"].isin(hillset_codes)]

# ----------------------
# Activator summary table
# ----------------------

summary = (
    df_year[df_year["summitCode"].isin(summits_df["summitCode"].dropna())]
    .drop_duplicates(subset=["userId", "summitCode"])
    .groupby(["userId", "Callsign"])
    .size()
    .reset_index(name="Summits Activated")
    .sort_values("Summits Activated", ascending=False)
)

total_summits = len(summits_df)

summary["% Complete"] = (summary["Summits Activated"] / total_summits * 100).round(0)

st.subheader("Summits activated by activator")

col_left, col_right = st.columns([0.7, 0.3])

with col_left:
    table_event = st.dataframe(
        summary.drop(columns="userId"),
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        width="stretch"
    )

with col_right:
    st.metric("Total Summits Activated", int(summary["Summits Activated"].sum()), border=True)
    st.metric("Total Activators", summary["Callsign"].nunique(), border=True)

# ----------------------
# Selected activator
# ----------------------

selected_callsign = None
if table_event and table_event.selection.rows:
    selected_callsign = summary.iloc[table_event.selection.rows[0]]["Callsign"]

# ----------------------
# Maps
# ----------------------

st.subheader("Maps")

if selected_callsign:
    st.markdown(f"**Selected activator:** `{selected_callsign}`")

    df_call = (
        df_year[
            (df_year["Callsign"] == selected_callsign) &
            (df_year["summitCode"].isin(summits_df["summitCode"].dropna()))
        ]
        .drop_duplicates(subset=["summitCode"])
    )

    # ---- Activated map
    m1 = folium.Map(location=[56.8, -4.2], zoom_start=7, tiles="OpenTopoMap")

    for _, r in df_call.iterrows():

        popup = f"""
        <b>{r['name']}</b><br>
        {"<a href='https://sotl.as/summits/" + r['summitCode'] + "' target='_blank'>" + r['summitCode'] + "</a><br>" if pd.notna(r.get("summitCode")) else ""}
        Points: {r.get('points', '—')}
        """

        tooltip = r["name"]

        points = r.get("points")

        color = (
            "lightgreen" if points == 1 else
            "green" if points == 2 else
            "darkgreen" if points == 4 else
            "orange" if points == 6 else
            "darkred" if points == 8 else
            "red"
        )

        folium.Marker(
            [r["latitude"], r["longitude"]],
            popup=popup,
            tooltip=tooltip,
            icon=folium.Icon(color=color)
        ).add_to(m1)

    st.markdown("### Activated summits")
    st_folium(m1, width="stretch", returned_objects=[])

    # ---- Unactivated map

    st.subheader("Unactivated summits")
    st.info("Unactivated summits map is only available when ALL years are selected.")

    if selected_year == "ALL" and selected_callsign:


        activated_codes = set(df_call["summitCode"].dropna())
        unactivated = summits_df[~summits_df["summitCode"].isin(activated_codes)]


        m2 = folium.Map(location=[56.8, -4.2], zoom_start=7, tiles="OpenTopoMap")

        for _, r in unactivated.iterrows():

            popup = f"""
            <b>{r['name']}</b><br>
            {"<a href='https://sotl.as/summits/" + r['summitCode'] + "' target='_blank'>" + r['summitCode'] + "</a><br>" if pd.notna(r.get("summitCode")) else ""}
            Points: {r.get('points', '—')}
            """

            tooltip = r["name"]

            points = r.get("points")

            color = (
                "lightgreen" if points == 1 else
                "green" if points == 2 else
                "darkgreen" if points == 4 else
                "orange" if points == 6 else
                "darkred" if points == 8 else
                "red"
            )

            folium.Marker(
                [r["latitude"], r["longitude"]],
                popup=popup,
                tooltip=tooltip,
                icon=folium.Icon(color=color)
            ).add_to(m2)


        if hillset == "Munros":
            for _, row in non_sota_munros.iterrows():
                popup = f"<b>{row['name']}</b><br>Elevation: {row['Elevation']} m"

                folium.CircleMarker(
                    location=[row["lat"], row["lon"]],
                    popup=popup,
                    tooltip=row["name"],
                    radius=5,
                    color="grey",
                    fill=True,
                    fill_color="grey",
                    fill_opacity=0.6,
                ).add_to(m2)

        st_folium(m2, width="stretch", returned_objects=[])

else:
    st.info("Select an activator from the table to see maps.")

# ----------------------
# Historical section
# ----------------------

st.header("Historical Annual Data")

historical = (
    df_hillset
    .drop_duplicates(subset=["userId", "summitCode", "year"])
    .groupby(["year", "Callsign"])
    .size()
    .reset_index(name="Summits")
)

top_per_year = (
    historical
    .sort_values(["year", "Summits"], ascending=[True, False])
    .groupby("year")
    .head(1)
    .sort_values("year", ascending=False)
    .rename(columns={"year": "Year"})
)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top activator per year")
    st.dataframe(top_per_year, hide_index=True)

with col2:
    yearly_totals = (
        df_hillset
        .drop_duplicates(subset=["userId", "summitCode", "year"])
        .groupby("year")
        .size()
        .reset_index(name="Total Activations")
    )

    st.subheader("Total activations per year")
    st.bar_chart(yearly_totals.set_index("year"))

# ----------------------
# Footer
# ----------------------

st.caption(
    f"Data generated nightly • Last update: {raw_data['generated_at']}"
)
