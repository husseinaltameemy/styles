"""Citation-cartel detection.

A *citation cartel* is a group of journals that cite each other at unusually
high rates to inflate impact metrics. We look for two signatures:

1. **Reciprocal pairs** — A cites B *and* B cites A, where each journal sends a
   disproportionate share of its outgoing citations to the other.
2. **Cartel clusters** — strongly-connected groups of journals whose citations
   stay largely *inside* the group (high internal-citation ratio).

Self-citations (A -> A) are excluded here; they are handled by the
self-citation module.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import pandas as pd


def build_graph(citations: pd.DataFrame) -> nx.DiGraph:
    """Build a weighted directed journal-citation graph (no self-loops)."""
    agg = (
        citations.groupby(["citing_journal", "cited_journal"], as_index=False)["count"]
        .sum()
    )
    G = nx.DiGraph()
    for row in agg.itertuples(index=False):
        if row.citing_journal == row.cited_journal:
            continue
        G.add_edge(row.citing_journal, row.cited_journal, weight=float(row.count))
    return G


@dataclass
class ReciprocalPair:
    journal_a: str
    journal_b: str
    a_to_b: float
    b_to_a: float
    share_a: float  # fraction of A's outgoing citations that go to B
    share_b: float  # fraction of B's outgoing citations that go to A
    score: float

    def as_dict(self) -> dict:
        return {
            "journal_a": self.journal_a,
            "journal_b": self.journal_b,
            "a_to_b": self.a_to_b,
            "b_to_a": self.b_to_a,
            "share_a": round(self.share_a, 3),
            "share_b": round(self.share_b, 3),
            "reciprocity_score": round(self.score, 3),
        }


def reciprocal_pairs(G: nx.DiGraph, min_total: float = 2.0) -> list[ReciprocalPair]:
    """Find mutually-citing journal pairs ranked by a reciprocity score.

    The score rewards pairs where *both* journals direct a large share of their
    outgoing citations to each other, weighted by the volume involved. It lies
    in ``[0, 1]`` (volume-dampened), higher = more cartel-like.
    """
    out_strength = {n: max(G.out_degree(n, weight="weight"), 1.0) for n in G.nodes}
    pairs: list[ReciprocalPair] = []
    seen: set[tuple[str, str]] = set()

    for u, v, data in G.edges(data=True):
        if (v, u) in seen or (u, v) in seen:
            continue
        if not G.has_edge(v, u):
            continue
        seen.add((u, v))
        a_to_b = data["weight"]
        b_to_a = G[v][u]["weight"]
        if a_to_b + b_to_a < min_total:
            continue
        share_a = a_to_b / out_strength[u]
        share_b = b_to_a / out_strength[v]
        # Geometric mean of shares rewards mutual concentration; the log term
        # dampens tiny-volume pairs that can look concentrated by chance.
        import math

        volume_factor = 1 - 1 / (1 + math.log1p(a_to_b + b_to_a))
        score = (share_a * share_b) ** 0.5 * volume_factor
        pairs.append(
            ReciprocalPair(u, v, a_to_b, b_to_a, share_a, share_b, score)
        )

    pairs.sort(key=lambda p: p.score, reverse=True)
    return pairs


@dataclass
class CartelCluster:
    journals: list[str]
    internal_weight: float
    external_weight: float
    internal_ratio: float
    score: float = field(default=0.0)

    def as_dict(self) -> dict:
        return {
            "journals": ", ".join(sorted(self.journals)),
            "size": len(self.journals),
            "internal_citations": self.internal_weight,
            "external_citations": self.external_weight,
            "internal_ratio": round(self.internal_ratio, 3),
            "cartel_score": round(self.score, 3),
        }


def detect_clusters(G: nx.DiGraph, min_internal_ratio: float = 0.5) -> list[CartelCluster]:
    """Find strongly-connected groups whose citations stay inside the group.

    For each strongly-connected component with >= 2 journals we compute the
    share of the members' total outgoing citations that land on other members.
    A high ratio means the group cites itself far more than the wider field.
    """
    clusters: list[CartelCluster] = []
    for comp in nx.strongly_connected_components(G):
        if len(comp) < 2:
            continue
        members = set(comp)
        internal = 0.0
        external = 0.0
        for u in members:
            for _, v, data in G.out_edges(u, data=True):
                if v in members:
                    internal += data["weight"]
                else:
                    external += data["weight"]
        total = internal + external
        ratio = internal / total if total else 0.0
        if ratio < min_internal_ratio:
            continue
        # Smaller, tighter clusters are more suspicious than large communities.
        size_factor = 1.0 if len(members) <= 5 else 5.0 / len(members)
        clusters.append(
            CartelCluster(
                journals=sorted(members),
                internal_weight=internal,
                external_weight=external,
                internal_ratio=ratio,
                score=round(ratio * size_factor, 3),
            )
        )
    clusters.sort(key=lambda c: c.score, reverse=True)
    return clusters


def analyze(citations: pd.DataFrame) -> dict:
    """Run the full cartel analysis and return a JSON-serializable summary."""
    G = build_graph(citations)
    pairs = reciprocal_pairs(G)
    clusters = detect_clusters(G)
    return {
        "n_journals": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "reciprocal_pairs": [p.as_dict() for p in pairs],
        "clusters": [c.as_dict() for c in clusters],
        "graph": G,
    }
