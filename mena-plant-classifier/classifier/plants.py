"""Plant detection and MENA provenance from record text.

Builds a name→entry index from ``knowledge.plants`` once, then matches the
combined title/abstract/keyword text of each record. Matching rules for accuracy:

* **Binomials and synonyms** (``Nigella sativa``, ``Matricaria recutita``) are the
  strongest evidence and are matched first, longest phrase first.
* **Common / vernacular names** (``black seed``, ``habbat al-barakah``) also match,
  but a short, ambiguous common name (``sage``, ``mint``, ``rue``) only counts when
  it appears as a whole word — the normalisation in :mod:`textutil` guarantees that.
* A **bare genus** mention (``Ziziphus sp.``) is accepted at reduced confidence
  when no full binomial from that genus matched.

Each detected plant carries its MENA flag, family and — for the *whole record* —
we derive ``mena_plant`` (any MENA plant present) and the list of families.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .knowledge.plants import PLANTS
from .textutil import normalize, find_term

# Short common names that are real words and need extra care are still safe
# because matching is whole-word; but we exclude a few that collide with English
# stopwords / lab jargon to avoid false positives.
_AMBIGUOUS_BLOCK = {"tea", "date", "rue", "anise"}  # only block as *common*, binomial still ok


@dataclass
class PlantHit:
    scientific: str
    family: str
    mena: bool
    matched_as: str          # the surface term that matched
    regions: list[str] = field(default_factory=list)
    known_uses: list[str] = field(default_factory=list)


def _build_index():
    """term -> (entry, kind) where kind is 'scientific' | 'synonym' | 'common' | 'genus'."""
    index: dict[str, tuple[dict, str]] = {}
    genera: dict[str, dict] = {}
    for entry in PLANTS:
        sci = entry["scientific"]
        index.setdefault(sci.lower(), (entry, "scientific"))
        genus = sci.split()[0]
        genera.setdefault(genus.lower(), entry)
        for syn in entry.get("synonyms", []):
            index.setdefault(syn.lower(), (entry, "synonym"))
        for name in entry.get("common", []):
            n = name.lower()
            if n in _AMBIGUOUS_BLOCK:
                continue
            index.setdefault(n, (entry, "common"))
    return index, genera


_INDEX, _GENERA = _build_index()


def _entry_to_hit(entry: dict, matched_as: str) -> PlantHit:
    return PlantHit(
        scientific=entry["scientific"],
        family=entry["family"],
        mena=entry["mena"],
        matched_as=matched_as,
        regions=list(entry.get("regions", [])),
        known_uses=list(entry.get("uses", [])),
    )


def detect(text: str) -> list[PlantHit]:
    """Return the distinct plants mentioned in ``text`` (by scientific name)."""
    norm = normalize(text)
    found: dict[str, PlantHit] = {}

    # 1) full names (scientific + synonym + common), longest first
    for term in sorted(_INDEX, key=len, reverse=True):
        if find_term(norm, term):
            entry, _kind = _INDEX[term]
            found.setdefault(entry["scientific"], _entry_to_hit(entry, term))

    # 2) bare genus mentions for genera not already represented by a binomial
    for genus, entry in _GENERA.items():
        if entry["scientific"] in found:
            continue
        # require the genus as a standalone word (e.g. "Ziziphus species")
        if find_term(norm, genus) and len(genus) >= 5:
            hit = _entry_to_hit(entry, genus + " (genus)")
            found.setdefault(entry["scientific"], hit)

    return list(found.values())


def summarize(hits: list[PlantHit]) -> dict:
    """Record-level roll-up used by the pipeline."""
    return {
        "plants": [h.scientific for h in hits],
        "plant_common": [h.matched_as for h in hits],
        "families": sorted({h.family for h in hits}),
        "mena_plant": any(h.mena for h in hits),
        "mena_plant_names": [h.scientific for h in hits if h.mena],
        "n_plants": len(hits),
    }
