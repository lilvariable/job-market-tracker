"""
ingest.py - Pull job postings from the Adzuna API and store them in SQLite.

Setup:
    1. Sign up for free API keys at https://developer.adzuna.com/
    2. Copy .env.example to .env and fill in ADZUNA_APP_ID / ADZUNA_APP_KEY
    3. pip install -r requirements.txt
    4. python src/ingest.py

This script is idempotent: re-running it will skip postings already stored
(deduped on Adzuna's own ad id), so it's safe to run on a schedule (e.g. weekly
via GitHub Actions) and just accumulate new postings over time.
"""
import os
import time
from datetime import date

import requests
from dotenv import load_dotenv

from db import init_db, insert_postings

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")
COUNTRY = os.getenv("ADZUNA_COUNTRY", "us")  # us, gb, etc.

BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{COUNTRY}/search/1"

# Tune these to match the roles you're targeting. Each is a separate query
# because Adzuna's search is a simple keyword match, not a semantic one --
# running several narrow queries gets better coverage than one broad query.
SEARCH_QUERIES = [
    "entry level data analyst",
    "entry level data scientist",
    "entry level data engineer",
    "junior business analyst",
    "data analyst intern",
]

RESULTS_PER_QUERY = 50  # Adzuna caps at 50 per page on the free tier


def fetch_postings(query: str) -> list[dict]:
    """Fetch one page of postings for a given search query."""
    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "what": query,
        "results_per_page": RESULTS_PER_QUERY,
        "content-type": "application/json",
    }

    resp = requests.get(BASE_URL, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()

    today = date.today().isoformat()
    rows = []
    for job in payload.get("results", []):
        rows.append(
            {
                "source_id": str(job.get("id")),
                "title": job.get("title"),
                "company": (job.get("company") or {}).get("display_name"),
                "location": (job.get("location") or {}).get("display_name"),
                "description": job.get("description"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "category": (job.get("category") or {}).get("label"),
                "posted_date": job.get("created"),
                "pulled_date": today,
                "search_query": query,
            }
        )
    return rows


def main():
    if not APP_ID or not APP_KEY:
        raise SystemExit(
            "Missing ADZUNA_APP_ID / ADZUNA_APP_KEY. "
            "Copy .env.example to .env and fill in your keys."
        )

    init_db()

    total_fetched = 0
    total_new = 0

    for query in SEARCH_QUERIES:
        print(f"Fetching: {query!r} ...")
        try:
            rows = fetch_postings(query)
        except requests.HTTPError as e:
            print(f"  request failed: {e}")
            continue

        new_count = insert_postings(rows)
        total_fetched += len(rows)
        total_new += new_count
        print(f"  got {len(rows)} postings, {new_count} new")

        time.sleep(1)  # be polite to the free-tier rate limit

    print(f"\nDone. Fetched {total_fetched} postings this run, {total_new} were new.")


if __name__ == "__main__":
    main()