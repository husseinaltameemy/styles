"""Optional online data sources (requires network access).

Two public sources are wired up:

* **Retraction Watch** database (hosted by Crossref) — a CSV of retractions
  including free-text reasons, which feed directly into the retraction
  classifier.
* **OpenAlex** — open scholarly metadata, used to look up a journal/source and
  report basic stats.

Every function degrades gracefully: on any network/parse error it returns a
``SourceResult`` with ``ok=False`` and a human-readable message rather than
raising, so the UI keeps working offline.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

try:
    import requests
except Exception:  # pragma: no cover - requests is a declared dependency
    requests = None  # type: ignore

RETRACTION_WATCH_CSV = (
    "https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv"
)
OPENALEX_SOURCES = "https://api.openalex.org/sources"
TIMEOUT = 30


@dataclass
class SourceResult:
    ok: bool
    message: str
    data: object = None


def _require_requests() -> SourceResult | None:
    if requests is None:
        return SourceResult(False, "The 'requests' library is not installed.")
    return None


def fetch_retraction_watch(limit: int | None = None) -> SourceResult:
    """Download the Retraction Watch dataset and normalize it for the app.

    Returns a ``SourceResult`` whose ``data`` is a DataFrame with the canonical
    retraction columns (``journal``, ``reason``, ``year``, ``doi``, ``title``).
    """
    err = _require_requests()
    if err:
        return err
    try:
        resp = requests.get(RETRACTION_WATCH_CSV, timeout=TIMEOUT)
        resp.raise_for_status()
        import io

        raw = pd.read_csv(io.StringIO(resp.text), low_memory=False)
    except Exception as exc:  # noqa: BLE001 - report any failure to the UI
        return SourceResult(
            False,
            f"Could not download Retraction Watch data (network may be "
            f"restricted in this environment): {exc}",
        )

    colmap = {
        "Journal": "journal",
        "Reason": "reason",
        "RetractionDate": "year",
        "OriginalPaperDOI": "doi",
        "Title": "title",
    }
    present = {k: v for k, v in colmap.items() if k in raw.columns}
    df = raw.rename(columns=present)
    keep = [c for c in ("journal", "reason", "year", "doi", "title") if c in df.columns]
    df = df[keep].copy()
    if "year" in df.columns:
        df["year"] = (
            df["year"].astype(str).str.extract(r"(\d{4})")[0].astype("Int64")
        )
    if "reason" in df.columns:
        # RW encodes tags as "+Tag;+Tag" — make them readable for the classifier.
        df["reason"] = df["reason"].astype(str).str.replace("+", " ", regex=False)
    if limit:
        df = df.head(limit)
    return SourceResult(
        True, f"Loaded {len(df)} retraction records from Retraction Watch.", df
    )


def lookup_openalex_source(name: str) -> SourceResult:
    """Look up a journal/source on OpenAlex by name and return basic stats."""
    err = _require_requests()
    if err:
        return err
    try:
        resp = requests.get(
            OPENALEX_SOURCES,
            params={"search": name, "per-page": 5},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except Exception as exc:  # noqa: BLE001
        return SourceResult(
            False, f"OpenAlex lookup failed (network may be restricted): {exc}"
        )
    if not results:
        return SourceResult(False, f"No OpenAlex source matched '{name}'.")
    rows = [
        {
            "name": r.get("display_name"),
            "issn_l": r.get("issn_l"),
            "publisher": r.get("host_organization_name"),
            "works_count": r.get("works_count"),
            "cited_by_count": r.get("cited_by_count"),
            "openalex_id": r.get("id"),
        }
        for r in results
    ]
    return SourceResult(True, f"Found {len(rows)} OpenAlex match(es).", pd.DataFrame(rows))
