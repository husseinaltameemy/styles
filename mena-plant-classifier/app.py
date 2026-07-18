"""MENA Medicinal-Plant Publication Classifier — Streamlit app.

Upload a bibliographic export (Scopus / PubMed / Web of Science CSV, or RIS) and
the app classifies every publication by:

* **Type** — original research / review / systematic review / meta-analysis /
  clinical trial / case report / editorial …
* **Plant** — species extracted from the text, flagged as MENA (Middle
  East / North Africa) or not, with plant family.
* **Therapeutic activity** — anti-cancer, anti-tumor, anti-diabetic,
  anti-inflammatory, antimicrobial, hepatoprotective …
* **Country** — from affiliations, flagged MENA or not.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from classifier import __version__, loaders, pipeline, report

SAMPLE = os.path.join(os.path.dirname(__file__), "sample_data", "sample_publications.csv")

st.set_page_config(page_title="MENA Medicinal-Plant Classifier",
                   page_icon="🌿", layout="wide")


def _explode(series: pd.Series) -> pd.Series:
    """Split comma-separated multi-valued cells into a long value-count series."""
    values: list[str] = []
    for cell in series.fillna("").astype(str):
        values += [x.strip() for x in cell.split(",") if x.strip()]
    return pd.Series(values, dtype=str)


# ----------------------------------------------------------------- data loading
st.sidebar.title("🌿 Data")
st.sidebar.caption(f"engine v{__version__}")
use_sample = st.sidebar.checkbox("Use bundled sample data", value=True)
uploaded = st.sidebar.file_uploader("…or upload a CSV / RIS export",
                                    type=["csv", "ris", "nbib", "txt"])

df_raw = None
if uploaded is not None:
    df_raw = loaders.load(uploaded.getvalue(), uploaded.name)
    use_sample = False
elif use_sample:
    df_raw = loaders.load_csv(SAMPLE)

st.title("Medicinal-Plant Publication Classifier")
st.caption("Type · Plant (MENA provenance) · Therapeutic activity · Country — "
           "a screening tool for medicinal-plant literature.")

if df_raw is None or len(df_raw) == 0:
    st.info("⬅️ Tick **Use bundled sample data** or upload a Scopus/PubMed/WoS "
            "CSV (or a RIS file) to begin. Only a **Title** column is required; "
            "**Abstract**, **Keywords**, **Document Type** and **Affiliations** "
            "sharply improve accuracy.")
    st.stop()

with st.spinner(f"Classifying {len(df_raw)} records…"):
    df = pipeline.classify_dataframe(df_raw)

# ------------------------------------------------------------------- top metrics
n = len(df)
mena_n = int(df["mena_relevant"].sum())
c1, c2, c3, c4 = st.columns(4)
c1.metric("Records", n)
c2.metric("MENA-relevant", f"{mena_n}", f"{mena_n / n:.0%}")
c3.metric("Distinct plants", _explode(df["plants"]).nunique())
c4.metric("Distinct activities", _explode(df["activities"]).nunique())

# ---------------------------------------------------------------------- filters
st.sidebar.title("🔎 Filters")


def _multi(col, label):
    opts = sorted(_explode(df[col]).unique())
    return st.sidebar.multiselect(label, opts)


f_type = st.sidebar.multiselect("Publication type", sorted(df["pub_type"].unique()))
f_activity = _multi("activities", "Therapeutic activity")
f_plant = _multi("plants", "Plant")
f_country = st.sidebar.multiselect("Country", sorted(c for c in df["country"].unique() if c))
mena_only = st.sidebar.checkbox("MENA-relevant only", value=False)
mena_plant_only = st.sidebar.checkbox("MENA plant only", value=False)

mask = pd.Series(True, index=df.index)
if f_type:
    mask &= df["pub_type"].isin(f_type)
if f_activity:
    mask &= df["activities"].apply(lambda s: any(a in str(s).split(", ") for a in f_activity))
if f_plant:
    mask &= df["plants"].apply(lambda s: any(p in str(s).split(", ") for p in f_plant))
if f_country:
    mask &= df["country"].isin(f_country)
if mena_only:
    mask &= df["mena_relevant"]
if mena_plant_only:
    mask &= df["mena_plant"]

view = df[mask]

# ------------------------------------------------------------------------- tabs
tab_table, tab_charts, tab_report = st.tabs(["📋 Classified table", "📊 Breakdowns", "📝 Report"])

with tab_table:
    st.write(f"Showing **{len(view)}** of {n} records.")
    display_cols = ["title", "pub_type", "pub_type_confidence", "primary_activity",
                    "activities", "plants", "mena_plant", "country", "country_mena",
                    "mena_relevant", "mena_basis", "year", "source"]
    display_cols = [c for c in display_cols if c in view.columns]
    st.dataframe(view[display_cols], use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download classified CSV",
                       view.to_csv(index=False).encode("utf-8"),
                       "classified_publications.csv", "text/csv")

with tab_charts:
    a, b = st.columns(2)
    with a:
        st.subheader("Publication types")
        st.bar_chart(view["pub_type"].value_counts())
        st.subheader("Countries")
        cc = view["country"][view["country"].astype(str).str.len() > 0].value_counts()
        st.bar_chart(cc)
    with b:
        st.subheader("Therapeutic activities")
        st.bar_chart(_explode(view["activities"]).value_counts().head(15))
        st.subheader("Top plants")
        st.bar_chart(_explode(view["plants"]).value_counts().head(15))
    st.subheader("MENA relevance")
    basis = view["mena_basis"].replace("", "not MENA").value_counts()
    st.bar_chart(basis)

with tab_report:
    md = report.build_report(view)
    st.markdown(md)
    st.download_button("⬇️ Download report (Markdown)", md.encode("utf-8"),
                       "classification_report.md", "text/markdown")

st.caption("⚠️ Screening output. Every label is derived from the supplied text "
           "and curated vocabularies (≈75 MENA/global plants, 35 activity "
           "classes, country→MENA map). Spot-check before use in a review.")
