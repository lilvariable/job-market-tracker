"""
db.py - SQLite schema and connection helper for the job market tracker.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "job_postings.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS job_postings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT UNIQUE,
    title TEXT,
    company TEXT,
    location TEXT,
    description TEXT,
    salary_min REAL,
    salary_max REAL,
    category TEXT,
    posted_date TEXT,
    pulled_date TEXT,
    search_query TEXT
);

CREATE INDEX IF NOT EXISTS idx_posted_date ON job_postings (posted_date);
CREATE INDEX IF NOT EXISTS idx_search_query ON job_postings (search_query);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the local SQLite DB, creating the file/schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """Create the job_postings table if it doesn't already exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_postings(rows: list[dict]) -> int:
    """
    Insert a batch of postings, skipping duplicates on source_id.
    Returns the number of NEW rows actually inserted.
    """
    if not rows:
        return 0

    conn = get_connection()
    inserted = 0
    try:
        cur = conn.cursor()
        for row in rows:
            cur.execute(
                """
                INSERT OR IGNORE INTO job_postings
                    (source_id, title, company, location, description,
                     salary_min, salary_max, category, posted_date,
                     pulled_date, search_query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("source_id"),
                    row.get("title"),
                    row.get("company"),
                    row.get("location"),
                    row.get("description"),
                    row.get("salary_min"),
                    row.get("salary_max"),
                    row.get("category"),
                    row.get("posted_date"),
                    row.get("pulled_date"),
                    row.get("search_query"),
                ),
            )
            if cur.rowcount:
                inserted += 1
        conn.commit()
    finally:
        conn.close()

    return inserted


def count_postings() -> int:
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"DB ready at {DB_PATH}")
    print(f"Current row count: {count_postings()}")