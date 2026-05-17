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

        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_sentence TEXT NOT NULL,
            original_quote TEXT,
            outcome TEXT,
            topic TEXT,
            direction TEXT,
            magnitude TEXT,
            diet_type TEXT,
            pmid TEXT,
            authors TEXT,
            year INTEGER,
            study_type TEXT,
            quality_tier INTEGER,
            is_null_finding INTEGER DEFAULT 0,
            is_contested INTEGER DEFAULT 0,
            confidence_interval TEXT,
            date_extracted TEXT
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


def insert_stats_for_topic(
    conn: sqlite3.Connection,
    topic: str,
    stats_list: list[dict],
) -> None:
    """Delete existing stats for topic and insert the new list."""
    today = datetime.utcnow().date().isoformat()
    conn.execute("DELETE FROM stats WHERE topic = ?", (topic,))
    for stat in stats_list:
        conn.execute("""
            INSERT INTO stats (
                stat_sentence, original_quote, outcome, topic, direction, magnitude,
                diet_type, pmid, authors, year, study_type, quality_tier,
                is_null_finding, is_contested, confidence_interval, date_extracted
            ) VALUES (
                :stat_sentence, :original_quote, :outcome, :topic, :direction, :magnitude,
                :diet_type, :pmid, :authors, :year, :study_type, :quality_tier,
                :is_null_finding, :is_contested, :confidence_interval, :date_extracted
            )
        """, {
            "stat_sentence": stat.get("stat_sentence", ""),
            "original_quote": stat.get("original_quote"),
            "outcome": stat.get("outcome"),
            "topic": topic,
            "direction": stat.get("direction"),
            "magnitude": stat.get("magnitude"),
            "diet_type": stat.get("diet_type"),
            "pmid": stat.get("pmid"),
            "authors": stat.get("authors"),
            "year": stat.get("year"),
            "study_type": stat.get("study_type"),
            "quality_tier": stat.get("quality_tier"),
            "is_null_finding": 1 if stat.get("is_null_finding") else 0,
            "is_contested": 0,
            "confidence_interval": stat.get("confidence_interval"),
            "date_extracted": today,
        })
    conn.commit()


def get_stats(
    conn: sqlite3.Connection,
    topic: str | None = None,
    quality_tier_max: int | None = None,
    direction: str | None = None,
) -> list[dict]:
    """Return stats as list of dicts. Optional filters: topic, quality_tier_max, direction."""
    query = "SELECT * FROM stats WHERE 1=1"
    params: list = []
    if topic is not None:
        query += " AND topic = ?"
        params.append(topic)
    if quality_tier_max is not None:
        query += " AND quality_tier <= ?"
        params.append(quality_tier_max)
    if direction is not None:
        query += " AND direction = ?"
        params.append(direction)
    query += " ORDER BY quality_tier ASC, year DESC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_top_stats(conn: sqlite3.Connection, n: int = 20) -> list[dict]:
    """Return top N stats ordered by quality_tier ASC then year DESC."""
    cursor = conn.execute(
        "SELECT * FROM stats ORDER BY quality_tier ASC, year DESC LIMIT ?", (n,)
    )
    return [dict(row) for row in cursor.fetchall()]


def mark_contested_stats(conn: sqlite3.Connection) -> None:
    """For each (topic, outcome) pair with conflicting directions, set is_contested=1."""
    # Find pairs that have both 'reduction' and 'increase'
    cursor = conn.execute("""
        SELECT topic, outcome
        FROM stats
        WHERE direction IN ('reduction', 'increase')
        GROUP BY topic, outcome
        HAVING COUNT(DISTINCT direction) >= 2
    """)
    contested_pairs = cursor.fetchall()
    for row in contested_pairs:
        conn.execute("""
            UPDATE stats SET is_contested = 1
            WHERE topic = ? AND outcome = ?
        """, (row["topic"], row["outcome"]))
    conn.commit()


def get_all_stats(conn: sqlite3.Connection) -> list[dict]:
    """Return all stats ordered by quality_tier ASC, year DESC."""
    cursor = conn.execute("SELECT * FROM stats ORDER BY quality_tier ASC, year DESC")
    return [dict(row) for row in cursor.fetchall()]
