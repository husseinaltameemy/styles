# 🌿 MENA Medicinal-Plant Publication Classifier

A high-precision tool that classifies **medicinal-plant publications** along four
axes, purpose-built for screening the Middle East / North Africa (MENA)
ethnopharmacology literature:

| Axis | What it produces |
|------|------------------|
| **Publication type** | Original Research · Review · Systematic Review · Meta-Analysis · Clinical Trial · Case Report · Conference Paper · Book Chapter · Editorial/Letter/Note · Erratum |
| **Plant** | Species extracted from the text (scientific + common/Arabic names), each flagged **MENA / non-MENA** with its plant **family** |
| **Therapeutic activity** | Anti-cancer / anti-tumor · anti-diabetic · anti-inflammatory · antioxidant · antimicrobial · antiviral · hepatoprotective · antihypertensive · neuroprotective … (35+ classes) |
| **Country** | Study country from affiliations, flagged **MENA / non-MENA** |

Each record also gets a headline **`mena_relevant`** flag (author country in MENA
**or** a MENA plant is studied) with the reason recorded in **`mena_basis`**.

> ⚠️ This is a **screening tool**. Every label is derived from the supplied text
> and curated vocabularies — spot-check before using it in a systematic review.

## Quick start

```bash
cd mena-plant-classifier
pip install -r requirements.txt
streamlit run app.py
```

Tick **Use bundled sample data** in the sidebar, or upload your own export.

### Or run it headless (no UI)

```bash
python classify_cli.py sample_data/sample_publications.csv --report -
# -> writes sample_publications.classified.csv and prints a Markdown summary
```

### Or call it from Python

```python
from classifier import loaders, pipeline
df = loaders.load_csv("scopus_export.csv")
enriched = pipeline.classify_dataframe(df)
```

## Input formats

Works with exports from the databases used for medicinal-plant reviews. Column
headers are matched flexibly, so Scopus / PubMed / Web of Science CSVs and RIS
files load without editing.

| Canonical field | Recognised headers (examples) | Needed for |
|-----------------|-------------------------------|------------|
| `title`         | Title, Article Title, `TI`    | **required** |
| `abstract`      | Abstract, `AB`, `N2`          | activity + plant accuracy |
| `keywords`      | Author Keywords, Index Keywords, `KW` | activity + plant accuracy |
| `document_type` | Document Type, Publication Type, `TY` | publication type |
| `affiliations`  | Authors with affiliations, Author Address, `AD` | country |
| `country`       | Country, Country/Region       | country (preferred) |
| `year`, `source`, `doi` | Year, Source Title, DOI | reporting |

Only **Title** is mandatory; the more of the rest you supply, the higher the
accuracy.

## How the classification works

Everything is transparent, rule- and lexicon-driven — no black-box model, so each
label comes with its supporting evidence.

* **Publication type** (`classifier/pubtype.py`) combines the `Document Type`
  field (strong prior) with text cues, and *upgrades* a generic "Article" to a
  more specific evidence-based type when the abstract clearly warrants it
  (e.g. an abstract that says "systematic review and meta-analysis … PRISMA …
  random effects model").
* **Plants** (`classifier/plants.py`) are matched against a curated knowledge
  base of **~75 plants** (`classifier/knowledge/plants.py`) — heavily weighted to
  MENA species (*Nigella sativa*, *Peganum harmala*, *Rhazya stricta*, *Ziziphus
  spina-christi*, *Artemisia herba-alba* …) but also carrying common **non-MENA**
  medicinal plants (turmeric, ginger, ginkgo, ginseng) so "is this MENA?" is
  answered correctly in both directions. Scientific names, botanical synonyms and
  English/Arabic/Persian common names all match; the longest, most specific name
  wins.
* **Activities** (`classifier/activities.py`) map ~250 surface terms onto 35+
  canonical activity classes (`classifier/knowledge/activities.py`).
  Hyphen / space / concatenation variants are unified, so `anti-cancer`,
  `anti cancer` and `anticancer` all resolve to the same label, and the specific
  matched term is kept as evidence (so *anticancer* vs *antitumor* is preserved).
* **Country** (`classifier/countries.py`) resolves from an explicit country field
  first, then affiliations, then free text — recognising names, aliases (KSA,
  UAE, Türkiye) and adjectives (Saudi, Egyptian) — and tags MENA membership.

### Accuracy safeguards

* Whole-word matching prevents substring false positives (`rue` never fires
  inside `true`).
* A short-name block list keeps ambiguous common words (`date`, `tea`, `rue`,
  `anise`) from matching as plants unless the binomial appears.
* Longest-phrase-first matching prefers `Ziziphus spina-christi` over the bare
  genus, and `systematic review` over `review`.

## Project layout

```
mena-plant-classifier/
├── app.py                       # Streamlit UI
├── classify_cli.py              # command-line batch classifier
├── classifier/
│   ├── loaders.py               # CSV/RIS parsing + column normalisation
│   ├── pubtype.py               # publication-type classifier
│   ├── plants.py                # plant detection + MENA flag
│   ├── activities.py            # therapeutic-activity detection
│   ├── countries.py             # country detection + MENA flag
│   ├── pipeline.py              # orchestrates all four axes
│   ├── report.py                # Markdown summary report
│   ├── textutil.py              # normalisation / phrase matching
│   └── knowledge/               # curated vocabularies (data)
│       ├── plants.py            #   ~75 plants, MENA-flagged
│       ├── activities.py        #   35+ activity classes
│       └── countries.py         #   country → MENA map
├── sample_data/
│   └── sample_publications.csv  # 18-record Scopus-style demo export
└── tests/
    └── test_classifier.py       # unit + end-to-end tests
```

## Tests

```bash
cd mena-plant-classifier
pip install pytest pandas
pytest -q
```

## Extending the knowledge bases

Accuracy scales with coverage, and every vocabulary is plain Python data:

* **Add a plant** — append a dict to `PLANTS` in
  `classifier/knowledge/plants.py` (set `mena` and list common/Arabic names).
* **Add an activity** — add a canonical label + surface terms to `ACTIVITIES`
  in `classifier/knowledge/activities.py`.
* **Adjust MENA scope** — flip the `mena` flag in
  `classifier/knowledge/countries.py` (e.g. to narrow the broad Arab-League tail).

## Deploy to the web (permanent URL, no install)

1. Push this folder to GitHub (it lives on branch
   `claude/publication-classifier-medicinal-plants-6z5pv4`).
2. Go to **https://share.streamlit.io**, sign in with GitHub, **Create app**.
3. Select **Repository** `husseinaltameemy/styles`, the branch above, and
   **Main file path** `mena-plant-classifier/app.py`. Deploy.

Streamlit installs `requirements.txt` automatically and gives you a shareable
`https://…streamlit.app` link that redeploys on every push.
