"""Unit tests for the integrity analysis modules.

Run with:  python -m pytest   (or)   python tests/test_analysis.py
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrity import (
    cartels,
    coercion,
    editor_citation,
    loaders,
    report,
    retractions,
    scorecard,
    self_citation,
)


def _citations() -> pd.DataFrame:
    here = os.path.dirname(os.path.abspath(__file__))
    return loaders.load_citations(os.path.join(here, "..", "sample_data", "citations.csv"))


def _retractions() -> pd.DataFrame:
    here = os.path.dirname(os.path.abspath(__file__))
    return loaders.load_retractions(os.path.join(here, "..", "sample_data", "retractions.csv"))


def test_loader_normalizes_aliases():
    df = loaders.load_citations("source,target\nA,B\nB,A\n")
    assert {"citing_journal", "cited_journal", "count"} <= set(df.columns)
    assert df["count"].tolist() == [1, 1]


def test_loader_missing_columns_raises():
    try:
        loaders.load_citations("foo,bar\n1,2\n")
    except ValueError as exc:
        assert "citing_journal" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_scopus_export_parsed_to_edges():
    here = os.path.dirname(os.path.abspath(__file__))
    df = loaders.load_citations(os.path.join(here, "..", "sample_data", "scopus_export.csv"))
    assert {"citing_journal", "cited_journal", "count"} <= set(df.columns)
    # Source title becomes the citing journal.
    assert "Journal of Alpha Studies" in set(df["citing_journal"])
    # Alpha cites Beta and Mainstream (cross-journal links extracted).
    alpha = df[df["citing_journal"] == "Journal of Alpha Studies"]
    cited = set(alpha["cited_journal"])
    assert "Journal of Beta Research" in cited
    # Self-citation captured (Alpha references Alpha).
    assert "Journal of Alpha Studies" in cited


def test_scopus_without_references_gives_helpful_error():
    csv = "Authors,Title,Source title,Cited by,EID,Document Type\nA,T,J Foo,3,x,Article\n"
    try:
        loaders.load_citations(csv)
    except ValueError as exc:
        assert "References" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError mentioning References")


def test_cartel_detects_reciprocal_pair():
    res = cartels.analyze(_citations())
    pair_keys = {
        frozenset((p["journal_a"], p["journal_b"])) for p in res["reciprocal_pairs"]
    }
    assert frozenset(("Journal of Alpha Studies", "Journal of Beta Research")) in pair_keys
    # The Alpha/Beta cluster should surface as a cartel cluster.
    clustered = {j for c in res["clusters"] for j in c["journals"].split(", ")}
    assert "Journal of Alpha Studies" in clustered


def test_self_citation_rate_and_spike():
    res = self_citation.analyze(_citations())
    table = res["table"].set_index("journal")
    # Alpha self-cites 70 of (70+...) received; should have a high rate.
    assert table.loc["Journal of Alpha Studies", "self_rate"] > 0.3
    assert "Journal of Alpha Studies" in res["flagged_high"]
    # Self-citation jumps 2021->2022 for Alpha => spike.
    assert "Journal of Alpha Studies" in res["flagged_spike"]


def test_coercion_scores_present():
    res = coercion.analyze(_citations())
    assert res["has_author_data"] is True
    assert not res["table"].empty
    assert res["table"]["coercion_risk"].max() <= 1.0


def test_retraction_classification():
    res = retractions.analyze(_retractions())
    scores = res["scores"].set_index("journal")
    assert scores.loc["Predatory Gamma Letters", "editorial_failures"] >= 2
    assert "Predatory Gamma Letters" in res["flagged_editorial"]
    # Honest error must be low severity and not an editorial failure.
    classified = res["classified"].set_index("doi")
    assert classified.loc["10.0000/ms.001", "category"] == "error"


def test_scorecard_ranks_journals():
    cits = _citations()
    rets = _retractions()
    card = scorecard.build(
        cartels.analyze(cits),
        self_citation.analyze(cits),
        coercion.analyze(cits),
        retractions.analyze(rets),
    )
    assert not card.empty
    assert {"journal", "concern_level", "concern_score", "flags"} <= set(card.columns)
    assert card["concern_score"].max() <= 1.0
    # Predatory Gamma Letters should carry an editorial-failure flag.
    pg = card.set_index("journal").loc["Predatory Gamma Letters"]
    assert "editorial failure" in pg["flags"]
    # Rows are sorted High -> Low concern.
    order = {"High": 0, "Elevated": 1, "Watch": 2, "Low": 3}
    levels = [order[v] for v in card["concern_level"]]
    assert levels == sorted(levels)


def test_editor_external_citation_detected():
    here = os.path.dirname(os.path.abspath(__file__))
    cits = loaders.load_citations(
        os.path.join(here, "..", "sample_data", "scopus_export.csv")
    )
    # Jones B. publishes in Journal of Beta Research but cites Journal of Alpha
    # Studies from there => an external citation to the target journal.
    res = editor_citation.analyze(cits, "Journal of Alpha Studies", "Jones B.")
    assert res["target"] == "Journal of Alpha Studies"
    assert res["summary"]["external_papers"] >= 1
    assert res["summary"]["external_citations"] >= 1
    # The external venue used is the Beta journal, not the target itself.
    venues = set(res["by_venue"]["external_venue"])
    assert "Journal of Beta Research" in venues
    assert "Journal of Alpha Studies" not in venues
    # Author ranking surfaces Jones B.
    assert "Jones B." in set(res["by_author"]["author"])


def test_editor_target_not_found():
    cits = loaders.load_citations("source,target\nA,B\nB,A\n")
    res = editor_citation.analyze(cits, "Nonexistent Journal")
    assert res["target"] is None
    assert "Nonexistent Journal" in res["note"]


def test_report_builds():
    cits = _citations()
    rets = _retractions()
    md = report.build_report(
        cartels.analyze(cits),
        self_citation.analyze(cits),
        coercion.analyze(cits),
        retractions.analyze(rets),
    )
    assert "Executive summary" in md
    assert "Predatory Gamma Letters" in md


if __name__ == "__main__":
    import traceback

    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in funcs:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(funcs) - failed}/{len(funcs)} tests passed")
    sys.exit(1 if failed else 0)
