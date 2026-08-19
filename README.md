# Job Market Tracker

An end-to-end data pipeline that tracks entry-level data science, data engineering, and business analyst job postings over time — built as a portfolio project to demonstrate ETL, NLP, and data visualization skills.

---

## What it does

The pipeline pulls job postings from the [Adzuna API](https://developer.adzuna.com/) weekly via a GitHub Actions cron job, deduplicates and stores them in a local SQLite database, and (in progress) extracts in-demand skills from job descriptions using NLP. A Streamlit dashboard surfaces trends over time: which skills are rising, which companies are hiring most, and how the market shifts week to week.

The database accumulates automatically — every Monday a new batch is pulled and committed back to the repo, so the commit history itself reflects the project growing in real time.

---

## Stack

| Layer | Tools |
|---|---|
| Data ingestion | Python, Requests, Adzuna REST API |
| Storage | SQLite |
| Automation | GitHub Actions (weekly cron) |
| NLP (Phase 2) | spaCy / NLTK (in progress) |
| Dashboard | Streamlit |
| Analysis | pandas, matplotlib |

---

## Project structure

```
job-market-tracker/
├── src/
│   ├── ingest.py        # Pulls postings from Adzuna, deduplicates, stores in SQLite
│   ├── db.py            # Schema definition and connection helpers
│   ├── clean.py         # Title/location normalization, keyword exclusion filters
│   └── nlp_extract.py   # Skill/tool extraction from job descriptions (Phase 2)
├── dashboard/
│   └── app.py           # Streamlit dashboard
├── notebooks/
│   └── exploration.ipynb
├── data/
│   └── job_postings.db  # Accumulating SQLite database
├── .github/workflows/
│   └── weekly_pull.yml  # GitHub Actions cron job (runs every Monday)
├── .env.example
└── requirements.txt
```

---

## Phases

**Phase 1 — ETL pipeline** 
- Adzuna API integration across 5 entry-level search queries
- Deduplication on Adzuna's job ID (`INSERT OR IGNORE`) so re-runs are safe
- `pulled_date` vs `posted_date` separation to enable time-on-market analysis later
- Fully automated via GitHub Actions — runs every Monday, commits updated `.db` back to repo

**Phase 2 — NLP skill extraction**  
- Parse job descriptions to extract mentioned tools and skills (Python, SQL, Tableau, etc.)
- Rank skills by frequency and track how demand shifts week to week

**Phase 3 — Dashboard**
- Streamlit app visualizing skill trends, top hiring companies, and geographic concentration

---

## Running locally

```bash
# Clone and install
git clone https://github.com/lilvariable/job-market-tracker.git
cd job-market-tracker
pip install -r requirements.txt

# Add your Adzuna API keys
cp .env.example .env
# Edit .env and fill in ADZUNA_APP_ID and ADZUNA_APP_KEY

# Run the ingestion pipeline
python src/ingest.py

# Launch the dashboard
streamlit run dashboard/app.py
```

---

## Automated weekly pulls

The pipeline runs autonomously every Monday at 8:00 AM CT via GitHub Actions. Adzuna API keys are stored as encrypted repository secrets — never committed to the repo. If a run finds no new postings (rare), the workflow skips the commit gracefully.

---

## Author

Sebastian — MS Data Science candidate, Texas Tech University  
[GitHub](https://github.com/lilvariable)
