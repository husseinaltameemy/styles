"""Load bibliographic exports and normalise their columns.

Supports the record shapes produced by the major databases used for
medicinal-plant reviews:

* **Scopus CSV** — ``Title``, ``Abstract``, ``Author Keywords``,
  ``Index Keywords``, ``Document Type``, ``Authors with affiliations``, ``Year``…
* **PubMed / Web of Science CSV** — similar fields under different headers.
* **Plain CSV** — any file with at least a title column.
* **RIS** — the tagged ``TY/TI/AB/KW/...`` format exported by reference managers.

Every source uses different header spellings, so a generous alias table maps them
onto a small set of canonical columns. Only ``title`` is truly required; the more
of ``abstract`` / ``keywords`` / ``document_type`` / ``affiliations`` / ``country``
are present, the higher the classification accuracy.
"""
from __future__ import annotations

import io
import re

import pandas as pd

# canonical column -> accepted header aliases (compared lower-cased/stripped)
COLUMN_ALIASES: dict[str, list[str]] = {
    "title": ["title", "article title", "document title", "ti"],
    "abstract": ["abstract", "abstract note", "ab", "description"],
    "keywords": ["author keywords", "index keywords", "keywords", "kw",
                 "author/keyword", "de", "id"],
    "document_type": ["document type", "doctype", "publication type", "type",
                      "reference type", "ty", "type of publication"],
    "authors": ["authors", "author", "author full names", "au", "author(s)"],
    "affiliations": ["affiliations", "authors with affiliations", "affiliation",
                     "author address", "addresses", "c1", "reprint address"],
    "country": ["country", "countries", "country/region", "correspondence country"],
    "year": ["year", "publication year", "py", "date"],
    "source": ["source title", "source", "journal", "publication name", "jo", "t2"],
    "doi": ["doi", "di", "digital object identifier"],
}

# RIS tag -> canonical column (multi-valued tags are joined with "; ")
RIS_TAGS = {
    "TI": "title", "T1": "title",
    "AB": "abstract", "N2": "abstract",
    "KW": "keywords",
    "TY": "document_type",
    "AU": "authors", "A1": "authors",
    "AD": "affiliations",
    "PY": "year", "Y1": "year",
    "JO": "source", "JF": "source", "T2": "source",
    "DO": "doi",
}


def _canonical_map(headers) -> dict[str, str]:
    """Map each incoming header to its canonical name (first alias wins)."""
    lookup = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            lookup[alias] = canonical
    out = {}
    for h in headers:
        key = str(h).strip().lower()
        if key in lookup and lookup[key] not in out.values():
            out[h] = lookup[key]
    return out


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename recognised columns to canonical names and guarantee the core set."""
    df = df.rename(columns=_canonical_map(df.columns))
    for col in ("title", "abstract", "keywords", "document_type",
                "authors", "affiliations", "country", "year", "source", "doi"):
        if col not in df.columns:
            df[col] = ""
    df = df.fillna("")
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip()
    return df


def load_csv(data) -> pd.DataFrame:
    """Load a CSV path / file-like / bytes into a normalised dataframe."""
    if isinstance(data, bytes):
        data = io.BytesIO(data)
    df = pd.read_csv(data, dtype=str, keep_default_na=False)
    return normalize_columns(df)


def load_ris(text: str) -> pd.DataFrame:
    """Parse RIS text into a normalised dataframe (one row per ``TY``…``ER`` block)."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    records: list[dict] = []
    current: dict[str, list[str]] = {}
    line_re = re.compile(r"^([A-Z][A-Z0-9])  - (.*)$")
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.strip() == "ER  -" or line.strip().startswith("ER  -"):
            if current:
                records.append({k: "; ".join(v) for k, v in current.items()})
            current = {}
            continue
        m = line_re.match(line)
        if not m:
            continue
        tag, value = m.group(1), m.group(2).strip()
        col = RIS_TAGS.get(tag)
        if col and value:
            current.setdefault(col, []).append(value)
    if current:
        records.append({k: "; ".join(v) for k, v in current.items()})
    df = pd.DataFrame(records)
    return normalize_columns(df)


def load(data, filename: str = "") -> pd.DataFrame:
    """Dispatch on file extension: ``.ris``/``.txt`` -> RIS, else CSV."""
    name = filename.lower()
    if name.endswith(".ris") or name.endswith(".nbib"):
        text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
        return load_ris(text)
    return load_csv(data)


def record_text(row) -> str:
    """Concatenate the searchable free-text fields of a record."""
    parts = [str(row.get(c, "")) for c in ("title", "abstract", "keywords")]
    return " . ".join(p for p in parts if p)
