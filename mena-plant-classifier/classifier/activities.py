"""Therapeutic-activity detection from record text.

Matches the :mod:`knowledge.activities` lexicon against title/abstract/keywords
and returns the canonical activity labels found, each with the surface term that
triggered it (so ``anticancer`` vs ``antitumor`` evidence is preserved even though
they share a canonical label).

A lightweight relevance ordering puts activities that appear in the **title or
keywords** ahead of those found only deep in the abstract, and the pipeline uses
the top-ranked one as the record's *primary activity*.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge.activities import ACTIVITIES
from .textutil import normalize, find_term


def _build_term_map() -> dict[str, str]:
    term_to_label: dict[str, str] = {}
    for label, terms in ACTIVITIES.items():
        for t in terms:
            term_to_label.setdefault(t.lower(), label)
    return term_to_label


_TERMS = _build_term_map()


@dataclass
class ActivityHit:
    label: str
    matched_terms: list[str] = field(default_factory=list)
    in_title_or_keywords: bool = False


def detect(title: str, abstract: str, keywords: str) -> list[ActivityHit]:
    """Detect activities, flagging those that surface in the title/keywords."""
    highlight = normalize(" . ".join([title or "", keywords or ""]))
    full = normalize(" . ".join([title or "", keywords or "", abstract or ""]))

    by_label: dict[str, ActivityHit] = {}
    for term in sorted(_TERMS, key=len, reverse=True):
        if not find_term(full, term):
            continue
        label = _TERMS[term]
        hit = by_label.setdefault(label, ActivityHit(label))
        if term not in hit.matched_terms:
            hit.matched_terms.append(term)
        if find_term(highlight, term):
            hit.in_title_or_keywords = True

    # rank: title/keyword hits first, then by number of distinct matched terms
    ranked = sorted(
        by_label.values(),
        key=lambda h: (h.in_title_or_keywords, len(h.matched_terms)),
        reverse=True,
    )
    return ranked


def summarize(hits: list[ActivityHit]) -> dict:
    return {
        "activities": [h.label for h in hits],
        "primary_activity": hits[0].label if hits else "",
        "activity_terms": {h.label: h.matched_terms for h in hits},
        "n_activities": len(hits),
    }
