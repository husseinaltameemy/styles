"""Retraction-based editorial-integrity scoring.

Free-text retraction reasons (as found in the Retraction Watch database) are
classified into weighted categories. The most severe causes - paper mills,
faked/compromised peer review, and data fabrication - point to a breakdown in
the journal's editorial and peer-review process rather than isolated author
misconduct.

Each journal gets an ``integrity_risk`` score: the sum of per-retraction
severities, scaled so a single severe retraction is noticeable and repeated
severe retractions dominate.
"""
from __future__ import annotations

import re

import pandas as pd

# category -> (severity weight, list of regex keywords)
CATEGORIES: dict[str, tuple[float, list[str]]] = {
    "paper_mill": (1.0, [r"paper ?mill", r"paper factory", r"systematic manipulation"]),
    "fake_peer_review": (
        0.95,
        [r"peer.?review", r"fake review", r"rigged review", r"reviewer identit",
         r"compromised review"],
    ),
    "data_fabrication": (
        0.9,
        [r"fabricat", r"falsif", r"fake data", r"made.?up data", r"invented data"],
    ),
    "image_manipulation": (0.75, [r"image", r"figure manipulat", r"western blot", r"duplicated image"]),
    "plagiarism": (0.7, [r"plagiar", r"copied", r"text overlap", r"self.?plagiar"]),
    "ethical": (0.5, [r"ethic", r"irb", r"consent", r"animal welfare", r"approval"]),
    "duplication": (0.4, [r"duplicat", r"redundant", r"overlap", r"salami"]),
    "authorship": (0.3, [r"authorship", r"author dispute", r"ghost author", r"gift author"]),
    "error": (0.1, [r"honest error", r"genuine error", r"unintentional", r"correction"]),
}
DEFAULT_SEVERITY = 0.3  # reason present but unclassified
# Causes that specifically implicate the editorial / peer-review process.
EDITORIAL_CATEGORIES = {"paper_mill", "fake_peer_review", "data_fabrication"}


def classify_reason(reason: str) -> tuple[str, float]:
    """Return ``(category, severity)`` for a free-text reason."""
    text = (reason or "").lower()
    if not text.strip():
        return "unspecified", DEFAULT_SEVERITY
    best_cat, best_sev = "other", DEFAULT_SEVERITY
    for cat, (severity, patterns) in CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, text):
                if severity > best_sev or best_cat == "other":
                    best_cat, best_sev = cat, severity
                break
    return best_cat, best_sev


def classify(retractions: pd.DataFrame) -> pd.DataFrame:
    """Add ``category`` and ``severity`` columns to a retractions frame."""
    df = retractions.copy()
    cats = df["reason"].apply(classify_reason)
    df["category"] = [c for c, _ in cats]
    df["severity"] = [s for _, s in cats]
    df["editorial_failure"] = df["category"].isin(EDITORIAL_CATEGORIES)
    return df


def journal_scores(retractions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate classified retractions into a per-journal risk table."""
    classified = classify(retractions)
    rows = []
    for journal, grp in classified.groupby("journal"):
        n = len(grp)
        sev_sum = grp["severity"].sum()
        editorial = int(grp["editorial_failure"].sum())
        top = (
            grp["category"].value_counts().idxmax() if n else "unspecified"
        )
        # Saturating score in [0, 1]: severity sum dampened so volume matters
        # without a single outlier pinning the scale.
        risk = 1 - 1 / (1 + sev_sum)
        rows.append(
            {
                "journal": journal,
                "retractions": n,
                "severity_sum": round(sev_sum, 2),
                "editorial_failures": editorial,
                "dominant_cause": top,
                "integrity_risk": round(risk, 3),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(
        ["editorial_failures", "integrity_risk"], ascending=False
    ).reset_index(drop=True)


def analyze(retractions: pd.DataFrame) -> dict:
    classified = classify(retractions)
    scores = journal_scores(retractions)
    flagged = (
        scores[scores["editorial_failures"] > 0]["journal"].tolist()
        if not scores.empty
        else []
    )
    cause_breakdown = (
        classified["category"].value_counts().to_dict() if not classified.empty else {}
    )
    return {
        "classified": classified,
        "scores": scores,
        "flagged_editorial": flagged,
        "cause_breakdown": cause_breakdown,
    }
