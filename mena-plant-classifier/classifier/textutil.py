"""Shared text-normalisation and phrase-matching helpers.

The classifiers all work by matching a curated vocabulary against the combined
title / abstract / keyword text of a record. Two subtleties matter for accuracy:

1. **Hyphen / space / concatenation equivalence.** ``anti-cancer``,
   ``anti cancer`` and ``anticancer`` must all match the same pattern. We handle
   this by normalising *both* the text and each search term into a canonical
   form where runs of non-alphanumeric characters collapse to a single space,
   then matching on whole-word boundaries.

2. **Longest-match-first.** ``Ziziphus spina-christi`` should win over the bare
   genus ``Ziziphus``. Callers that build term→label maps sort terms by length
   descending before matching so the most specific phrase is found first.
"""
from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lower-case and collapse every run of non-alphanumerics to one space.

    ``"Anti-Cancer (in-vitro)"`` -> ``" anti cancer in vitro "`` (padded so that
    boundary checks with a leading/trailing space are simple substring tests).
    """
    if not text:
        return " "
    return " " + _NON_ALNUM.sub(" ", text.lower()).strip() + " "


def find_term(norm_text: str, term: str) -> bool:
    """Whole-word containment test of ``term`` inside already-normalised text."""
    needle = " " + _NON_ALNUM.sub(" ", term.lower()).strip() + " "
    return needle in norm_text


def match_vocab(norm_text: str, term_to_label: dict[str, str]) -> list[tuple[str, str]]:
    """Return ``(label, matched_term)`` pairs for every vocabulary hit.

    ``term_to_label`` maps a surface term to the canonical label it implies.
    Terms are tried longest-first so a specific multi-word phrase is preferred,
    and once a label has been recorded via a longer phrase we still allow other
    labels to match — only exact duplicate (label, term) pairs are de-duplicated.
    """
    hits: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for term in sorted(term_to_label, key=len, reverse=True):
        if find_term(norm_text, term):
            label = term_to_label[term]
            key = (label, term)
            if key not in seen:
                seen.add(key)
                hits.append((label, term))
    return hits
