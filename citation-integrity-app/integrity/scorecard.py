"""Consolidated per-journal integrity scorecard.

Combines the four individual analyses (cartels, self-citation, coercion,
retractions) into a single ranked table with one overall *concern score* and a
plain-language *concern level* per journal, so a non-specialist can read the
result at a glance.

Inputs are the result dicts returned by each analysis module's ``analyze()``
function (any of them may be ``None`` if that data wasn't supplied).
"""
from __future__ import annotations

import pandas as pd

# How much each signal contributes to the overall concern score.
WEIGHTS = {"cartel": 0.30, "self_citation": 0.20, "coercion": 0.20, "retraction": 0.30}

LEVELS = [
    (0.65, "High"),
    (0.45, "Elevated"),
    (0.25, "Watch"),
    (0.0, "Low"),
]


def _level(score: float) -> str:
    for threshold, label in LEVELS:
        if score >= threshold:
            return label
    return "Low"


def _cartel_scores(cartel: dict | None) -> dict[str, float]:
    """Map each journal to its strongest cartel signal in [0, 1]."""
    scores: dict[str, float] = {}
    if not cartel:
        return scores
    for cluster in cartel.get("clusters", []):
        for j in cluster["journals"].split(", "):
            scores[j] = max(scores.get(j, 0.0), float(cluster["cartel_score"]))
    for pair in cartel.get("reciprocal_pairs", []):
        s = float(pair["reciprocity_score"])
        for j in (pair["journal_a"], pair["journal_b"]):
            scores[j] = max(scores.get(j, 0.0), s)
    return scores


def build(
    cartel: dict | None = None,
    selfcite: dict | None = None,
    coercion: dict | None = None,
    retraction: dict | None = None,
) -> pd.DataFrame:
    """Return a ranked scorecard, one row per journal."""
    cartel_scores = _cartel_scores(cartel)

    self_rate: dict[str, float] = {}
    spike_set: set[str] = set()
    if selfcite is not None:
        tbl = selfcite["table"]
        self_rate = dict(zip(tbl["journal"], tbl["self_rate"]))
        spike_set = set(selfcite.get("flagged_spike", []))

    coercion_risk: dict[str, float] = {}
    if coercion is not None:
        ct = coercion["table"]
        coercion_risk = dict(zip(ct["journal"], ct["coercion_risk"]))

    integrity_risk: dict[str, float] = {}
    editorial_fail: dict[str, int] = {}
    if retraction is not None and not retraction["scores"].empty:
        rs = retraction["scores"]
        integrity_risk = dict(zip(rs["journal"], rs["integrity_risk"]))
        editorial_fail = dict(zip(rs["journal"], rs["editorial_failures"]))

    journals = (
        set(cartel_scores)
        | set(self_rate)
        | set(coercion_risk)
        | set(integrity_risk)
    )

    rows = []
    for j in sorted(journals):
        c = cartel_scores.get(j, 0.0)
        # Self-citation level saturates at 0.5 for the scorecard component.
        s_raw = self_rate.get(j, 0.0)
        s = min(s_raw / 0.5, 1.0)
        co = coercion_risk.get(j, 0.0)
        r = integrity_risk.get(j, 0.0)

        overall = (
            WEIGHTS["cartel"] * c
            + WEIGHTS["self_citation"] * s
            + WEIGHTS["coercion"] * co
            + WEIGHTS["retraction"] * r
        )
        flags = []
        if c >= 0.5:
            flags.append("cartel")
        if s_raw >= 0.30:
            flags.append("high self-citation")
        if j in spike_set:
            flags.append("self-citation spike")
        if co >= 0.45:
            flags.append("coercion risk")
        if editorial_fail.get(j, 0) > 0:
            flags.append("editorial failure")

        rows.append(
            {
                "journal": j,
                "concern_level": _level(overall),
                "concern_score": round(overall, 3),
                "cartel": round(c, 3),
                "self_citation_rate": round(s_raw, 3),
                "coercion_risk": round(co, 3),
                "integrity_risk": round(r, 3),
                "editorial_failures": editorial_fail.get(j, 0),
                "flags": ", ".join(flags) if flags else "—",
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    level_order = {"High": 0, "Elevated": 1, "Watch": 2, "Low": 3}
    df["_o"] = df["concern_level"].map(level_order)
    df = df.sort_values(["_o", "concern_score"], ascending=[True, False])
    return df.drop(columns="_o").reset_index(drop=True)
