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
    full_description TEXT,
    redirect_url TEXT,
    salary_min REAL,
    salary_max REAL,
    category TEXT,
    posted_date TEXT,
    pulled_date TEXT,
    search_query TEXT
);

CREATE TABLE IF NOT EXISTS job_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    posting_id INTEGER REFERENCES job_postings(id),
    skill TEXT,
    category TEXT,
    extracted_date TEXT
);

CREATE INDEX IF NOT EXISTS idx_posted_date ON job_postings (posted_date);
CREATE INDEX IF NOT EXISTS idx_search_query ON job_postings (search_query);
CREATE INDEX IF NOT EXISTS idx_skill ON job_skills (skill);
CREATE INDEX IF NOT EXISTS idx_skill_posting ON job_skills (posting_id);
"""


def get_connection() -> sqlite3.Connection:
    """Open a connection to the local SQLite DB, creating the file/schema if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Create tables if they don't exist, and migrate existing DBs by adding
    new columns (redirect_url, full_description) if they're missing.
    SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS, so we
    catch the error when the column already exists.
    """
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        # Migrate existing databases: add new columns if they don't exist yet
        for col in ("redirect_url TEXT", "full_description TEXT"):
            col_name = col.split()[0]
            try:
                conn.execute(f"ALTER TABLE job_postings ADD COLUMN {col}")
                conn.commit()
                print(f"Migrated: added column '{col_name}' to job_postings")
            except sqlite3.OperationalError:
                pass  # column already exists, nothing to do
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
                     redirect_url, salary_min, salary_max, category,
                     posted_date, pulled_date, search_query)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row.get("source_id"),
                    row.get("title"),
                    row.get("company"),
                    row.get("location"),
                    row.get("description"),
                    row.get("redirect_url"),
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
            else:
                # Row already exists — backfill redirect_url if it was missing
                cur.execute(
                    """
                    UPDATE job_postings
                    SET redirect_url = ?
                    WHERE source_id = ? AND redirect_url IS NULL
                    """,
                    (row.get("redirect_url"), row.get("source_id")),
                )
        conn.commit()
    finally:
        conn.close()

    return inserted


def get_unenriched_postings() -> list[dict]:
    """Return postings that have a redirect_url but no full_description yet."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT id, redirect_url
            FROM job_postings
            WHERE redirect_url IS NOT NULL
              AND full_description IS NULL
            """
        )
        return [{"id": row[0], "redirect_url": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def update_full_description(posting_id: int, full_description: str) -> None:
    """Store the scraped full description for a single posting."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE job_postings SET full_description = ? WHERE id = ?",
            (full_description, posting_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_unprocessed_postings() -> list[dict]:
    """
    Return postings that have not yet had skills extracted.
    Prefers full_description over the truncated API description.
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            SELECT jp.id,
                   COALESCE(jp.full_description, jp.description) AS best_description
            FROM job_postings jp
            LEFT JOIN job_skills js ON jp.id = js.posting_id
            WHERE js.posting_id IS NULL
              AND COALESCE(jp.full_description, jp.description) IS NOT NULL
            """
        )
        return [{"id": row[0], "description": row[1]} for row in cur.fetchall()]
    finally:
        conn.close()


def insert_skills(rows: list[dict]) -> int:
    """
    Insert extracted skill rows. Each row must have:
        posting_id, skill, category, extracted_date
    Returns number of rows inserted.
    """
    if not rows:
        return 0

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT INTO job_skills (posting_id, skill, category, extracted_date)
            VALUES (:posting_id, :skill, :category, :extracted_date)
            """,
            rows,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


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