"""
SQLite database helpers for the Plant-Based Research Hub.
"""

import sqlite3
import json
from datetime import datetime


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a sqlite3 connection with row_factory set."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS studies (
            pmid TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            authors TEXT,
            journal TEXT,
            pub_date TEXT,
            pub_year INTEGER,
            abstract TEXT,
            study_type TEXT,
            quality_tier INTEGER,
            sample_size INTEGER,
            topics TEXT,
            funding_notes TEXT,
            doi TEXT,
            pubmed_url TEXT,
            date_added TEXT
        );

        CREATE TABLE IF NOT EXISTS summaries (
            topic TEXT PRIMARY KEY,
            current_consensus TEXT,
            evidence_evolution TEXT,
            agreements TEXT,
            conflicts TEXT,
            limitations TEXT,
            unknowns TEXT,
            study_count INTEGER,
            last_updated TEXT,
            latest_study_year INTEGER
        );

        CREATE TABLE IF NOT EXISTS fetch_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fetch_date TEXT,
            topic TEXT,
            new_studies INTEGER,
            total_studies INTEGER
        );
    """)
    conn.commit()


def upsert_study(conn: sqlite3.Connection, study_dict: dict) -> None:
    """Insert or replace a study record."""
    conn.execute("""
        INSERT OR REPLACE INTO studies (
            pmid, title, authors, journal, pub_date, pub_year,
            abstract, study_type, quality_tier, sample_size,
            topics, funding_notes, doi, pubmed_url, date_added
        ) VALUES (
            :pmid, :title, :authors, :journal, :pub_date, :pub_year,
            :abstract, :study_type, :quality_tier, :sample_size,
            :topics, :funding_notes, :doi, :pubmed_url, :date_added
        )
    """, study_dict)
    conn.commit()


def get_studies_for_topic(
    conn: sqlite3.Connection,
    topic: str,
    min_quality_tier: int = 5,
) -> list[dict]:
    """Return all studies for a given topic ordered by pub_year ASC.

    min_quality_tier: include studies with quality_tier <= this value.
    """
    cursor = conn.execute("""
        SELECT * FROM studies
        WHERE topics LIKE ? AND quality_tier <= ?
        ORDER BY pub_year ASC
    """, (f'%"{topic}"%', min_quality_tier))
    rows = cursor.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["topics"] = json.loads(d["topics"]) if d["topics"] else []
        except (json.JSONDecodeError, TypeError):
            d["topics"] = []
        result.append(d)
    return result


def get_summary(conn: sqlite3.Connection, topic: str) -> dict | None:
    """Return the summary dict for a topic, or None if not found."""
    cursor = conn.execute("SELECT * FROM summaries WHERE topic = ?", (topic,))
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_summary(
    conn: sqlite3.Connection,
    topic: str,
    sections_dict: dict,
    study_count: int,
    latest_year: int | None,
) -> None:
    """Insert or replace a topic summary."""
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO summaries (
            topic,
            current_consensus,
            evidence_evolution,
            agreements,
            conflicts,
            limitations,
            unknowns,
            study_count,
            last_updated,
            latest_study_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        topic,
        sections_dict.get("current_consensus", ""),
        sections_dict.get("evidence_evolution", ""),
        sections_dict.get("agreements", ""),
        sections_dict.get("conflicts", ""),
        sections_dict.get("limitations", ""),
        sections_dict.get("unknowns", ""),
        study_count,
        now,
        latest_year,
    ))
    conn.commit()


def get_study_count(conn: sqlite3.Connection, topic: str) -> int:
    """Return the number of studies tagged with a given topic."""
    cursor = conn.execute(
        "SELECT COUNT(*) FROM studies WHERE topics LIKE ?",
        (f'%"{topic}"%',),
    )
    return cursor.fetchone()[0]


def log_fetch(
    conn: sqlite3.Connection,
    topic: str,
    new_count: int,
    total_count: int,
) -> None:
    """Record a fetch event in the fetch_log table."""
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO fetch_log (fetch_date, topic, new_studies, total_studies)
        VALUES (?, ?, ?, ?)
    """, (now, topic, new_count, total_count))
    conn.commit()


def study_exists(conn: sqlite3.Connection, pmid: str) -> bool:
    """Return True if the given PMID is already in the database."""
    cursor = conn.execute(
        "SELECT 1 FROM studies WHERE pmid = ?", (pmid,)
    )
    return cursor.fetchone() is not None


def get_all_studies(conn: sqlite3.Connection) -> list[dict]:
    """Return all studies ordered by pub_year DESC."""
    cursor = conn.execute("SELECT * FROM studies ORDER BY pub_year DESC")
    rows = cursor.fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["topics"] = json.loads(d["topics"]) if d["topics"] else []
        except (json.JSONDecodeError, TypeError):
            d["topics"] = []
        result.append(d)
    return result


def update_study_topics(conn: sqlite3.Connection, pmid: str, new_topic: str) -> None:
    """Add a topic to an existing study's topics JSON array if not already present."""
    cursor = conn.execute("SELECT topics FROM studies WHERE pmid = ?", (pmid,))
    row = cursor.fetchone()
    if row is None:
        return
    try:
        topics = json.loads(row["topics"]) if row["topics"] else []
    except (json.JSONDecodeError, TypeError):
        topics = []
    if new_topic not in topics:
        topics.append(new_topic)
        conn.execute(
            "UPDATE studies SET topics = ? WHERE pmid = ?",
            (json.dumps(topics), pmid),
        )
        conn.commit()
