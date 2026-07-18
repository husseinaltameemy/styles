"""Country detection and MENA classification.

Resolution order (first hit wins), because explicit fields are far more reliable
than scraping free text:

1. a dedicated ``country`` column, if present;
2. the ``affiliations`` string (Scopus "Authors with affiliations" ends each
   affiliation with the country);
3. the free text (title/abstract/keywords) as a last resort.

Names, aliases (``KSA``, ``UAE``, ``Turkiye``) and adjectival forms
(``Saudi``, ``Egyptian``) are all recognised. When several countries appear we
return the full set but pick a single *primary* country — the MENA one if any,
else the first match — since most medicinal-plant studies are single-country.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge.countries import COUNTRIES
from .textutil import normalize, find_term


def _build_index() -> list[tuple[str, str, bool]]:
    """(surface term, canonical country, is_mena), longest term first."""
    rows: list[tuple[str, str, bool]] = []
    for country, meta in COUNTRIES.items():
        mena = meta["mena"]
        rows.append((country.lower(), country, mena))
        for alias in meta.get("aliases", []):
            rows.append((alias.lower(), country, mena))
        for adj in meta.get("adjectives", []):
            rows.append((adj.lower(), country, mena))
    rows.sort(key=lambda r: len(r[0]), reverse=True)
    return rows


_INDEX = _build_index()


@dataclass
class CountryResult:
    primary: str = ""
    all_countries: list[str] = field(default_factory=list)
    mena: bool = False
    source: str = ""          # which field the country came from


def _scan(text: str) -> list[str]:
    if not text:
        return []
    norm = normalize(text)
    found: list[str] = []
    for term, country, _mena in _INDEX:
        if country in found:
            continue
        if find_term(norm, term):
            found.append(country)
    return found


def detect(row) -> CountryResult:
    """Detect countries from the best-available field of a record."""
    for field_name, source in (("country", "country field"),
                               ("affiliations", "affiliations"),
                               (None, "text")):
        if field_name is None:
            text = " . ".join(str(row.get(c, "")) for c in ("title", "abstract", "keywords"))
        else:
            text = str(row.get(field_name, ""))
        countries = _scan(text)
        if countries:
            mena_hits = [c for c in countries if COUNTRIES[c]["mena"]]
            primary = mena_hits[0] if mena_hits else countries[0]
            return CountryResult(
                primary=primary,
                all_countries=countries,
                mena=bool(mena_hits),
                source=source,
            )
    return CountryResult()
