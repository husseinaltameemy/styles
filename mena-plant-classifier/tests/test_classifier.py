"""Unit tests for the classification engine.

Run from the app directory with:  pytest -q
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from classifier import loaders, pipeline  # noqa: E402
from classifier import activities, countries, plants, pubtype  # noqa: E402


# ---------------------------------------------------------------- plant detection
def test_detects_binomial_and_mena_flag():
    hits = plants.detect("Antidiabetic effect of Nigella sativa seed extract")
    names = [h.scientific for h in hits]
    assert "Nigella sativa" in names
    assert all(h.mena for h in hits if h.scientific == "Nigella sativa")


def test_non_mena_plant_flagged_false():
    hits = plants.detect("Curcuma longa curcumin in colorectal cancer")
    curcuma = [h for h in hits if h.scientific == "Curcuma longa"]
    assert curcuma and curcuma[0].mena is False


def test_common_and_synonym_names():
    assert any(h.scientific == "Nigella sativa"
               for h in plants.detect("black seed lowers glucose"))
    assert any(h.scientific == "Matricaria chamomilla"
               for h in plants.detect("Matricaria recutita flower extract"))


def test_ambiguous_short_word_not_matched_as_plant():
    # "date" is blocked as a common name to avoid false positives on calendar dates
    hits = plants.detect("data collected on 5 date points during the assay")
    assert "Phoenix dactylifera" not in [h.scientific for h in hits]


# ------------------------------------------------------------- activity detection
def test_activity_hyphen_space_concatenation_equivalence():
    for text in ("anti-cancer activity", "anti cancer activity", "anticancer activity"):
        labels = [h.label for h in activities.detect(text, "", "")]
        assert "Anticancer/Antitumor" in labels


def test_antidiabetic_and_primary_activity_from_title():
    hits = activities.detect(
        "Antidiabetic effect of extract", "It also showed antioxidant activity", "")
    summary = activities.summarize(hits)
    # title-level activity outranks abstract-only one
    assert summary["primary_activity"] == "Antidiabetic"
    assert "Antioxidant" in summary["activities"]


def test_antitumor_maps_to_anticancer_group():
    labels = [h.label for h in activities.detect("strong antitumour effect", "", "")]
    assert "Anticancer/Antitumor" in labels


# -------------------------------------------------------------- country detection
def test_country_from_affiliation_and_mena():
    res = countries.detect({"affiliations": "King Saud University, Riyadh, Saudi Arabia"})
    assert res.primary == "Saudi Arabia"
    assert res.mena is True


def test_country_adjective_and_alias():
    assert countries.detect({"country": "KSA"}).primary == "Saudi Arabia"
    assert countries.detect({"affiliations": "an Egyptian cohort"}).primary == "Egypt"


def test_non_mena_country():
    res = countries.detect({"affiliations": "AIIMS, New Delhi, India"})
    assert res.primary == "India" and res.mena is False


# ------------------------------------------------------------ publication typing
def test_systematic_review_from_text_upgrades_article():
    row = {"title": "A systematic review and meta-analysis of fenugreek",
           "abstract": "Following PRISMA, a random effects model pooled 12 trials.",
           "keywords": "meta-analysis", "document_type": "Review"}
    res = pubtype.classify(row)
    assert res.label in ("Meta-Analysis", "Systematic Review")


def test_clinical_trial_detection():
    row = {"title": "Effect of Hibiscus in a randomized placebo-controlled clinical trial",
           "abstract": "double blind placebo controlled trial in healthy volunteers",
           "keywords": "clinical trial", "document_type": "Article"}
    assert pubtype.classify(row).label == "Clinical Trial"


def test_original_research_default_for_lab_study():
    row = {"title": "Antioxidant activity of extract",
           "abstract": "The methanolic extract was evaluated in vitro with IC50 values",
           "keywords": "", "document_type": "Article"}
    assert pubtype.classify(row).label == "Original Research"


def test_editorial_from_doctype():
    row = {"title": "The growing role of medicinal plants", "abstract": "",
           "keywords": "", "document_type": "Editorial"}
    assert pubtype.classify(row).label == "Editorial/Letter/Note"


# --------------------------------------------------------------------- pipeline
def _sample_path():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "sample_data", "sample_publications.csv")


def test_pipeline_end_to_end_on_sample():
    df = loaders.load_csv(_sample_path())
    out = pipeline.classify_dataframe(df)
    assert len(out) == 18
    # every enrichment column present
    for col in ("pub_type", "primary_activity", "plants", "country", "mena_relevant"):
        assert col in out.columns
    # the Nigella sativa row is MENA-relevant on both counts
    nigella = out[out["plants"].str.contains("Nigella sativa")].iloc[0]
    assert nigella["mena_relevant"] is True or nigella["mena_relevant"] == True  # noqa: E712
    assert nigella["country"] == "Saudi Arabia"
    assert nigella["primary_activity"] == "Antidiabetic"
    # the turmeric/India row is NOT MENA-relevant (non-MENA plant, non-MENA country)
    turmeric = out[out["plants"].str.contains("Curcuma longa")].iloc[0]
    assert bool(turmeric["mena_relevant"]) is False


def test_pipeline_mena_basis_plant_only():
    # A MENA plant studied by a non-MENA author country -> MENA-relevant via plant.
    row = {"title": "Anticancer activity of Rhazya stricta",
           "abstract": "cytotoxic against HepG2", "keywords": "",
           "affiliations": "Department of Biology, Kyoto University, Japan"}
    res = pipeline.classify_record(row)
    assert res["mena_relevant"] is True
    assert res["country_mena"] is False
    assert "plant" in res["mena_basis"]


def test_ris_loader_roundtrip():
    ris = (
        "TY  - JOUR\n"
        "TI  - Antidiabetic effect of Nigella sativa\n"
        "AB  - black seed lowered blood glucose in rats\n"
        "KW  - antidiabetic\n"
        "AD  - King Saud University, Riyadh, Saudi Arabia\n"
        "PY  - 2021\n"
        "ER  - \n"
    )
    df = loaders.load_ris(ris)
    out = pipeline.classify_dataframe(df)
    assert out.iloc[0]["country"] == "Saudi Arabia"
    assert "Nigella sativa" in out.iloc[0]["plants"]
