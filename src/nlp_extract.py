"""
nlp_extract.py - Extract in-demand skills from job descriptions using keyword matching.

Design choice: keyword matching over a curated skill list, not spaCy NER.
Job descriptions are not clean prose -- they're dense bullet lists. A targeted
match against a known skill vocabulary is more precise and more defensible
than a general NLP model for this use case.

Run: python src/nlp_extract.py
Safe to re-run: only processes postings that don't yet have skill rows.
"""

import re
from datetime import date

from db import get_unprocessed_postings, insert_skills, init_db

# ---------------------------------------------------------------------------
# Skill vocabulary
# Keys are the canonical display name stored in the DB.
# Values are regex patterns that match how the skill appears in job text.
# Patterns are case-insensitive and use word boundaries to avoid partial matches
# (e.g. "R" won't match inside "Oracle" or "framework").
# ---------------------------------------------------------------------------
SKILLS: dict[str, dict] = {
    # --- Languages ---
    "Python":           {"category": "Language", "pattern": r"\bpython\b"},
    "R":                {"category": "Language", "pattern": r"\br\b"},
    "SQL":              {"category": "Language", "pattern": r"\bsql\b"},
    "Java":             {"category": "Language", "pattern": r"\bjava\b"},
    "Scala":            {"category": "Language", "pattern": r"\bscala\b"},
    "Julia":            {"category": "Language", "pattern": r"\bjulia\b"},
    "MATLAB":           {"category": "Language", "pattern": r"\bmatlab\b"},
    "Bash":             {"category": "Language", "pattern": r"\bbash\b"},

    # --- Databases ---
    "PostgreSQL":       {"category": "Database", "pattern": r"\bpostgresql\b|\bpostgres\b"},
    "MySQL":            {"category": "Database", "pattern": r"\bmysql\b"},
    "SQLite":           {"category": "Database", "pattern": r"\bsqlite\b"},
    "SQL Server":       {"category": "Database", "pattern": r"\bsql\s*server\b"},
    "Oracle":           {"category": "Database", "pattern": r"\boracle\b"},
    "MongoDB":          {"category": "Database", "pattern": r"\bmongodb\b"},
    "Snowflake":        {"category": "Database", "pattern": r"\bsnowflake\b"},
    "Redshift":         {"category": "Database", "pattern": r"\bredshift\b"},
    "BigQuery":         {"category": "Database", "pattern": r"\bbigquery\b"},
    "Cassandra":        {"category": "Database", "pattern": r"\bcassandra\b"},

    # --- Cloud platforms ---
    "AWS":              {"category": "Cloud", "pattern": r"\baws\b|\bamazon\s+web\s+services\b"},
    "Azure":            {"category": "Cloud", "pattern": r"\bazure\b"},
    "GCP":              {"category": "Cloud", "pattern": r"\bgcp\b|\bgoogle\s+cloud\b"},

    # --- Data engineering tools ---
    "Spark":            {"category": "Data Engineering", "pattern": r"\bspark\b|\bpyspark\b"},
    "Kafka":            {"category": "Data Engineering", "pattern": r"\bkafka\b"},
    "Airflow":          {"category": "Data Engineering", "pattern": r"\bairflow\b"},
    "dbt":              {"category": "Data Engineering", "pattern": r"\bdbt\b"},
    "Hadoop":           {"category": "Data Engineering", "pattern": r"\bhadoop\b"},
    "ETL":              {"category": "Data Engineering", "pattern": r"\betl\b"},
    "Databricks":       {"category": "Data Engineering", "pattern": r"\bdatabricks\b"},

    # --- ML / AI ---
    "Machine Learning": {"category": "ML/AI", "pattern": r"\bmachine\s+learning\b"},
    "Deep Learning":    {"category": "ML/AI", "pattern": r"\bdeep\s+learning\b"},
    "NLP":              {"category": "ML/AI", "pattern": r"\bnlp\b|\bnatural\s+language\s+processing\b"},
    "scikit-learn":     {"category": "ML/AI", "pattern": r"\bscikit[\-\s]?learn\b|\bsklearn\b"},
    "TensorFlow":       {"category": "ML/AI", "pattern": r"\btensorflow\b"},
    "PyTorch":          {"category": "ML/AI", "pattern": r"\bpytorch\b"},
    "XGBoost":          {"category": "ML/AI", "pattern": r"\bxgboost\b"},
    "LLM":              {"category": "ML/AI", "pattern": r"\bllm\b|\blarge\s+language\s+model\b"},

    # --- Data analysis / viz ---
    "pandas":           {"category": "Analysis", "pattern": r"\bpandas\b"},
    "NumPy":            {"category": "Analysis", "pattern": r"\bnumpy\b"},
    "Excel":            {"category": "Analysis", "pattern": r"\bexcel\b"},
    "Tableau":          {"category": "Analysis", "pattern": r"\btableau\b"},
    "Power BI":         {"category": "Analysis", "pattern": r"\bpower\s*bi\b"},
    "Looker":           {"category": "Analysis", "pattern": r"\blooker\b"},
    "matplotlib":       {"category": "Analysis", "pattern": r"\bmatplotlib\b"},
    "Seaborn":          {"category": "Analysis", "pattern": r"\bseaborn\b"},
    "Plotly":           {"category": "Analysis", "pattern": r"\bplotly\b"},

    # --- Statistics ---
    "Statistics":       {"category": "Statistics", "pattern": r"\bstatistics\b|\bstatistical\b"},
    "A/B Testing":      {"category": "Statistics", "pattern": r"\ba/?b\s+test(ing)?\b"},
    "Regression":       {"category": "Statistics", "pattern": r"\bregression\b"},
    "Hypothesis Testing": {"category": "Statistics", "pattern": r"\bhypothesis\s+test(ing)?\b"},

    # --- Dev tools / practices ---
    "Git":              {"category": "Dev Tools", "pattern": r"\bgit\b"},
    "Docker":           {"category": "Dev Tools", "pattern": r"\bdocker\b"},
    "Kubernetes":       {"category": "Dev Tools", "pattern": r"\bkubernetes\b|\bk8s\b"},
    "CI/CD":            {"category": "Dev Tools", "pattern": r"\bci/?cd\b"},
    "REST API":         {"category": "Dev Tools", "pattern": r"\brest\s*api\b|\brestful\b"},
    "Agile":            {"category": "Dev Tools", "pattern": r"\bagile\b|\bscrum\b"},
    "Linux":            {"category": "Dev Tools", "pattern": r"\blinux\b|\bunix\b"},

    # --- Soft / business skills ---
    "Communication":    {"category": "Soft Skills", "pattern": r"\bcommunication\b"},
    "Stakeholder Management": {"category": "Soft Skills", "pattern": r"\bstakeholder\b"},
    "Data Storytelling": {"category": "Soft Skills", "pattern": r"\bdata\s+storytelling\b|\bstorytelling\b"},
}

# Pre-compile all patterns once at import time for performance
_COMPILED: dict[str, re.Pattern] = {
    skill: re.compile(meta["pattern"], re.IGNORECASE)
    for skill, meta in SKILLS.items()
}


def extract_skills(text: str) -> list[str]:
    """Return a deduplicated list of skill names found in text."""
    return [skill for skill, pattern in _COMPILED.items() if pattern.search(text)]


def process_all() -> None:
    init_db()
    postings = get_unprocessed_postings()

    if not postings:
        print("No unprocessed postings found — everything is up to date.")
        return

    print(f"Processing {len(postings)} postings...")

    today = date.today().isoformat()
    skill_rows = []

    for posting in postings:
        found = extract_skills(posting["description"])
        for skill in found:
            skill_rows.append(
                {
                    "posting_id": posting["id"],
                    "skill": skill,
                    "category": SKILLS[skill]["category"],
                    "extracted_date": today,
                }
            )

    inserted = insert_skills(skill_rows)
    unique_postings = len({r["posting_id"] for r in skill_rows})
    print(f"Done. Inserted {inserted} skill rows across {unique_postings} postings.")


if __name__ == "__main__":
    process_all()