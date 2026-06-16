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

On top of these it produces:

- a consolidated **Integrity Scorecard** — every journal ranked by an overall
  *concern level* (High / Elevated / Watch / Low) with the specific flags it
  tripped, downloadable as CSV;
- an interactive **citation-network graph** with cartel members highlighted;
- a **downloadable Markdown report** summarizing all findings.

> ⚠️ Every metric here is a **screening indicator** to guide further
> investigation — none is proof of misconduct.

## Quick start

```bash
cd citation-integrity-app
pip install -r requirements.txt
streamlit run app.py
```

Then tick **Use bundled sample data** in the sidebar, or upload your own CSVs.
Start on the **🏅 Scorecard** tab for the at-a-glance ranking.

## Run it without a terminal (deploy to the web)

To get a permanent URL you can open from any browser — no Python install:

1. Make sure this folder is pushed to GitHub (it is, on branch
   `claude/confident-cori-0h1g3v`).
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. Click **Create app** → **Deploy a public app from GitHub** and select:
   - **Repository:** `husseinaltameemy/styles`
   - **Branch:** `claude/confident-cori-0h1g3v`
   - **Main file path:** `citation-integrity-app/app.py`
4. Click **Deploy**. Streamlit installs `requirements.txt` automatically and
   gives you a shareable `https://…streamlit.app` link.

Updates pushed to the branch redeploy automatically.

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

#### Scopus exports (auto-detected)

You can also upload a **Scopus document export** directly — no manual reshaping.
When exporting from Scopus, choose **Export → CSV** and tick the **References**
field (under *Citation information*). The app then:

- uses each article's **`Source title`** as the **citing journal**, and
- scans its **`References`** text for journal names, turning each match into a
  **cited journal** link (weighted by how often it appears, self-citations
  included).

Only journals that appear as a `Source title` in the file are tracked as
citation targets by default — that's the set under analysis. Use the sidebar
**"Extra journals to track in references"** box to also watch for journals that
have no articles in your export. If you upload a Scopus file *without* the
References field, the app tells you exactly what to re-export.

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
│   ├── scorecard.py        # consolidated per-journal concern ranking
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
