"""
enrich.py - Fetch full job descriptions from each posting's redirect_url.

Adzuna's API returns truncated ~500 char descriptions. This script visits
the actual job page for each posting, strips the HTML, and stores the full
text in the full_description column so nlp_extract.py has real content.

Run AFTER ingest.py, BEFORE nlp_extract.py:
    python src/enrich.py

Safe to re-run: only fetches postings where full_description is still NULL.
Be aware: some job pages may block scrapers or require JavaScript — those
will be skipped gracefully and logged so you can review them.
"""

import time
import re
import requests
from requests.exceptions import RequestException

from db import get_unenriched_postings, update_full_description, init_db

# How long to wait between requests — be polite, avoid rate-limiting
REQUEST_DELAY = 1.5  # seconds

# Timeout per request
REQUEST_TIMEOUT = 10  # seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Minimum character count to consider a fetch successful
MIN_TEXT_LENGTH = 200


def extract_text_from_html(html: str) -> str:
    """
    Pull readable text out of raw HTML without external dependencies.
    Strips script/style blocks first, then removes all remaining tags.
    This avoids needing BeautifulSoup while still producing clean text.
    """
    # Remove script and style blocks entirely
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_full_description(url: str) -> str | None:
    """
    Fetch a job posting page and return its text content.
    Returns None if the fetch fails or the result is too short to be useful.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        text = extract_text_from_html(resp.text)
        if len(text) < MIN_TEXT_LENGTH:
            return None
        return text
    except RequestException:
        return None


def main() -> None:
    init_db()
    postings = get_unenriched_postings()

    if not postings:
        print("No unenriched postings found — everything is up to date.")
        return

    print(f"Enriching {len(postings)} postings...")

    success = 0
    skipped = 0

    for i, posting in enumerate(postings, 1):
        text = fetch_full_description(posting["redirect_url"])

        if text:
            update_full_description(posting["id"], text)
            success += 1
            status = f"ok ({len(text)} chars)"
        else:
            skipped += 1
            status = "skipped (blocked or too short)"

        print(f"  [{i}/{len(postings)}] {status}")
        time.sleep(REQUEST_DELAY)

    print(f"\nDone. {success} enriched, {skipped} skipped.")
    if skipped:
        print(
            f"Note: {skipped} postings still have only the truncated Adzuna description. "
            "This is normal — some job sites block automated requests."
        )


if __name__ == "__main__":
    main()