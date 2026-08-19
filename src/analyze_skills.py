"""
analyze_skills.py - Quick analysis of extracted skills across all postings.

Run AFTER nlp_extract.py has been run at least once.
Run: python src/analyze_skills.py
"""
import sqlite3
import pandas as pd

from db import DB_PATH

conn = sqlite3.connect(DB_PATH)

# --- 1. Overall top 20 skills ---
top_skills = pd.read_sql_query(
    """
    SELECT skill, category, COUNT(*) as postings
    FROM job_skills
    GROUP BY skill
    ORDER BY postings DESC
    LIMIT 20
    """,
    conn,
)

# --- 2. Top skills broken out by search query (role type) ---
by_role = pd.read_sql_query(
    """
    SELECT jp.search_query, js.skill, COUNT(*) as postings
    FROM job_skills js
    JOIN job_postings jp ON js.posting_id = jp.id
    GROUP BY jp.search_query, js.skill
    ORDER BY jp.search_query, postings DESC
    """,
    conn,
)

# --- 3. Top skills per category ---
by_category = pd.read_sql_query(
    """
    SELECT category, skill, COUNT(*) as postings
    FROM job_skills
    GROUP BY category, skill
    ORDER BY category, postings DESC
    """,
    conn,
)

conn.close()

# --- Print results ---
pd.set_option("display.max_colwidth", 30)
pd.set_option("display.max_rows", 50)

print("=" * 50)
print("TOP 20 SKILLS ACROSS ALL POSTINGS")
print("=" * 50)
print(top_skills.to_string(index=False))

print("\n" + "=" * 50)
print("TOP 5 SKILLS PER ROLE TYPE")
print("=" * 50)
for query, group in by_role.groupby("search_query"):
    print(f"\n{query.upper()}")
    print(group.head(5)[["skill", "postings"]].to_string(index=False))

print("\n" + "=" * 50)
print("TOP 3 SKILLS PER CATEGORY")
print("=" * 50)
for category, group in by_category.groupby("category"):
    print(f"\n{category}")
    print(group.head(3)[["skill", "postings"]].to_string(index=False))