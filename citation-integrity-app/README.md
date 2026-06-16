# Citation & Editorial Integrity Analyzer

A Streamlit app for screening academic journals for **research-integrity red
flags** from citation and retraction data:

1. **Citation cartels** — groups of journals that cite each other at unusually
   high rates to inflate impact metrics (reciprocal pairs + tightly
   self-citing clusters).
2. **Self-citation metrics** — per-journal self-citation rate plus year-over-year
   spike detection.
3. **Coercive self-citation risk** — heuristic indicators that a journal may be
   pressuring authors to cite it (high level + rising trend + many authors
   funneling citations to one journal).
4. **Editorial integrity** — retraction-based scoring that highlights
   *editorial-process* failures (paper mills, faked/compromised peer review,
   data fabrication) versus isolated author errors.

It also produces a **downloadable Markdown report** summarizing all findings.

> ⚠️ Every metric here is a **screening indicator** to guide further
> investigation — none is proof of misconduct.

## Quick start

```bash
cd citation-integrity-app
pip install -r requirements.txt
streamlit run app.py
```

Then tick **Use bundled sample data** in the sidebar, or upload your own CSVs.

## Input formats

### Citations CSV
One row per citation edge (or aggregated with a `count`). Column names are
matched flexibly (e.g. `source`/`target` also work).

| column           | required | notes                                  |
|------------------|----------|----------------------------------------|
| `citing_journal` | ✅       | journal making the citation            |
| `cited_journal`  | ✅       | journal being cited                    |
| `year`           | optional | enables self-citation trend/spike      |
| `count`          | optional | edge weight; defaults to 1             |
| `citing_author`  | optional | enables the coercion author-spread signal |

A row where `citing_journal == cited_journal` is a **self-citation**.

### Retractions CSV
| column    | required | notes                                       |
|-----------|----------|---------------------------------------------|
| `journal` | ✅       | journal where the retraction occurred       |
| `reason`  | optional | free text; classified into cause categories |
| `year`    | optional |                                             |
| `doi`     | optional |                                             |

## Online data (optional)

- **Retraction Watch** — one click downloads the public Retraction Watch
  dataset (via Crossref) and feeds it into the analysis.
- **OpenAlex** — look up a journal by name for basic metadata.

Both require outbound network access; if it's blocked the app reports a clear
message and keeps working with uploaded CSVs.

## How the scores work

- **Reciprocity score** — geometric mean of the citation shares each journal
  in a pair directs at the other, volume-dampened to ignore tiny pairs.
- **Cartel cluster score** — internal-citation ratio of a strongly-connected
  group, scaled down for large groups.
- **Self-citation rate** — `self-citations ÷ total citations received`.
- **Coercion risk** — `0.45·level + 0.30·trend + 0.25·author-spread`.
- **Integrity risk** — saturating sum of per-retraction severities, with
  editorial-process causes weighted highest.

## Project layout

```
citation-integrity-app/
├── app.py                  # Streamlit UI
├── integrity/
│   ├── loaders.py          # CSV loading + column normalization
│   ├── cartels.py          # citation-graph cartel detection
│   ├── self_citation.py    # self-citation rates & trends
│   ├── coercion.py         # coercive-citation risk heuristics
│   ├── retractions.py      # retraction-reason classification & scoring
│   ├── report.py           # Markdown report builder
│   └── sources.py          # optional online sources (Retraction Watch, OpenAlex)
├── sample_data/            # example citations.csv & retractions.csv
├── tests/test_analysis.py  # unit tests
└── requirements.txt
```

## Tests

```bash
python tests/test_analysis.py      # no pytest needed
# or
python -m pytest
```
