"""
Generates AI narrative summaries for each research topic using Groq.
"""

import json
import os
import re
import sqlite3

from groq import Groq

from config import TOPICS, GROQ_MODEL, MIN_QUALITY_FOR_NARRATIVE
from database import (
    get_studies_for_topic,
    get_summary,
    upsert_summary,
    get_study_count,
)

_groq_client: Groq | None = None


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _groq_client


def format_studies_for_prompt(studies: list[dict]) -> str:
    """Format a list of study dicts into a readable block for the prompt."""
    lines = []
    for study in studies:
        sample = study.get("sample_size")
        sample_str = str(sample) if sample else "NR"
        abstract = study.get("abstract") or ""
        funding = study.get("funding_notes") or ""

        block = (
            f"[PMID: {study.get('pmid', 'N/A')}] "
            f"[{study.get('study_type', 'unknown')}, n={sample_str}] "
            f"{study.get('pub_year', 'N/A')}\n"
            f"Title: {study.get('title', '')}\n"
            f"Authors: {study.get('authors', '')}\n"
            f"Journal: {study.get('journal', '')}\n"
            f"Abstract: {abstract[:600]}{'...' if len(abstract) > 600 else ''}\n"
        )
        if funding:
            block += f"Funding notes: {funding}\n"
        block += "---"
        lines.append(block)
    return "\n".join(lines)


SYSTEM_PROMPT = (
    "You are a scientific research analyst specializing in plant-based nutrition. "
    "You write clear, evidence-based summaries for a general audience. "
    "You always cite sources using [Author et al., Year, PMID: XXXXX] format. "
    "You use direct quotes from abstracts in \"quotation marks\" with citation. "
    "You never speculate beyond what studies state. "
    "You clearly label study quality: [Meta-analysis, n=X], [RCT, n=X], [Cohort, n=X]."
)


def _build_user_prompt(topic_key: str, topic_config: dict, studies: list[dict]) -> str:
    formatted = format_studies_for_prompt(studies)
    topic_name = topic_config["name"]
    n_studies = len(studies)

    return f"""Please analyze the following {n_studies} research studies on the topic: **{topic_name}**.

Generate a structured JSON response with exactly these six keys:

1. "current_consensus" — What does the current body of evidence say? Cite the strongest studies (meta-analyses and RCTs first). Use [Author et al., Year, PMID: XXXXX] format for citations.

2. "evidence_evolution" — How has the scientific understanding of this topic changed over time? Note shifts in methodology, sample sizes, or conclusions across the time range of studies provided.

3. "agreements" — What do most or all studies agree on? List the key points of convergence with supporting citations.

4. "conflicts" — Where do studies disagree? Describe genuine scientific disagreements (not just absence of evidence), with citations for each side.

5. "limitations" — IMPORTANT: Only include methodological limitations that are structurally inherent or explicitly acknowledged in the studies themselves. Valid limitation types: self-reported dietary data, healthy user bias, short follow-up duration, industry or conflict-of-interest funding, use of surrogate markers rather than hard clinical endpoints, limited generalizability due to study population characteristics. Do NOT include speculation or generic disclaimers. Cite specific studies where these limitations are noted.

6. "unknowns" — What research questions remain unanswered? What study types or populations are missing from the evidence base?

Respond ONLY with a valid JSON object (no markdown, no code blocks, no preamble). All six keys must be present.

---
STUDIES:

{formatted}
"""


def _parse_json_response(text: str) -> dict | None:
    """Extract and parse JSON from a model response."""
    # Strip markdown code fences if present
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if code_block:
        text = code_block.group(1)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find first { ... } block
        brace_match = re.search(r"\{[\s\S]+\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass
    return None


def generate_topic_summary(
    topic_key: str,
    topic_config: dict,
    studies: list[dict],
) -> dict:
    """Generate a 6-section summary dict for a topic using the Groq API."""
    client = _get_client()
    user_prompt = _build_user_prompt(topic_key, topic_config, studies)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # First attempt
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    result = _parse_json_response(raw_text)

    if result is None:
        # Retry with explicit instructions
        print(f"    [WARN] JSON parse failed for {topic_key}, retrying...")
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({
            "role": "user",
            "content": (
                "Your previous response could not be parsed as JSON. "
                "Please respond ONLY with a valid JSON object containing exactly these keys: "
                "current_consensus, evidence_evolution, agreements, conflicts, limitations, unknowns. "
                "No markdown, no code blocks, no extra text."
            ),
        })
        retry_response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw_text = retry_response.choices[0].message.content or ""
        result = _parse_json_response(raw_text)

    if result is None:
        print(f"    [ERROR] Could not parse JSON for {topic_key}, using empty summary.")
        result = {
            "current_consensus": "Summary generation failed. Please try again.",
            "evidence_evolution": "",
            "agreements": "",
            "conflicts": "",
            "limitations": "",
            "unknowns": "",
        }

    # Ensure all keys are present
    for key in ("current_consensus", "evidence_evolution", "agreements", "conflicts", "limitations", "unknowns"):
        result.setdefault(key, "")

    return result


def update_summaries_for_topics(
    conn: sqlite3.Connection,
    topics_with_new_studies: list[str],
    force_all: bool = False,
) -> None:
    """Generate or regenerate summaries for topics that need updating."""
    if force_all:
        topics_to_update = list(TOPICS.keys())
        print(f"  Force-regenerating all {len(topics_to_update)} topic summaries...")
    else:
        topics_to_update = topics_with_new_studies
        print(f"  Regenerating summaries for {len(topics_to_update)} topics with new studies...")

    for topic_key in topics_to_update:
        topic_config = TOPICS.get(topic_key)
        if topic_config is None:
            print(f"  [WARN] Unknown topic key: {topic_key}")
            continue

        print(f"  Generating summary for: {topic_config['name']}")

        # Only use studies meeting quality threshold (tier 1 through MIN_QUALITY_FOR_NARRATIVE)
        studies = get_studies_for_topic(conn, topic_key, min_quality_tier=MIN_QUALITY_FOR_NARRATIVE)

        if not studies:
            print(f"    No qualifying studies found for {topic_key}, skipping.")
            continue

        print(f"    Using {len(studies)} qualifying studies (tier 1-{MIN_QUALITY_FOR_NARRATIVE})...")

        sections = generate_topic_summary(topic_key, topic_config, studies)

        # Determine latest study year
        years = [s["pub_year"] for s in studies if s.get("pub_year")]
        latest_year = max(years) if years else None

        upsert_summary(conn, topic_key, sections, len(studies), latest_year)
        print(f"    Summary saved.")
