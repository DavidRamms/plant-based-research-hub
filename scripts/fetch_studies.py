"""
Fetches plant-based diet research studies from PubMed NCBI E-utilities.
"""

import sys
import re
import json
import time
import sqlite3
from datetime import datetime
from typing import Optional

import requests
from lxml import etree

from config import TOPICS, STUDY_QUALITY_TIERS, RATE_LIMIT_DELAY, BOOTSTRAP_YEARS
from database import (
    upsert_study,
    study_exists,
    update_study_topics,
    get_study_count,
    log_fetch,
)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _get_with_retry(url: str, params: dict, retries: int = 1) -> Optional[requests.Response]:
    """GET request with one retry on failure."""
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt < retries:
                print(f"  [WARN] Request failed ({exc}), retrying...", file=sys.stderr)
                time.sleep(1.0)
            else:
                print(f"  [ERROR] Request failed after retry: {exc}", file=sys.stderr)
                return None


def search_pubmed(
    query: str,
    max_results: int = 200,
    date_range_years: Optional[int] = None,
) -> list[str]:
    """Search PubMed and return a list of PMIDs."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
    }
    if date_range_years is not None:
        params["datetype"] = "pdat"
        params["reldate"] = date_range_years * 365

    time.sleep(RATE_LIMIT_DELAY)
    response = _get_with_retry(ESEARCH_URL, params)
    if response is None:
        return []

    try:
        data = response.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except (ValueError, KeyError) as exc:
        print(f"  [ERROR] Failed to parse esearch JSON: {exc}", file=sys.stderr)
        return []


def _detect_study_type(publication_types: list[str]) -> tuple[str, int]:
    """Return (study_type_string, quality_tier) from a list of PubMed publication type strings."""
    # Check in priority order (best quality first)
    for pub_type in publication_types:
        pub_type_stripped = pub_type.strip()
        if pub_type_stripped in ("Meta-Analysis", "Systematic Review"):
            return "meta-analysis", 1
        if pub_type_stripped in (
            "Randomized Controlled Trial",
            "Clinical Trial, Phase III",
            "Clinical Trial, Phase II",
            "Controlled Clinical Trial",
        ):
            return "RCT", 2

    for pub_type in publication_types:
        pub_type_stripped = pub_type.strip()
        if pub_type_stripped in (
            "Observational Study",
            "Cohort Studies",
            "Longitudinal Studies",
            "Prospective Studies",
        ):
            return "cohort", 3
        if pub_type_stripped == "Review":
            return "review", 3

    for pub_type in publication_types:
        pub_type_stripped = pub_type.strip()
        if pub_type_stripped in (
            "Cross-Sectional Studies",
            "Case-Control Studies",
            "Retrospective Studies",
        ):
            return "cross-sectional", 4

    for pub_type in publication_types:
        pub_type_stripped = pub_type.strip()
        if pub_type_stripped in ("Case Reports", "Editorial", "Comment", "Letter"):
            return "case/opinion", 5

    return "observational", 3


def _extract_sample_size(abstract: str) -> Optional[int]:
    """Extract the largest plausible sample size from abstract text."""
    if not abstract:
        return None

    patterns = [
        r'\bn\s*=\s*([0-9,]+)',
        r'\bN\s*=\s*([0-9,]+)',
        r'([0-9,]+)\s+participants',
        r'([0-9,]+)\s+patients',
        r'([0-9,]+)\s+subjects',
        r'([0-9,]+)\s+individuals',
        r'([0-9,]+)\s+adults',
        r'([0-9,]+)\s+men\b',
        r'([0-9,]+)\s+women\b',
    ]

    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, abstract, re.IGNORECASE):
            raw = match.group(1).replace(",", "")
            try:
                n = int(raw)
                if 2 <= n < 1_000_000:
                    found.append(n)
            except ValueError:
                pass

    return max(found) if found else None


def _extract_funding_notes(abstract: str) -> Optional[str]:
    """Check last 200 chars of abstract for funding/conflict mentions."""
    if not abstract:
        return None
    tail = abstract[-200:].lower()
    keywords = [
        "conflict of interest",
        "funding",
        "supported by",
        "grant",
        "sponsored by",
        "financial disclosure",
        "industry",
    ]
    for kw in keywords:
        if kw in tail:
            # Return the raw tail (original case) trimmed
            return abstract[-200:].strip()
    return None


def fetch_study_details(pmids: list[str]) -> list[dict]:
    """Fetch full study details for a list of PMIDs. Batches in groups of 20."""
    if not pmids:
        return []

    results = []
    batch_size = 20

    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        ids_str = ",".join(batch)

        params = {
            "db": "pubmed",
            "id": ids_str,
            "rettype": "xml",
            "retmode": "xml",
        }

        time.sleep(RATE_LIMIT_DELAY)
        response = _get_with_retry(EFETCH_URL, params)
        if response is None:
            continue

        try:
            root = etree.fromstring(response.content)
        except etree.XMLSyntaxError as exc:
            print(f"  [ERROR] Failed to parse XML: {exc}", file=sys.stderr)
            continue

        for article in root.findall(".//PubmedArticle"):
            try:
                study = _parse_article(article)
                if study:
                    results.append(study)
            except Exception as exc:
                print(f"  [ERROR] Failed to parse article: {exc}", file=sys.stderr)

    return results


def _parse_article(article: etree._Element) -> Optional[dict]:
    """Parse a single PubmedArticle XML element into a study dict."""
    # PMID — first occurrence
    pmid_el = article.find(".//PMID")
    if pmid_el is None or not pmid_el.text:
        return None
    pmid = pmid_el.text.strip()

    # Title
    title_el = article.find(".//ArticleTitle")
    title = ""
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()
    if not title:
        return None

    # Abstract — join multiple AbstractText elements
    abstract_parts = []
    for at in article.findall(".//AbstractText"):
        label = at.get("Label", "")
        text = "".join(at.itertext()).strip()
        if text:
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
    abstract = " ".join(abstract_parts)

    # Authors — first 3, then "et al."
    authors_list = []
    for author_el in article.findall(".//Author"):
        last = author_el.findtext("LastName", "").strip()
        initials = author_el.findtext("Initials", "").strip()
        if last:
            authors_list.append(f"{last} {initials}".strip())
    if len(authors_list) > 3:
        authors = ", ".join(authors_list[:3]) + " et al."
    else:
        authors = ", ".join(authors_list)

    # Journal
    journal = (
        article.findtext(".//Journal/ISOAbbreviation")
        or article.findtext(".//MedlineTA")
        or ""
    ).strip()

    # Publication date
    pub_date = ""
    pub_year = None
    year_el = article.find(".//PubDate/Year")
    month_el = article.find(".//PubDate/Month")
    day_el = article.find(".//PubDate/Day")
    if year_el is not None and year_el.text:
        pub_year = int(year_el.text.strip())
        pub_date = year_el.text.strip()
        if month_el is not None and month_el.text:
            pub_date += f"-{month_el.text.strip()}"
            if day_el is not None and day_el.text:
                pub_date += f"-{day_el.text.strip()}"
    else:
        # Try MedlineDate
        medline_el = article.find(".//PubDate/MedlineDate")
        if medline_el is not None and medline_el.text:
            pub_date = medline_el.text.strip()
            # Extract first 4-digit year
            year_match = re.search(r"\b(19|20)\d{2}\b", pub_date)
            if year_match:
                pub_year = int(year_match.group())

    # DOI
    doi = ""
    for aid in article.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = (aid.text or "").strip()
            break

    # Publication types
    publication_types = []
    for pt in article.findall(".//PublicationType"):
        if pt.text:
            publication_types.append(pt.text.strip())

    study_type, quality_tier = _detect_study_type(publication_types)

    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    sample_size = _extract_sample_size(abstract)
    funding_notes = _extract_funding_notes(abstract)

    return {
        "pmid": pmid,
        "title": title,
        "authors": authors,
        "journal": journal,
        "pub_date": pub_date,
        "pub_year": pub_year,
        "abstract": abstract,
        "study_type": study_type,
        "quality_tier": quality_tier,
        "sample_size": sample_size,
        "topics": json.dumps([]),  # Will be set by caller
        "funding_notes": funding_notes,
        "doi": doi,
        "pubmed_url": pubmed_url,
        "date_added": datetime.utcnow().isoformat(),
    }


def fetch_all_topics(
    conn: sqlite3.Connection,
    is_bootstrap: bool = False,
) -> dict[str, int]:
    """Fetch studies for all topics and store in the database.

    Returns dict of {topic_key: new_study_count}.
    """
    date_range_years = BOOTSTRAP_YEARS if is_bootstrap else 1
    new_counts: dict[str, int] = {}

    for topic_key, topic_config in TOPICS.items():
        print(f"  Fetching topic: {topic_config['name']}")
        all_pmids: set[str] = set()

        for query in topic_config["queries"]:
            pmids = search_pubmed(
                query,
                max_results=200,
                date_range_years=date_range_years,
            )
            all_pmids.update(pmids)
            print(f"    Query returned {len(pmids)} PMIDs")

        print(f"    Total unique PMIDs: {len(all_pmids)}")

        # Split into new vs. existing
        new_pmids = [p for p in all_pmids if not study_exists(conn, p)]
        existing_pmids = [p for p in all_pmids if study_exists(conn, p)]

        print(f"    New: {len(new_pmids)}, Already in DB: {len(existing_pmids)}")

        # Update topics for existing studies that were found under a new topic
        for pmid in existing_pmids:
            update_study_topics(conn, pmid, topic_key)

        # Fetch details for new PMIDs
        if new_pmids:
            studies = fetch_study_details(new_pmids)
            for study in studies:
                study["topics"] = json.dumps([topic_key])
                upsert_study(conn, study)

        new_counts[topic_key] = len(new_pmids)
        total = get_study_count(conn, topic_key)
        log_fetch(conn, topic_key, len(new_pmids), total)
        print(f"    Done. Total studies for topic: {total}")

    return new_counts
