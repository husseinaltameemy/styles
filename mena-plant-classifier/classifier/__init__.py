"""MENA Medicinal-Plant Publication Classifier.

A rule- and lexicon-driven engine that classifies medicinal-plant publications by
publication type, plant (with MENA provenance), therapeutic activity, and country.

Public entry points:

    from classifier import loaders, pipeline
    df = loaders.load_csv("export.csv")
    enriched = pipeline.classify_dataframe(df)
"""
from __future__ import annotations

from . import (
    activities,
    countries,
    loaders,
    pipeline,
    plants,
    pubtype,
    report,
    textutil,
)

__all__ = [
    "activities", "countries", "loaders", "pipeline",
    "plants", "pubtype", "report", "textutil",
]

__version__ = "0.1.0"
