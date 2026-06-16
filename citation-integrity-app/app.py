"""Citation & Editorial Integrity — Streamlit app.

Upload citation and retraction CSVs (or pull retractions online) to screen
journals for citation cartels, self-citation inflation, coercive-citation risk,
and editorial-integrity problems, then download a brief report.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from integrity import cartels, coercion, loaders, report, retractions, self_citation, sources

st.set_page_config(page_title="Citation & Editorial Integrity", layout="wide")

st.title("🔎 Citation & Editorial Integrity Analyzer")
st.caption(
    "Screen journals for citation cartels, self-citation inflation, coercive "
    "citation, and retraction-based editorial-integrity problems. "
    "Findings are screening indicators, not proof of misconduct."
)

# --------------------------------------------------------------------------- #
# Sidebar: data input
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("1 · Citations data")
    st.markdown(
        "CSV with at least **citing_journal** and **cited_journal**. "
        "Optional: `year`, `count`, `citing_author`."
    )
    cit_file = st.file_uploader("Upload citations CSV", type="csv", key="cit")
    use_sample = st.checkbox("Use bundled sample data", value=False)

    st.header("2 · Retractions data")
    st.markdown("CSV with **journal** and **reason** (optional `year`, `doi`).")
    ret_file = st.file_uploader("Upload retractions CSV", type="csv", key="ret")
    fetch_rw = st.button("Fetch from Retraction Watch (online)")

    st.header("3 · Online lookup (optional)")
    oa_name = st.text_input("Look up a journal on OpenAlex")
    oa_go = st.button("Search OpenAlex")


# --------------------------------------------------------------------------- #
# Load data
# --------------------------------------------------------------------------- #
SAMPLE_DIR = "sample_data"
citations_df: pd.DataFrame | None = None
retractions_df: pd.DataFrame | None = None

try:
    if cit_file is not None:
        citations_df = loaders.load_citations(cit_file.getvalue())
    elif use_sample:
        citations_df = loaders.load_citations(f"{SAMPLE_DIR}/citations.csv")
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load citations CSV: {exc}")

try:
    if ret_file is not None:
        retractions_df = loaders.load_retractions(ret_file.getvalue())
    elif use_sample:
        retractions_df = loaders.load_retractions(f"{SAMPLE_DIR}/retractions.csv")
except Exception as exc:  # noqa: BLE001
    st.error(f"Could not load retractions CSV: {exc}")

if fetch_rw:
    with st.spinner("Downloading Retraction Watch data…"):
        res = sources.fetch_retraction_watch()
    if res.ok:
        retractions_df = loaders.load_retractions(res.data.to_csv(index=False).encode())
        st.success(res.message)
    else:
        st.warning(res.message)

if oa_go and oa_name.strip():
    with st.spinner("Querying OpenAlex…"):
        res = sources.lookup_openalex_source(oa_name.strip())
    if res.ok:
        st.subheader(f"OpenAlex results for “{oa_name}”")
        st.dataframe(res.data, use_container_width=True)
    else:
        st.warning(res.message)


# --------------------------------------------------------------------------- #
# Run analyses
# --------------------------------------------------------------------------- #
cartel_res = selfcite_res = coercion_res = retraction_res = None

if citations_df is not None and not citations_df.empty:
    cartel_res = cartels.analyze(citations_df)
    selfcite_res = self_citation.analyze(citations_df)
    coercion_res = coercion.analyze(citations_df)

if retractions_df is not None and not retractions_df.empty:
    retraction_res = retractions.analyze(retractions_df)

if citations_df is None and retractions_df is None:
    st.info(
        "⬅️ Upload a citations and/or retractions CSV to begin, or tick "
        "**Use bundled sample data** in the sidebar."
    )
    st.stop()

tabs = st.tabs(
    ["📊 Overview", "🕸️ Cartels", "🔁 Self-citation", "🧭 Coercion", "⚠️ Retractions", "📝 Report"]
)

# --- Overview --------------------------------------------------------------- #
with tabs[0]:
    cols = st.columns(4)
    cols[0].metric("Journals (citation graph)", cartel_res["n_journals"] if cartel_res else 0)
    cols[1].metric("Cartel clusters", len(cartel_res["clusters"]) if cartel_res else 0)
    cols[2].metric(
        "High self-citation", len(selfcite_res["flagged_high"]) if selfcite_res else 0
    )
    cols[3].metric(
        "Editorial-failure journals",
        len(retraction_res["flagged_editorial"]) if retraction_res else 0,
    )
    if citations_df is not None:
        st.subheader("Citations (preview)")
        st.dataframe(citations_df.head(50), use_container_width=True)
    if retractions_df is not None:
        st.subheader("Retractions (preview)")
        st.dataframe(retractions_df.head(50), use_container_width=True)

# --- Cartels ---------------------------------------------------------------- #
with tabs[1]:
    if cartel_res:
        st.subheader("Reciprocal (mutually-citing) pairs")
        pairs = pd.DataFrame(cartel_res["reciprocal_pairs"])
        st.dataframe(pairs, use_container_width=True) if not pairs.empty else st.write("None detected.")

        st.subheader("Suspected cartel clusters")
        clusters = pd.DataFrame(cartel_res["clusters"])
        st.dataframe(clusters, use_container_width=True) if not clusters.empty else st.write("None detected.")
        st.caption(
            "Clusters are strongly-connected journal groups whose citations stay "
            "largely inside the group (high internal-citation ratio)."
        )
    else:
        st.info("No citations data loaded.")

# --- Self-citation ---------------------------------------------------------- #
with tabs[2]:
    if selfcite_res:
        st.subheader("Self-citation rates")
        st.dataframe(selfcite_res["table"], use_container_width=True)
        trend = selfcite_res["trend"]
        if not trend.empty:
            st.subheader("Self-citation rate over time")
            pivot = trend.pivot_table(
                index="year", columns="journal", values="self_rate"
            )
            st.line_chart(pivot)
            if selfcite_res["flagged_spike"]:
                st.warning(
                    "Year-over-year spike flagged for: "
                    + ", ".join(selfcite_res["flagged_spike"])
                )
        else:
            st.caption("Add a `year` column to the citations CSV to see trends.")
    else:
        st.info("No citations data loaded.")

# --- Coercion --------------------------------------------------------------- #
with tabs[3]:
    if coercion_res:
        if not coercion_res["has_author_data"]:
            st.caption(
                "No `citing_author` column found — the author-spread signal is "
                "unavailable; risk relies on level and trend only."
            )
        st.subheader("Coercive-citation risk indicators")
        st.dataframe(coercion_res["table"], use_container_width=True)
        st.caption(
            "Composite of self-citation level (0.45), recent trend (0.30), and "
            "author concentration (0.25). Indicators only — not proof."
        )
    else:
        st.info("No citations data loaded.")

# --- Retractions ------------------------------------------------------------ #
with tabs[4]:
    if retraction_res:
        st.subheader("Editorial-integrity scores")
        st.dataframe(retraction_res["scores"], use_container_width=True)
        st.subheader("Retraction causes")
        st.bar_chart(pd.Series(retraction_res["cause_breakdown"]))
        with st.expander("Classified retraction records"):
            st.dataframe(retraction_res["classified"], use_container_width=True)
    else:
        st.info("No retractions data loaded. Upload a CSV or fetch from Retraction Watch.")

# --- Report ----------------------------------------------------------------- #
with tabs[5]:
    md = report.build_report(cartel_res, selfcite_res, coercion_res, retraction_res)
    st.markdown(md)
    st.download_button(
        "⬇️ Download report (Markdown)",
        data=md.encode(),
        file_name="integrity_report.md",
        mime="text/markdown",
    )
