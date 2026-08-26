# Job Market Tracker — Project Process Summary

## Overview

An end-to-end data pipeline that tracks entry-level data job postings weekly,
extracts in-demand skills from job descriptions, and visualizes trends through
an interactive dashboard. Built across three phases over a single weekend
with automated weekly updates running passively via GitHub Actions.

**Live dashboard:** https://your-app-url.streamlit.app
**Repository:** https://github.com/lilvariable/job-market-tracker

---

## Phase 1 — ETL Pipeline

### What was built
- `db.py` — SQLite schema with two tables (`job_postings`, `job_skills`) and
  connection/insert helpers
- `ingest.py` — pulls job postings from the Adzuna REST API across 5 search
  queries, deduplicates on Adzuna's job ID using `INSERT OR IGNORE`, and stores
  results with both `posted_date` and `pulled_date` for time-on-market analysis
- `.github/workflows/weekly_pull.yml` — GitHub Actions cron job that runs every
  Monday at 8am CT, ingests new postings, and commits the updated database back
  to the repository automatically

### First run results
176 postings fetched, 173 new across 5 role types:
- entry level data analyst
- entry level data scientist
- entry level data engineer
- junior business analyst
- data analyst intern

---

### Diagnostic Problems — Phase 1

**Problem 1: Civil engineering false positives**
Some job postings for civil engineering roles were fetched because the term
"data center" appeared in their titles, triggering keyword matches.

*Solution:* Noted for Phase 2 cleanup. A title-level keyword exclusion filter
in `clean.py` handles this — filtering titles containing terms like
"civil", "construction", or "structural" that don't belong in data role searches.

---

**Problem 2: GitHub Actions workflow file was empty**
After creating `.github/workflows/weekly_pull.yml` in VS Code and committing,
the file on GitHub was blank — content had not been saved before staging.
The Actions tab showed: `No event triggers defined in 'on'`.

*Solution:* Reopened the file in VS Code, pasted the full YAML content,
saved explicitly, verified with `cat .github/workflows/weekly_pull.yml`
in the terminal before staging, then re-committed and pushed.

---

**Problem 3: GitHub Actions permissions error**
The automated workflow failed on the "Commit and push updated data" step
because the default Actions token only has read access.

*Solution:* In the repo on GitHub → Settings → Actions → General →
Workflow permissions → changed to "Read and write permissions".

---

**Problem 4: Git diverged branches after creating README on GitHub**
The README.md was created directly on GitHub rather than locally, causing
the remote and local branches to diverge. `git push` failed with:
`fatal: Need to specify how to reconcile divergent branches.`

*Solution:*
```bash
git pull --no-rebase origin main
# Resolved the merge commit message in the editor, then:
git push
```

---

**Problem 5: Binary file merge conflict on job_postings.db**
After the diverged branch pull, git could not auto-merge the binary `.db`
file, producing: `CONFLICT (content): Merge conflict in data/job_postings.db`.

*Solution:* Keep the local version (which has real data) and discard remote:
```bash
git checkout --ours data/job_postings.db
git add data/job_postings.db
git commit -m "Merge remote README, keep local database"
git push
```

---

## Phase 2 — NLP Skill Extraction

### What was built
- `nlp_extract.py` — keyword matching against a curated vocabulary of 60+
  skills across 8 categories (Language, Database, Cloud, Data Engineering,
  ML/AI, Analysis, Statistics, Dev Tools, Soft Skills). Uses pre-compiled
  regex patterns with word boundaries to avoid partial matches.
- `job_skills` table — stores one row per skill per posting, enabling
  flexible aggregation by role type, category, or date
- `analyze_skills.py` — quick terminal analysis showing top 20 skills overall,
  top 5 per role type, and top 3 per category
- `enrich.py` — fetches full job description text from each posting's
  redirect URL and stores it in `full_description`, since the Adzuna API
  truncates descriptions to ~500 characters

### Design decision: keyword matching over spaCy/NER
Job descriptions are dense bullet lists, not clean prose. A targeted match
against a known skill vocabulary produces more reliable results than a general
NLP model for this use case, and is more defensible in interviews.

---

### Diagnostic Problems — Phase 2

**Problem 1: Only 11 skills detected across 173 postings**
Initial `analyze_skills.py` output showed implausibly low skill counts —
SQL appearing only twice across all data analyst postings, pandas and Git
showing zero hits despite being ubiquitous in the industry.

*Diagnosis:* Checked description lengths:
```bash
python3 -c "
import sqlite3, sys
sys.path.insert(0, 'src')
from db import DB_PATH
conn = sqlite3.connect(DB_PATH)
rows = conn.execute(
    'SELECT title, length(description), description FROM job_postings LIMIT 5'
).fetchall()
for title, length, desc in rows:
    print(f'{title} ({length} chars)')
    print(desc)
conn.close()
"
```
Confirmed: Adzuna's free tier caps API descriptions at ~500 characters,
cutting off mid-sentence before most tool mentions appear.

*Solution:* Built `enrich.py` to fetch full job pages via each posting's
`redirect_url`, parse HTML using regex (no BeautifulSoup dependency),
and store full text in a new `full_description` column. `nlp_extract.py`
updated to use `COALESCE(full_description, description)` as input.

---

**Problem 2: enrich.py found no postings to enrich**
After adding the `redirect_url` column and running `enrich.py`, it
immediately reported: `No unenriched postings found — everything is up to date.`

*Diagnosis:* The original 173 postings were inserted before `redirect_url`
was added to the schema. `INSERT OR IGNORE` skips existing rows, so
re-running `ingest.py` didn't backfill the URL for those rows.
`get_unenriched_postings()` filters on `redirect_url IS NOT NULL`,
so all 173 original postings were silently excluded.

*Solution:* Updated `insert_postings()` in `db.py` to also run an UPDATE
for existing rows with a missing `redirect_url`:
```python
cur.execute(
    """
    UPDATE job_postings
    SET redirect_url = ?
    WHERE source_id = ? AND redirect_url IS NULL
    """,
    (row.get("redirect_url"), row.get("source_id")),
)
```
Re-ran `ingest.py` to backfill, confirmed 206/238 rows now had URLs.
The remaining 32 were expired postings no longer returned by the API —
those fall back to the truncated description, which is acceptable.

---

**Problem 3: High skip rate in enrich.py (151/206 skipped)**
55 postings were successfully enriched; 151 were skipped because the
job pages blocked automated HTTP requests or returned too little content.

*Solution:* Accepted as expected behavior. Many job sites (Workday,
Greenhouse, LinkedIn redirects) block scrapers. The 55 enriched postings
added meaningful signal, and the 151 skipped fall back to the 500-char
Adzuna excerpt. The final skill counts were still dramatically improved:
SQL went from 2 → 40 postings, Excel from 2 → 28, Communication 2 → 32.

---

**Problem 4: Databricks miscategorized as Database**
The skill vocabulary initially categorized Databricks under "Database"
when it is a data engineering and ML platform.

*Solution:* Changed category in `nlp_extract.py`:
```python
"Databricks": {"category": "Data Engineering", "pattern": r"\bdatabricks\b"},
```
Cleared `job_skills` table and re-ran extraction to apply the correction.

---

## Phase 3 — Streamlit Dashboard

### What was built
- `dashboard/app.py` — interactive Streamlit dashboard with:
  - Sidebar role-type filter that updates all charts simultaneously
  - KPI cards: total postings, unique companies, skills tracked, top skill
  - Horizontal bar chart of top N skills colored by category
  - Role × skill heatmap (signature element — shows skill clustering by role)
  - Donut chart of skills by category
  - Top hiring companies bar chart
  - Cumulative posting trend over time
- `.streamlit/config.toml` — custom dark theme (slate background `#0D1117`,
  indigo `#6366F1` primary, emerald `#10B981` secondary)
- Deployed to Streamlit Cloud for a publicly accessible live URL

### Design decisions
- Plotly used throughout for interactivity and consistent styling
- Role × skill heatmap chosen as the signature element — immediately
  communicates analytical thinking and differentiates from generic dashboards
- Dark theme avoids Streamlit's default blue and the generic light dashboard look

---

### Diagnostic Problems — Phase 3

**Problem 1: Heatmap caption said "Darker = more postings"**
The colorscale runs from dark (zero postings) to light purple (high postings),
making the caption factually backwards.

*Solution:* Changed caption text from `"Darker = more postings"` to
`"Lighter = more postings"`.

---

## Final Pipeline Order

For any fresh environment or after a new weekly pull:

```bash
python3 src/ingest.py        # Pull new postings from Adzuna
python3 src/enrich.py        # Fetch full descriptions via redirect URLs
python3 src/nlp_extract.py   # Extract skills from descriptions
python3 src/analyze_skills.py  # Terminal analysis (optional)
streamlit run dashboard/app.py  # Launch dashboard
```

GitHub Actions handles `ingest.py` automatically every Monday.
`enrich.py` and `nlp_extract.py` can be added to the workflow later.

---

## Key Metrics at Project Completion

| Metric | Value |
|---|---|
| Total postings | 238 |
| Postings with full descriptions | 55 |
| Skills tracked | 60+ across 8 categories |
| Unique companies | varies by role filter |
| Top skill overall | Python (69 postings) |
| Automation cadence | Every Monday via GitHub Actions |
| Dashboard | Live on Streamlit Cloud |