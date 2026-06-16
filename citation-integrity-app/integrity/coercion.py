"""Heuristics for coercive / editor-pressured self-citation.

Coercive citation is when a journal's editors pressure authors to add citations
to that same journal during review. It cannot be *proven* from citation counts
alone, so this module produces **risk indicators**, not verdicts. The composite
risk score blends three observable signatures:

* **Level**   - the journal's overall self-citation rate is high.
* **Trend**   - that rate has recently jumped (consistent with a new policy).
* **Spread**  - many *different* citing authors funnel an outsized share of
  their references into this one journal (only available when the citations CSV
  carries a ``citing_author`` column).

Each component is scaled to ``[0, 1]`` and combined with transparent weights.
"""
from __future__ import annotations

import pandas as pd

from . import self_citation

WEIGHTS = {"level": 0.45, "trend": 0.30, "spread": 0.25}
RISK_FLAG_THRESHOLD = 0.45
# An author is "directed" at a journal if that journal receives at least this
# share of the author's outgoing citations.
AUTHOR_CONCENTRATION = 0.5


def _level_component(table: pd.DataFrame) -> pd.Series:
    """Map self-citation rate onto [0, 1] (saturating at 0.5)."""
    return (table["self_rate"] / 0.5).clip(upper=1.0)


def _trend_component(citations: pd.DataFrame, journals: list[str]) -> pd.Series:
    trend = self_citation.self_citation_trend(citations)
    if trend.empty:
        return pd.Series(0.0, index=journals)
    peak = trend.groupby("journal")["delta"].max().clip(lower=0.0)
    # A +0.25 year-over-year jump saturates the component.
    return (peak / 0.25).clip(upper=1.0).reindex(journals).fillna(0.0)


def _spread_component(citations: pd.DataFrame, journals: list[str]) -> pd.Series:
    """Fraction of authors who funnel >= AUTHOR_CONCENTRATION of their cites to J."""
    if "citing_author" not in citations.columns:
        return pd.Series(0.0, index=journals)

    data = citations.dropna(subset=["citing_author"]).copy()
    data["citing_author"] = data["citing_author"].astype(str).str.strip()
    data = data[data["citing_author"] != ""]
    if data.empty:
        return pd.Series(0.0, index=journals)

    author_total = data.groupby("citing_author")["count"].sum()
    author_journal = data.groupby(["cited_journal", "citing_author"])["count"].sum()
    share = author_journal / author_total
    directed = share[share >= AUTHOR_CONCENTRATION]

    # Distinct authors per journal (directed) over distinct authors citing it.
    counts = directed.reset_index().groupby("cited_journal")["citing_author"].nunique()
    citing_authors = data.groupby("cited_journal")["citing_author"].nunique()
    spread = (counts / citing_authors).reindex(journals).fillna(0.0)
    return spread.clip(upper=1.0)


def analyze(citations: pd.DataFrame) -> dict:
    table = self_citation.self_citation_table(citations).set_index("journal")
    journals = table.index.tolist()

    level = _level_component(table)
    trend = _trend_component(citations, journals)
    spread = _spread_component(citations, journals)

    risk = (
        WEIGHTS["level"] * level
        + WEIGHTS["trend"] * trend
        + WEIGHTS["spread"] * spread
    )

    out = pd.DataFrame(
        {
            "journal": journals,
            "self_rate": table["self_rate"].values,
            "level_component": level.round(3).values,
            "trend_component": trend.round(3).values,
            "spread_component": spread.round(3).values,
            "coercion_risk": risk.round(3).values,
        }
    )
    out["flag"] = out["coercion_risk"] >= RISK_FLAG_THRESHOLD
    out = out.sort_values("coercion_risk", ascending=False).reset_index(drop=True)
    return {
        "table": out,
        "flagged": out[out["flag"]]["journal"].tolist(),
        "has_author_data": "citing_author" in citations.columns,
    }
