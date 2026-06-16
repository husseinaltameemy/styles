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
import re
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


# --- Scopus export support ------------------------------------------------- #
# A Scopus document export is one row per *article* (not per citation). We turn
# it into journal-to-journal citation links: the article's source journal is the
# *citing* journal, and the journals named in its "References" field are the
# *cited* journals.
SCOPUS_REF_ALIASES = ["references", "reference", "cited references", "cited_references"]
SCOPUS_SRC_ALIASES = ["source title", "source_title", "publication name", "journal"]
SCOPUS_ABBREV_ALIASES = [
    "abbreviated source title", "abbrev source title", "abbreviated_source_title",
]
SCOPUS_YEAR_ALIASES = ["year", "publication year", "pub_year"]
SCOPUS_AUTHOR_ALIASES = ["authors", "author full names"]
# Other columns that mark a file as a Scopus article list (used for hints).
SCOPUS_HINT_COLS = {"cited by", "eid", "document type", "source title", "art. no."}


def _col_lookup(columns) -> dict[str, str]:
    return {str(c).lower().strip(): c for c in columns}


def _find_col(lookup: dict[str, str], aliases: Iterable[str]) -> str | None:
    for a in aliases:
        if a in lookup:
            return lookup[a]
    return None


def _norm_text(s) -> str:
    """Lower-case and collapse runs of non-alphanumerics to single spaces."""
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def is_scopus_export(columns) -> bool:
    """True if the file is a Scopus export carrying a References field."""
    lookup = _col_lookup(columns)
    has_ref = _find_col(lookup, SCOPUS_REF_ALIASES) is not None
    has_cited = _find_col(
        lookup, ["cited_journal", "cited journal", "cited", "target", "to_journal"]
    ) is not None
    has_src = (
        _find_col(lookup, SCOPUS_SRC_ALIASES) is not None
        or _find_col(lookup, ["citing_journal", "citing journal"]) is not None
    )
    return has_ref and has_src and not has_cited


def _looks_like_scopus_without_refs(columns) -> bool:
    lookup = _col_lookup(columns)
    hints = sum(1 for h in SCOPUS_HINT_COLS if h in lookup)
    return hints >= 2 and _find_col(lookup, SCOPUS_REF_ALIASES) is None


def load_scopus_citations(
    raw: pd.DataFrame, min_alias_len: int = 6, extra_journals: Iterable[str] | None = None
) -> pd.DataFrame:
    """Convert a Scopus document export into journal-to-journal citation links.

    For each article, the source journal is the citing journal; every journal
    from the dataset (plus any ``extra_journals``) whose name appears in that
    article's ``References`` text becomes a cited journal, weighted by how many
    times it appears. Self-citations arise naturally when the article's own
    journal appears in its references.
    """
    lookup = _col_lookup(raw.columns)
    ref_col = _find_col(lookup, SCOPUS_REF_ALIASES)
    src_col = _find_col(lookup, ["citing_journal", "citing journal"]) or _find_col(
        lookup, SCOPUS_SRC_ALIASES
    )
    if ref_col is None or src_col is None:
        raise ValueError(
            "Scopus export needs both a source-journal column (e.g. 'Source title') "
            "and a 'References' column."
        )
    abbr_col = _find_col(lookup, SCOPUS_ABBREV_ALIASES)
    year_col = _find_col(lookup, SCOPUS_YEAR_ALIASES)
    author_col = _find_col(lookup, SCOPUS_AUTHOR_ALIASES)

    work = raw.copy()
    work[src_col] = work[src_col].astype(str).str.strip()

    # Build the journal universe: each journal's full title plus its abbreviated
    # title (Scopus references usually use the abbreviation), normalized.
    universe: dict[str, set[str]] = {}

    def add_alias(journal: str, alias) -> None:
        norm = _norm_text(alias)
        if len(norm) >= min_alias_len:
            universe.setdefault(journal, set()).add(norm)

    src_i = work.columns.get_loc(src_col)
    abbr_i = work.columns.get_loc(abbr_col) if abbr_col else None
    for row in work.itertuples(index=False):
        journal = row[src_i]
        if not journal or str(journal).lower() == "nan":
            continue
        add_alias(journal, journal)
        if abbr_i is not None:
            add_alias(journal, row[abbr_i])
    for j in extra_journals or []:
        add_alias(j, j)

    patterns = {
        journal: [re.compile(r"\b" + re.escape(a) + r"\b") for a in aliases]
        for journal, aliases in universe.items()
    }

    ref_i = work.columns.get_loc(ref_col)
    year_i = work.columns.get_loc(year_col) if year_col else None
    auth_i = work.columns.get_loc(author_col) if author_col else None

    edges = []
    for row in work.itertuples(index=False):
        citing = row[src_i]
        if not citing or str(citing).lower() == "nan":
            continue
        refs = row[ref_i]
        if refs is None or (isinstance(refs, float) and pd.isna(refs)):
            continue
        text = _norm_text(refs)
        if not text:
            continue
        year = row[year_i] if year_i is not None else None
        author = row[auth_i] if auth_i is not None else None
        for cited, pats in patterns.items():
            count = 0
            for pat in pats:
                count = max(count, len(pat.findall(text)))
            if count:
                edges.append(
                    {
                        "citing_journal": str(citing).strip(),
                        "cited_journal": cited,
                        "year": year,
                        "count": count,
                        "citing_author": author,
                    }
                )

    if not edges:
        raise ValueError(
            "Read the Scopus export but found no references matching any journal "
            "in the file. Make sure the export includes the 'References' field and "
            "that it covers more than one journal."
        )

    out = pd.DataFrame(edges)
    out["count"] = pd.to_numeric(out["count"], errors="coerce").fillna(1)
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    if out["citing_author"].isna().all():
        out = out.drop(columns="citing_author")
    return out.reset_index(drop=True)


def load_citations(source, extra_journals: Iterable[str] | None = None) -> pd.DataFrame:
    """Load and validate a citations CSV.

    Accepts either a citation-link CSV (``citing_journal``/``cited_journal``) or
    a Scopus document export with a ``References`` field, which is converted to
    citation links automatically. ``extra_journals`` adds journal names to look
    for in Scopus reference text beyond those that appear as a source title.
    Returns a frame with at least ``citing_journal``, ``cited_journal`` and a
    numeric ``count`` column.
    """
    raw = _read_any(source)
    if is_scopus_export(raw.columns):
        return load_scopus_citations(raw, extra_journals=extra_journals)

    df = _normalize_headers(raw, CITATION_ALIASES)

    missing = [c for c in ("citing_journal", "cited_journal") if c not in df.columns]
    if missing:
        if _looks_like_scopus_without_refs(raw.columns):
            raise ValueError(
                "This looks like a Scopus article export, but it has no "
                "'References' column — so the journals each article cites are "
                "unknown. Re-export from Scopus with the References field "
                "included (Export → CSV → tick 'References'), then upload again."
            )
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
