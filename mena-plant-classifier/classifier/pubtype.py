"""Publication-type classification.

Produces one canonical type per record with a confidence and the evidence used:

    Systematic Review, Meta-Analysis, Review, Clinical Trial, Original Research,
    Case Report, Conference Paper, Book Chapter, Editorial/Letter/Note,
    Erratum, Other

Two signals are combined:

* **Document-type field** (Scopus/WoS/PubMed ``Document Type``) — a strong prior
  when present. Mapped through ``DOCTYPE_MAP``.
* **Text cues** in title/abstract/keywords — can *upgrade* a generic "Article"
  to a more specific evidence-based type (a paper tagged only "Article" whose
  abstract says "systematic review and meta-analysis" is one), and is the sole
  signal when no document-type field exists.

The cascade is ordered by specificity: systematic review / meta-analysis outrank
plain review, which outranks the various primary-study cues that all roll up to
"Original Research".
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .textutil import normalize, find_term

# ---- document-type field vocabulary -> canonical label ----------------------
DOCTYPE_MAP: dict[str, str] = {
    "article": "Original Research",
    "journal article": "Original Research",
    "research article": "Original Research",
    "original article": "Original Research",
    "review": "Review",
    "review article": "Review",
    "short survey": "Review",
    "systematic review": "Systematic Review",
    "meta-analysis": "Meta-Analysis",
    "meta analysis": "Meta-Analysis",
    "clinical trial": "Clinical Trial",
    "randomized controlled trial": "Clinical Trial",
    "conference paper": "Conference Paper",
    "conference review": "Conference Paper",
    "proceedings paper": "Conference Paper",
    "book chapter": "Book Chapter",
    "book": "Book Chapter",
    "editorial": "Editorial/Letter/Note",
    "letter": "Editorial/Letter/Note",
    "note": "Editorial/Letter/Note",
    "comment": "Editorial/Letter/Note",
    "case reports": "Case Report",
    "case report": "Case Report",
    "erratum": "Erratum",
    "correction": "Erratum",
    "retracted": "Erratum",
    "jour": "Original Research",   # RIS generic journal tag
    "rprt": "Original Research",
}

# ---- text cues (checked in this priority order) -----------------------------
# Each tuple: (canonical label, [surface cues], base confidence when text-only)
TEXT_CUES: list[tuple[str, list[str], float]] = [
    ("Meta-Analysis",
     ["meta analysis", "meta analytic", "pooled analysis", "random effects model",
      "pooled odds ratio", "pooled risk ratio", "forest plot"], 0.9),
    ("Systematic Review",
     ["systematic review", "prisma", "systematic literature review",
      "scoping review", "systematic search"], 0.9),
    ("Review",
     ["a review", "review of", "narrative review", "literature review",
      "comprehensive review", "an overview", "this review", "mini review",
      "critical review", "ethnobotanical review", "state of the art"], 0.6),
    ("Clinical Trial",
     ["randomized controlled trial", "randomised controlled trial",
      "double blind", "placebo controlled", "clinical trial", "randomized clinical",
      "crossover trial", "in patients", "healthy volunteers", "enrolled patients"], 0.75),
    ("Case Report",
     ["case report", "a case of", "we report a case", "case series"], 0.8),
    ("Original Research",
     ["in vitro", "in vivo", "was investigated", "were evaluated", "we investigated",
      "ethnobotanical survey", "ethnopharmacological survey", "phytochemical screening",
      "gc ms analysis", "antioxidant activity of", "were extracted", "wistar rats",
      "albino mice", "cell line", "ic50", "mic values", "aqueous extract",
      "methanolic extract", "ethanolic extract", "experimental", "assay"], 0.6),
]

# specificity order for resolving competing signals
PRIORITY = [
    "Meta-Analysis", "Systematic Review", "Clinical Trial", "Case Report",
    "Review", "Original Research", "Conference Paper", "Book Chapter",
    "Editorial/Letter/Note", "Erratum", "Other",
]
_RANK = {label: i for i, label in enumerate(PRIORITY)}


@dataclass
class PubTypeResult:
    label: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    doctype_raw: str = ""


def _from_doctype(doctype_raw: str) -> str | None:
    key = doctype_raw.strip().lower()
    if not key:
        return None
    if key in DOCTYPE_MAP:
        return DOCTYPE_MAP[key]
    # partial contains (handles "Article; Early Access", "Article in Press")
    for token, label in DOCTYPE_MAP.items():
        if token in key:
            return label
    return None


def _from_text(norm_text: str) -> list[tuple[str, float, str]]:
    """Return (label, confidence, cue) for each cue category that fires."""
    out = []
    for label, cues, conf in TEXT_CUES:
        for cue in cues:
            if find_term(norm_text, cue):
                out.append((label, conf, cue))
                break
    return out


def classify(row) -> PubTypeResult:
    """Classify one record (a mapping with title/abstract/keywords/document_type)."""
    doctype_raw = str(row.get("document_type", ""))
    doc_label = _from_doctype(doctype_raw)

    text = " . ".join(str(row.get(c, "")) for c in ("title", "abstract", "keywords"))
    norm = normalize(text)
    text_hits = _from_text(norm)

    # Best (most specific) text signal, if any.
    text_best = None
    if text_hits:
        text_best = min(text_hits, key=lambda h: _RANK.get(h[0], 99))

    # --- Decision cascade ----------------------------------------------------
    if doc_label is None:
        if text_best:
            label, conf, cue = text_best
            return PubTypeResult(label, conf, [f"text: {cue}"], doctype_raw)
        return PubTypeResult("Other", 0.3, [], doctype_raw)

    evidence = [f"document type: {doctype_raw.strip()}"]

    # Generic "Article" / "Review" can be sharpened by strong text evidence.
    if doc_label in ("Original Research", "Review") and text_best:
        t_label, t_conf, cue = text_best
        # Only upgrade to a *more specific* type, and only on high-confidence cues.
        if _RANK[t_label] < _RANK[doc_label] and t_conf >= 0.75:
            return PubTypeResult(t_label, min(0.95, 0.6 + t_conf / 2),
                                 evidence + [f"text: {cue}"], doctype_raw)
        # Text agrees with / reinforces the field label.
        if t_label == doc_label:
            return PubTypeResult(doc_label, 0.9, evidence + [f"text: {cue}"], doctype_raw)

    return PubTypeResult(doc_label, 0.8, evidence, doctype_raw)
