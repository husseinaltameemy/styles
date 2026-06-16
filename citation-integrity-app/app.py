"""Citation & Editorial Integrity — Streamlit app.

Upload citation and retraction CSVs (or pull retractions online) to screen
journals for citation cartels, self-citation inflation, coercive-citation risk,
and editorial-integrity problems, then download a brief report.

Run with:  streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from integrity import (
    cartels,
    coercion,
    editor_citation,
    loaders,
    report,
    retractions,
    scorecard,
    self_citation,
    sources,
)


def _citation_network_figure(graph, clusters):
    """Build a Plotly network figure of the citation graph, cartels highlighted."""
    import networkx as nx
    import plotly.graph_objects as go

    if graph.number_of_nodes() == 0:
        return None

    cartel_nodes = {j for c in clusters for j in c["journals"].split(", ")}
    pos = nx.spring_layout(graph, seed=42, k=0.9)

    edge_x, edge_y = [], []
    for u, v in graph.edges():
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.6, color="#bbb"), hoverinfo="none",
    )

    node_x, node_y, text, color = [], [], [], []
    for n in graph.nodes():
        x, y = pos[n]
        node_x.append(x)
        node_y.append(y)
        text.append(n)
        color.append("#d62728" if n in cartel_nodes else "#1f77b4")
    node_trace = go.Scatter(
        x=node_x, y=node_y, mode="markers+text", text=text,
        textposition="top center", hoverinfo="text",
        marker=dict(size=16, color=color, line=dict(width=1, color="#333")),
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=520,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig

st.set_page_config(page_title="Citation & Editorial Integrity", layout="wide")

APP_VERSION = "1.3 — Editor/author citation tracing"

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
    st.caption(f"Build {APP_VERSION}")
    st.header("1 · Citations data")
    st.markdown(
        "CSV with at least **citing_journal** and **cited_journal**. "
        "Optional: `year`, `count`, `citing_author`."
    )
    st.caption(
        "Also accepts a **Scopus export** (with the *References* field): "
        "`Source title` is the citing journal and references are parsed into "
        "cited journals automatically."
    )
    cit_file = st.file_uploader("Upload citations / Scopus CSV", type="csv", key="cit")
    use_sample = st.checkbox("Use bundled sample data", value=False)
    extra_journals_raw = st.text_area(
        "Extra journals to track in references (one per line, optional)",
        help="For Scopus exports: also look for these journal names in the "
        "reference lists, even if they have no articles in your file.",
    )
    extra_journals = [j.strip() for j in extra_journals_raw.splitlines() if j.strip()]

    st.header("2 · Editor / author citation")
    st.markdown(
        "Detect a person (e.g. an **Editor-in-Chief**) citing a journal heavily "
        "in papers they publish **elsewhere**."
    )
    editor_target = st.text_input(
        "Target journal to trace citations to",
        help="The journal under scrutiny, e.g. 'Journal of Techniques'. Also add "
        "it to the 'Extra journals to track' box above so it is matched inside "
        "reference lists.",
        key="editor_target",
    )
    editor_author = st.text_input(
        "Focal author / editor name (optional)",
        help="Limit the analysis to articles authored by this person, e.g. "
        "'Smith J.'. Leave blank to rank all authors instead.",
        key="editor_author",
    )

    st.header("3 · Retractions data")
    st.markdown("CSV with **journal** and **reason** (optional `year`, `doi`).")
    ret_file = st.file_uploader("Upload retractions CSV", type="csv", key="ret")
    fetch_rw = st.button("Fetch from Retraction Watch (online)")

    st.header("4 · Online lookup (optional)")
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
        citations_df = loaders.load_citations(cit_file.getvalue(), extra_journals=extra_journals)
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

editor_res = None

if citations_df is not None and not citations_df.empty:
    cartel_res = cartels.analyze(citations_df)
    selfcite_res = self_citation.analyze(citations_df)
    coercion_res = coercion.analyze(citations_df)
    if editor_target.strip():
        editor_res = editor_citation.analyze(
            citations_df, editor_target.strip(), editor_author.strip() or None
        )

if retractions_df is not None and not retractions_df.empty:
    retraction_res = retractions.analyze(retractions_df)

if citations_df is None and retractions_df is None:
    st.info(
        "⬅️ Upload a citations and/or retractions CSV to begin, or tick "
        "**Use bundled sample data** in the sidebar."
    )
    st.stop()

scorecard_df = scorecard.build(cartel_res, selfcite_res, coercion_res, retraction_res)

tabs = st.tabs(
    [
        "🏅 Scorecard",
        "📊 Overview",
        "🕸️ Cartels",
        "🔁 Self-citation",
        "🧑‍⚖️ Editor / author",
        "🧭 Coercion",
        "⚠️ Retractions",
        "📝 Report",
    ]
)

# --- Scorecard -------------------------------------------------------------- #
with tabs[0]:
    st.subheader("Integrity scorecard")
    st.caption(
        "One row per journal, ranked by overall concern. Score blends cartel "
        "(0.30), self-citation (0.20), coercion (0.20) and retraction (0.30) "
        "signals. A screening aid — not proof of misconduct."
    )
    if scorecard_df.empty:
        st.info("Load citations and/or retractions data to build the scorecard.")
    else:
        counts = scorecard_df["concern_level"].value_counts()
        cols = st.columns(4)
        for col, level in zip(cols, ["High", "Elevated", "Watch", "Low"]):
            col.metric(level, int(counts.get(level, 0)))

        def _highlight(row):
            colors = {
                "High": "background-color: #f8d7da",
                "Elevated": "background-color: #fff3cd",
                "Watch": "background-color: #fff8e1",
                "Low": "background-color: #d4edda",
            }
            return [colors.get(row["concern_level"], "")] * len(row)

        st.dataframe(
            scorecard_df.style.apply(_highlight, axis=1),
            use_container_width=True,
        )
        st.download_button(
            "⬇️ Download scorecard (CSV)",
            data=scorecard_df.to_csv(index=False).encode(),
            file_name="integrity_scorecard.csv",
            mime="text/csv",
        )

# --- Overview --------------------------------------------------------------- #
with tabs[1]:
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
with tabs[2]:
    if cartel_res:
        st.subheader("Citation network")
        st.caption("Red nodes belong to a suspected cartel cluster; arrows are citations.")
        try:
            fig = _citation_network_figure(cartel_res["graph"], cartel_res["clusters"])
            if fig is not None:
                st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:  # noqa: BLE001
            st.caption(f"(Network graph unavailable: {exc})")

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
with tabs[3]:
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

# --- Editor / author -------------------------------------------------------- #
with tabs[4]:
    st.subheader("Editor / author citation to a target journal")
    st.caption(
        "Splits every citation **to the target journal** into *internal* (from "
        "articles in that journal) and *external* (from articles published "
        "elsewhere). A high external share concentrated in one person is a "
        "screening indicator of editor-driven citation inflation — not proof."
    )
    if editor_res is None:
        st.info(
            "Enter a **Target journal** in the sidebar (section 2) to run this "
            "analysis. Tip: also add that journal to *Extra journals to track* so "
            "its name is detected inside reference lists."
        )
    elif editor_res["target"] is None:
        st.warning(editor_res["note"])
    else:
        s = editor_res["summary"]
        who = editor_res["author"] or "all authors"
        st.markdown(
            f"Tracing citations to **{editor_res['target']}** "
            f"(author filter: *{who}*)."
        )
        badge = {"High": "🔴", "Elevated": "🟠", "Watch": "🟡", "Low": "🟢"}
        st.markdown(
            f"**Concern level: {badge.get(editor_res['level'], '')} "
            f"{editor_res['level']}**"
        )
        cols = st.columns(4)
        cols[0].metric("External papers citing it", s.get("external_papers", 0))
        cols[1].metric("External citations", s.get("external_citations", 0))
        cols[2].metric(
            "External share",
            f"{s.get('external_share', 0) * 100:.0f}%",
            help="Share of all citations to the target journal that come from "
            "articles published in *other* journals.",
        )
        cols[3].metric("Outside venues used", s.get("n_external_venues", 0))

        if not editor_res["by_author"].empty:
            st.subheader("Who cites the target journal from outside")
            st.caption(
                "Authors ranked by how often they cite the target journal in "
                "papers published elsewhere. The top name is the prime suspect "
                "for editor-style self-promotion."
            )
            st.dataframe(editor_res["by_author"], use_container_width=True)

        if not editor_res["by_venue"].empty:
            st.subheader("Outside journals used to cite the target")
            st.dataframe(editor_res["by_venue"], use_container_width=True)

        if not editor_res["by_year"].empty:
            st.subheader("External citations over time")
            st.bar_chart(editor_res["by_year"].set_index("year")["citations_to_target"])

        if s.get("internal_citations"):
            st.caption(
                f"For context: {s['internal_citations']} citation(s) to the target "
                f"came from within the target journal itself (ordinary journal "
                f"self-citation, shown on the Self-citation tab)."
            )
        st.caption(
            "Screening indicator only. Frequent citation of a leading field "
            "journal can be entirely legitimate; treat results as a prompt for "
            "a closer manual review of the flagged author's reference lists."
        )

# --- Coercion --------------------------------------------------------------- #
with tabs[5]:
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
with tabs[6]:
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
with tabs[7]:
    md = report.build_report(cartel_res, selfcite_res, coercion_res, retraction_res)
    st.markdown(md)
    st.download_button(
        "⬇️ Download report (Markdown)",
        data=md.encode(),
        file_name="integrity_report.md",
        mime="text/markdown",
    )
