"""End-to-end classification pipeline.

Takes a normalised dataframe (from :mod:`classifier.loaders`) and returns the
same rows enriched with every classification axis the app reports on:

* ``pub_type`` (+ ``pub_type_confidence``, ``pub_type_evidence``)
* ``plants`` / ``plant_families`` / ``mena_plant``
* ``activities`` / ``primary_activity``
* ``country`` / ``country_mena`` / ``all_countries``
* ``mena_relevant`` — the headline flag: the study is MENA-relevant when the
  author country is in MENA **or** a MENA plant is studied. ``mena_basis``
  records *why* (country / plant / both).

The functions are pure and importable so the same logic backs the Streamlit UI,
the CLI and the tests.
"""
from __future__ import annotations

import pandas as pd

from . import activities as activities_mod
from . import countries as countries_mod
from . import plants as plants_mod
from . import pubtype as pubtype_mod


def classify_record(row: dict) -> dict:
    """Classify a single record (mapping) and return a flat result dict."""
    title = str(row.get("title", ""))
    abstract = str(row.get("abstract", ""))
    keywords = str(row.get("keywords", ""))
    text = " . ".join(p for p in (title, abstract, keywords) if p)

    pt = pubtype_mod.classify(row)
    plant_hits = plants_mod.detect(text)
    plant_sum = plants_mod.summarize(plant_hits)
    act_hits = activities_mod.detect(title, abstract, keywords)
    act_sum = activities_mod.summarize(act_hits)
    country = countries_mod.detect(row)

    mena_basis = []
    if country.mena:
        mena_basis.append("country")
    if plant_sum["mena_plant"]:
        mena_basis.append("plant")
    mena_relevant = bool(mena_basis)

    return {
        "pub_type": pt.label,
        "pub_type_confidence": round(pt.confidence, 2),
        "pub_type_evidence": "; ".join(pt.evidence),
        "plants": ", ".join(plant_sum["plants"]),
        "plant_families": ", ".join(plant_sum["families"]),
        "mena_plant": plant_sum["mena_plant"],
        "mena_plant_names": ", ".join(plant_sum["mena_plant_names"]),
        "n_plants": plant_sum["n_plants"],
        "activities": ", ".join(act_sum["activities"]),
        "primary_activity": act_sum["primary_activity"],
        "n_activities": act_sum["n_activities"],
        "country": country.primary,
        "all_countries": ", ".join(country.all_countries),
        "country_mena": country.mena,
        "country_source": country.source,
        "mena_relevant": mena_relevant,
        "mena_basis": "+".join(mena_basis) if mena_basis else "",
    }


# Order of the enrichment columns in the output table.
RESULT_COLUMNS = [
    "pub_type", "pub_type_confidence",
    "primary_activity", "activities",
    "plants", "plant_families", "mena_plant", "mena_plant_names",
    "country", "country_mena", "all_countries",
    "mena_relevant", "mena_basis",
    "n_plants", "n_activities", "pub_type_evidence", "country_source",
]


def classify_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of ``df`` with all classification columns appended."""
    results = [classify_record(r) for r in df.to_dict(orient="records")]
    res_df = pd.DataFrame(results, index=df.index)
    # keep the original bibliographic columns first, enrichment after
    ordered = [c for c in ("title", "year", "source", "document_type", "doi")
               if c in df.columns]
    base = df[ordered] if ordered else df
    return pd.concat([base, res_df[RESULT_COLUMNS]], axis=1)
