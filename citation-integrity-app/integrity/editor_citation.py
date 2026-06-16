"""Editor / author self-promotion via *external* venues.

Journal self-citation (see ``self_citation.py``) only sees citations a journal
makes to itself. It is blind to a subtler pattern: a person tied to a journal —
classically its Editor-in-Chief — inflating that journal's citation count by
citing it heavily in the papers they publish in *other* journals.

This module looks at every citation **to a target journal** and separates it
into *internal* (from articles published in the target journal itself) and
*external* (from articles published elsewhere). When the citing data carries an
author list (Scopus exports do), it attributes the external citations to the
authors who made them, surfacing the individuals who most consistently cite the
target journal from outside it.

All outputs are screening indicators meant to guide a closer manual look — not
proof of misconduct. A legitimate domain expert may simply cite the leading
journal in their field often.
"""
from __future__ import annotations

import re

import pandas as pd


def _norm(s) -> str:
    """Lower-case and collapse non-alphanumerics to single spaces."""
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def _split_authors(value) -> list[str]:
    """Split a Scopus-style author list (``Smith J.; Doe A.``) into names."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    parts = re.split(r"[;|]", str(value))
    return [p.strip() for p in parts if p.strip() and p.strip().lower() != "nan"]


def resolve_target(citations: pd.DataFrame, target: str) -> str | None:
    """Match ``target`` to a journal name actually present in the data.

    Case-/punctuation-insensitive; returns the canonical name as it appears in
    the citations frame, or ``None`` if no journal matches.
    """
    want = _norm(target)
    if not want:
        return None
    names = pd.unique(
        pd.concat(
            [citations["citing_journal"], citations["cited_journal"]],
            ignore_index=True,
        )
    )
    # Exact normalized match first, then a containment fallback.
    for name in names:
        if _norm(name) == want:
            return str(name)
    # Containment fallback, but only for names long enough that a substring
    # match is meaningful (avoids matching short tokens like "A" inside words).
    for name in names:
        n = _norm(name)
        if len(n) >= 4 and len(want) >= 4 and (want in n or n in want):
            return str(name)
    return None


def _level(external_share: float, external_papers: int) -> str:
    """Heuristic concern level for editor-style external self-promotion."""
    if external_papers >= 5 and external_share >= 0.5:
        return "High"
    if external_papers >= 3 and external_share >= 0.35:
        return "Elevated"
    if external_papers >= 2:
        return "Watch"
    return "Low"


def analyze(
    citations: pd.DataFrame,
    target_journal: str,
    focal_author: str | None = None,
) -> dict:
    """Analyze external citations directed at ``target_journal``.

    Parameters
    ----------
    citations:
        Citation-link frame (``citing_journal``, ``cited_journal``, ``count``,
        optional ``year`` and ``citing_author``). A Scopus export parsed by
        :func:`integrity.loaders.load_citations` provides exactly this.
    target_journal:
        The journal under scrutiny (e.g. a title whose Editor-in-Chief you
        suspect of citing it from elsewhere).
    focal_author:
        Optional author/editor name. When given, only citations from articles
        whose author list contains this name (case-insensitive substring) are
        counted, isolating that person's behaviour.

    Returns a dict with a resolved target, per-venue / per-year / per-author
    breakdowns of the *external* citations, summary metrics, and a heuristic
    concern level. ``target`` is ``None`` when the journal is not found.
    """
    target = resolve_target(citations, target_journal)
    empty = pd.DataFrame()
    if target is None:
        return {
            "target": None,
            "requested": target_journal,
            "author": focal_author,
            "has_author_data": "citing_author" in citations.columns,
            "by_venue": empty,
            "by_year": empty,
            "by_author": empty,
            "summary": {},
            "level": "Low",
            "note": (
                f"No journal matching “{target_journal}” was found in the data. "
                "Make sure the target journal is also listed under "
                "“Extra journals to track in references”, so its name is "
                "detected inside the reference lists."
            ),
        }

    has_authors = "citing_author" in citations.columns
    to_target = citations[citations["cited_journal"] == target].copy()

    if focal_author and has_authors:
        want = _norm(focal_author)
        to_target = to_target[
            to_target["citing_author"].apply(lambda a: want in _norm(a))
        ]

    to_target["count"] = pd.to_numeric(to_target["count"], errors="coerce").fillna(1)
    external = to_target[to_target["citing_journal"] != target].copy()
    internal = to_target[to_target["citing_journal"] == target].copy()

    ext_cites = float(external["count"].sum())
    int_cites = float(internal["count"].sum())
    total_cites = ext_cites + int_cites
    ext_papers = int(len(external))
    external_share = ext_cites / total_cites if total_cites else 0.0

    # Per external venue: how many of the focal/each author's papers there cite
    # the target, and how many citations in total.
    by_venue = (
        external.groupby("citing_journal")
        .agg(papers=("count", "size"), citations_to_target=("count", "sum"))
        .reset_index()
        .rename(columns={"citing_journal": "external_venue"})
        .sort_values("citations_to_target", ascending=False)
        .reset_index(drop=True)
    )

    # Per year (external only), if a usable year column exists.
    if "year" in external.columns and not external["year"].dropna().empty:
        by_year = (
            external.dropna(subset=["year"])
            .assign(year=lambda d: d["year"].astype(int))
            .groupby("year")
            .agg(papers=("count", "size"), citations_to_target=("count", "sum"))
            .reset_index()
            .sort_values("year")
            .reset_index(drop=True)
        )
    else:
        by_year = empty

    # Per author (external only): who drives the outside citations to the target.
    by_author = empty
    if has_authors and not external.empty:
        rows = []
        for rec in external.itertuples(index=False):
            cites = float(getattr(rec, "count", 1) or 1)
            for name in _split_authors(getattr(rec, "citing_author", None)):
                rows.append({"author": name, "papers": 1, "citations_to_target": cites})
        if rows:
            by_author = (
                pd.DataFrame(rows)
                .groupby("author")
                .agg(papers=("papers", "sum"), citations_to_target=("citations_to_target", "sum"))
                .reset_index()
                .sort_values(
                    ["citations_to_target", "papers"], ascending=False
                )
                .reset_index(drop=True)
            )

    level = _level(external_share, ext_papers)

    summary = {
        "external_papers": ext_papers,
        "external_citations": int(ext_cites),
        "internal_papers": int(len(internal)),
        "internal_citations": int(int_cites),
        "total_citations": int(total_cites),
        "external_share": round(external_share, 4),
        "n_external_venues": int(by_venue.shape[0]),
        "top_external_venue": by_venue["external_venue"].iloc[0] if not by_venue.empty else None,
        "top_external_author": by_author["author"].iloc[0] if not by_author.empty else None,
    }

    return {
        "target": target,
        "requested": target_journal,
        "author": focal_author or None,
        "has_author_data": has_authors,
        "by_venue": by_venue,
        "by_year": by_year,
        "by_author": by_author,
        "summary": summary,
        "level": level,
        "note": "",
    }
