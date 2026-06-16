"""CSV loading and column normalization.

Two input datasets are supported:

1. **Citations** — one row per citation edge (or aggregated with a ``count``):
   required: ``citing_journal``, ``cited_journal``
   optional: ``year``, ``count`` (defaults to 1), ``citing_author``,
   ``cited_author``

2. **Retractions** — one row per retracted paper:
   required: ``journal``, ``reason``
   optional: ``year``, ``doi``, ``title``

Real-world exports use many different header names, so we map a generous set
of aliases onto the canonical column names above.
"""
from __future__ import annotations

import io
from typing import Iterable

import pandas as pd

# Canonical column -> accepted aliases (all compared lower-cased / stripped).
CITATION_ALIASES = {
    "citing_journal": [
        "citing_journal", "citing journal", "source", "source_journal",
        "from", "from_journal", "citing", "citing_source", "citing_venue",
    ],
    "cited_journal": [
        "cited_journal", "cited journal", "target", "target_journal",
        "to", "to_journal", "cited", "cited_source", "cited_venue",
    ],
    "year": ["year", "citing_year", "pub_year", "publication_year"],
    "count": ["count", "weight", "n", "citations", "num", "frequency", "freq"],
    "citing_author": ["citing_author", "author", "citing author", "from_author"],
    "cited_author": ["cited_author", "cited author", "to_author"],
}

RETRACTION_ALIASES = {
    "journal": ["journal", "source", "venue", "journal_name", "journal title"],
    "reason": [
        "reason", "reasons", "cause", "causes", "retraction_reason",
        "retractionnature", "notes", "description",
    ],
    "year": ["year", "retraction_year", "retractionyear", "pub_year"],
    "doi": ["doi", "originalpaperdoi", "original_doi"],
    "title": ["title", "paper_title", "article_title"],
}


def _normalize_headers(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    """Rename columns to canonical names using ``alias_map``."""
    lookup = {}
    for canonical, aliases in alias_map.items():
        for a in aliases:
            lookup[a.lower().strip()] = canonical
    renamed = {}
    for col in df.columns:
        key = str(col).lower().strip()
        if key in lookup:
            renamed[col] = lookup[key]
    return df.rename(columns=renamed)


def _read_any(source) -> pd.DataFrame:
    """Read a CSV from a path, file-like object, or raw bytes/str."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    elif isinstance(source, str) and ("\n" in source or "," in source) and not source.endswith(".csv"):
        source = io.StringIO(source)
    return pd.read_csv(source)


def load_citations(source) -> pd.DataFrame:
    """Load and validate a citations CSV.

    Returns a frame with at least ``citing_journal``, ``cited_journal`` and a
    numeric ``count`` column. ``year`` is preserved when present.
    """
    df = _normalize_headers(_read_any(source), CITATION_ALIASES)

    missing = [c for c in ("citing_journal", "cited_journal") if c not in df.columns]
    if missing:
        raise ValueError(
            "Citations file is missing required column(s): "
            f"{', '.join(missing)}. Found columns: {list(df.columns)}"
        )

    df["citing_journal"] = df["citing_journal"].astype(str).str.strip()
    df["cited_journal"] = df["cited_journal"].astype(str).str.strip()

    if "count" not in df.columns:
        df["count"] = 1
    df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(1)

    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # Drop blank journal rows.
    df = df[(df["citing_journal"] != "") & (df["cited_journal"] != "")]
    return df.reset_index(drop=True)


def load_retractions(source) -> pd.DataFrame:
    """Load and validate a retractions CSV."""
    df = _normalize_headers(_read_any(source), RETRACTION_ALIASES)

    if "journal" not in df.columns:
        raise ValueError(
            "Retractions file is missing required 'journal' column. "
            f"Found columns: {list(df.columns)}"
        )
    if "reason" not in df.columns:
        df["reason"] = ""

    df["journal"] = df["journal"].astype(str).str.strip()
    df["reason"] = df["reason"].fillna("").astype(str)
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    df = df[df["journal"] != ""]
    return df.reset_index(drop=True)


def journals_in(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    """Unique sorted journal names across the given columns."""
    names: set[str] = set()
    for c in columns:
        if c in df.columns:
            names.update(df[c].dropna().astype(str).str.strip())
    names.discard("")
    return sorted(names)
