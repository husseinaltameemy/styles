"""Journal self-citation metrics and trend detection.

The journal self-citation rate (as used in tools like JCR) is the share of a
journal's *received* citations that come from itself:

    self_citation_rate(J) = citations(J -> J) / citations(* -> J)

We also compute the rate over time and flag journals whose self-citation share
has risen sharply, which is a common indicator of metric manipulation.
"""
from __future__ import annotations

import pandas as pd

# Above this received-self-citation share a journal is flagged (Thomson
# Reuters historically scrutinized titles above ~0.7; we use a softer default).
HIGH_RATE_THRESHOLD = 0.30
# Year-over-year jump in self-citation share that counts as a spike.
SPIKE_THRESHOLD = 0.15


def self_citation_table(citations: pd.DataFrame) -> pd.DataFrame:
    """Per-journal self-citation summary.

    Columns: journal, received_total, self_citations, self_rate,
    given_total, outward_self_rate.
    """
    received = (
        citations.groupby("cited_journal")["count"].sum().rename("received_total")
    )
    given = (
        citations.groupby("citing_journal")["count"].sum().rename("given_total")
    )
    self_mask = citations["citing_journal"] == citations["cited_journal"]
    self_cites = (
        citations[self_mask].groupby("cited_journal")["count"].sum().rename("self_citations")
    )

    journals = sorted(
        set(received.index) | set(given.index)
    )
    df = pd.DataFrame(index=journals)
    df = df.join(received).join(given).join(self_cites)
    df = df.fillna(0.0)
    df["self_rate"] = df.apply(
        lambda r: r["self_citations"] / r["received_total"] if r["received_total"] else 0.0,
        axis=1,
    )
    df["outward_self_rate"] = df.apply(
        lambda r: r["self_citations"] / r["given_total"] if r["given_total"] else 0.0,
        axis=1,
    )
    df.index.name = "journal"
    df = df.reset_index()
    df["high_self_citation"] = df["self_rate"] >= HIGH_RATE_THRESHOLD
    return df.sort_values("self_rate", ascending=False).reset_index(drop=True)


def self_citation_trend(citations: pd.DataFrame) -> pd.DataFrame:
    """Per-journal, per-year self-citation rate plus a spike flag.

    Returns an empty frame if the citations data has no ``year`` column.
    """
    if "year" not in citations.columns or citations["year"].dropna().empty:
        return pd.DataFrame(
            columns=["journal", "year", "self_rate", "received_total", "delta", "spike"]
        )

    data = citations.dropna(subset=["year"]).copy()
    data["year"] = data["year"].astype(int)

    received = (
        data.groupby(["cited_journal", "year"])["count"].sum().rename("received_total")
    )
    self_mask = data["citing_journal"] == data["cited_journal"]
    self_cites = (
        data[self_mask].groupby(["cited_journal", "year"])["count"].sum().rename("self_citations")
    )
    out = pd.concat([received, self_cites], axis=1).fillna(0.0).reset_index()
    out = out.rename(columns={"cited_journal": "journal"})
    out["self_rate"] = out.apply(
        lambda r: r["self_citations"] / r["received_total"] if r["received_total"] else 0.0,
        axis=1,
    )
    out = out.sort_values(["journal", "year"])
    out["delta"] = out.groupby("journal")["self_rate"].diff().fillna(0.0)
    out["spike"] = out["delta"] >= SPIKE_THRESHOLD
    return out.reset_index(drop=True)


def analyze(citations: pd.DataFrame) -> dict:
    table = self_citation_table(citations)
    trend = self_citation_trend(citations)
    spiking = (
        sorted(trend[trend["spike"]]["journal"].unique().tolist())
        if not trend.empty
        else []
    )
    return {
        "table": table,
        "trend": trend,
        "flagged_high": table[table["high_self_citation"]]["journal"].tolist(),
        "flagged_spike": spiking,
    }
