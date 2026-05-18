"""
Generates AI narrative summaries for each research topic using Groq.
"""

import json
import os
import re
import sqlite3
import time

from groq import Groq

from config import TOPICS, GROQ_MODEL, GROQ_STATS_MODEL, MIN_QUALITY_FOR_NARRATIVE, MAX_STUDIES_PER_SUMMARY, MAX_STUDIES_PER_EXTRACTION, EXTRACTION_CALL_DELAY
from database import (
    get_studies_for_topic,
    get_summary,
    upsert_summary,
    get_study_count,
    insert_stats_for_topic,
    mark_contested_stats,
    insert_contested_for_topic,
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
            f"Abstract: {abstract[:200]}{'...' if len(abstract) > 200 else ''}\n"
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

        total_qualifying = len(studies)

        # Cap studies sent to Groq: prioritise by quality tier (ascending = better first),
        # then by recency (descending). This keeps prompts within Groq's free-tier limits.
        studies_sorted = sorted(
            studies,
            key=lambda s: (s.get("quality_tier") or 5, -(s.get("pub_year") or 0)),
        )
        studies_for_prompt = studies_sorted[:MAX_STUDIES_PER_SUMMARY]

        print(
            f"    {total_qualifying} qualifying studies — "
            f"sending top {len(studies_for_prompt)} (by tier + recency) to Groq..."
        )

        try:
            sections = generate_topic_summary(topic_key, topic_config, studies_for_prompt)
        except Exception as exc:
            print(f"    [ERROR] Summary generation failed for {topic_key}: {exc}")
            continue

        # Determine latest study year across ALL qualifying studies (not just the capped set)
        years = [s["pub_year"] for s in studies if s.get("pub_year")]
        latest_year = max(years) if years else None

        upsert_summary(conn, topic_key, sections, total_qualifying, latest_year)
        print(f"    Summary saved.")


STATS_SYSTEM_PROMPT = (
    "You are extracting specific quantitative findings from peer-reviewed nutrition research. "
    "You extract only what is explicitly stated — never calculate, infer, or extrapolate. "
    "Every stat you extract must have a number that appears verbatim in the abstract."
)


def _build_stats_user_prompt(topic_key: str, topic_config: dict, studies: list[dict]) -> str:
    formatted = format_studies_for_prompt(studies)
    topic_name = topic_config["name"]
    n_studies = len(studies)

    return f"""Extract all qualifying quantitative findings from the following {n_studies} peer-reviewed studies on: **{topic_name}**.

A finding qualifies if it has ALL of:
1. A specific percentage, number, or ratio appearing explicitly in the abstract
2. A named health outcome
3. An explicit or implied comparison group (vs omnivores, vs baseline, vs meat-eaters)

For null findings (no significant difference found), extract them too with direction="null".

Respond ONLY with valid JSON containing a single key "stats" whose value is an array. Each element must have these fields:

{{
  "stat_sentence": "Vegan diets were associated with a 34% lower risk of cardiovascular mortality compared to omnivores",
  "original_quote": "exact text from abstract containing this stat",
  "outcome": "cardiovascular mortality",
  "direction": "reduction",
  "magnitude": "34%",
  "diet_type": "vegan",
  "is_null_finding": false,
  "confidence_interval": "HR 0.66, 95% CI 0.52-0.84"
}}

Rules:
- diet_type must be one of: "vegan", "vegetarian", "plant-based", "meat-free", "other"
- direction must be one of: "reduction", "increase", "null"
- is_null_finding must be true only when direction is "null"
- confidence_interval may be null if not stated
- Only extract numbers that appear verbatim in the abstract — never calculate or estimate
- If a study has no qualifying findings, do not add it to the array

Respond ONLY with the JSON object. No markdown, no code blocks, no preamble.

---
STUDIES:

{formatted}
"""


def extract_stats_for_topic(
    topic_key: str,
    topic_config: dict,
    studies: list[dict],
) -> list[dict]:
    """Extract quotable statistics from tier 1-2 studies for a topic."""
    if not studies:
        return []

    client = _get_client()
    user_prompt = _build_stats_user_prompt(topic_key, topic_config, studies)

    messages = [
        {"role": "system", "content": STATS_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    # First attempt — use the 8b model (500k TPD) to keep stats off the 70b quota
    response = client.chat.completions.create(
        model=GROQ_STATS_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    result = _parse_json_response(raw_text)

    if result is None or "stats" not in result:
        # Retry once
        print(f"    [WARN] Stats JSON parse failed for {topic_key}, retrying...")
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({
            "role": "user",
            "content": (
                "Your previous response could not be parsed. "
                "Please respond ONLY with a valid JSON object containing exactly one key: "
                "\"stats\" whose value is an array of stat objects. "
                "No markdown, no code blocks, no extra text."
            ),
        })
        retry_response = client.chat.completions.create(
            model=GROQ_STATS_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw_text = retry_response.choices[0].message.content or ""
        result = _parse_json_response(raw_text)

    if result is None or "stats" not in result:
        print(f"    [ERROR] Could not parse stats JSON for {topic_key}, returning empty list.")
        return []

    stats_list = result["stats"]
    if not isinstance(stats_list, list):
        return []
    return stats_list


def extract_stats_for_all_topics(
    conn: sqlite3.Connection,
    topics_to_update: list[str],
    force_all: bool = False,
) -> None:
    """Extract and store quotable stats for topics that need updating."""
    if force_all:
        topics = list(TOPICS.keys())
        print(f"  Force-extracting stats for all {len(topics)} topics...")
    else:
        topics = topics_to_update
        print(f"  Extracting stats for {len(topics)} topics with new studies...")

    for topic_key in topics:
        topic_config = TOPICS.get(topic_key)
        if topic_config is None:
            print(f"  [WARN] Unknown topic key: {topic_key}")
            continue

        print(f"  Extracting stats for: {topic_config['name']}")

        # Tier 1-2 studies, capped to stay under 8b model's 6k TPM limit
        studies = get_studies_for_topic(conn, topic_key, min_quality_tier=2)
        studies = sorted(studies, key=lambda s: (s.get("quality_tier") or 5, -(s.get("pub_year") or 0)))
        studies = studies[:MAX_STUDIES_PER_EXTRACTION]

        if not studies:
            print(f"    No tier 1-2 studies found for {topic_key}, skipping.")
            insert_stats_for_topic(conn, topic_key, [])
            continue

        print(f"    Sending top {len(studies)} tier 1-2 studies to Groq...")

        try:
            raw_stats = extract_stats_for_topic(topic_key, topic_config, studies)
        except Exception as exc:
            print(f"    [ERROR] Stats extraction failed for {topic_key}: {exc}")
            continue

        # Enrich each stat with study metadata
        # Build a lookup from pmid to study record for enrichment
        pmid_to_study: dict[str, dict] = {s["pmid"]: s for s in studies}

        enriched: list[dict] = []
        for stat in raw_stats:
            # Try to find the study by matching original_quote or pmid hint in stat
            # We associate stats with a study by finding the study whose abstract
            # contains the original_quote text
            original_quote = stat.get("original_quote", "")
            matched_study: dict | None = None
            if original_quote:
                for study in studies:
                    abstract = study.get("abstract") or ""
                    if original_quote[:80].lower() in abstract.lower():
                        matched_study = study
                        break

            enriched_stat = dict(stat)
            enriched_stat["is_null_finding"] = 1 if stat.get("is_null_finding") else 0
            if matched_study:
                enriched_stat["pmid"] = matched_study.get("pmid")
                enriched_stat["authors"] = matched_study.get("authors")
                enriched_stat["year"] = matched_study.get("pub_year")
                enriched_stat["study_type"] = matched_study.get("study_type")
                enriched_stat["quality_tier"] = matched_study.get("quality_tier")
            else:
                enriched_stat.setdefault("pmid", None)
                enriched_stat.setdefault("authors", None)
                enriched_stat.setdefault("year", None)
                enriched_stat.setdefault("study_type", None)
                enriched_stat.setdefault("quality_tier", None)

            enriched.append(enriched_stat)

        insert_stats_for_topic(conn, topic_key, enriched)
        print(f"    Saved {len(enriched)} stats for {topic_key}.")
        time.sleep(EXTRACTION_CALL_DELAY)

    # Mark contested stats across all topics
    mark_contested_stats(conn)
    print("  Contested stats marked.")


CONTESTED_SYSTEM_PROMPT = (
    "You are a scientific analyst identifying studies that challenge plant-based or vegan diet "
    "recommendations. You extract only what is explicitly stated in abstracts. You are scrupulously "
    "honest — if a study is genuinely methodologically weak, you say so; if it is strong, you say so. "
    "You never fabricate counter-evidence that doesn't exist."
)


def _build_contested_user_prompt(topic_key: str, topic_config: dict, studies: list[dict]) -> str:
    """Build a prompt for contested claim extraction, truncating abstracts to 150 chars."""
    topic_name = topic_config["name"]
    n_studies = len(studies)

    # Format studies with 150-char abstract truncation to keep tokens down
    lines = []
    for study in studies:
        sample = study.get("sample_size")
        sample_str = str(sample) if sample else "NR"
        abstract = study.get("abstract") or ""
        funding = study.get("funding_notes") or ""
        block = (
            f"[PMID: {study.get('pmid', 'N/A')}] "
            f"[Tier {study.get('quality_tier', '?')}, {study.get('study_type', 'unknown')}, n={sample_str}] "
            f"{study.get('pub_year', 'N/A')}\n"
            f"Title: {study.get('title', '')}\n"
            f"Abstract: {abstract[:150]}{'...' if len(abstract) > 150 else ''}\n"
        )
        if funding:
            block += f"Funding: {funding}\n"
        block += "---"
        lines.append(block)
    formatted = "\n".join(lines)

    return f"""Review the following {n_studies} peer-reviewed studies on the topic: **{topic_name}**.

Identify studies that meet EITHER of these criteria:
1. **Direct negative finding**: the study reports that a plant-based, vegan, or vegetarian diet caused harm, increased disease risk, or led to worse health outcomes compared to omnivorous or meat-containing diets.
2. **Meat-positive finding**: the study reports that consuming meat, animal protein, or animal products provided a specific health benefit.

For each qualifying study, return a JSON object with these fields:

{{
  "pmid": "12345678",
  "claim_type": "negative",
  "claim_summary": "Plain English: what this study claims, in 1-2 sentences",
  "study_limitations": "Comma-separated list of limitations: both those stated in the abstract AND structurally inherent ones (self-reported dietary data, healthy user bias, short follow-up, surrogate markers, limited generalisability, industry funding). Be specific.",
  "industry_funding": "Name of funding body if meat/dairy/egg industry funded, otherwise null",
  "counter_evidence_exists": true,
  "counter_response": "What the broader evidence says — ONLY if higher-quality (lower tier), larger sample size, or more recent studies in the provided list contradict this finding. If no such evidence exists, set this to null and set counter_evidence_exists to false.",
  "contradicting_pmids": ["pmid1", "pmid2"]
}}

claim_type must be "negative" or "meat_positive".
Return JSON with key "contested" containing the array. Return empty array if no qualifying studies found.

---
STUDIES:

{formatted}
"""


def extract_contested_for_topic(
    topic_key: str,
    topic_config: dict,
    all_studies: list[dict],
) -> list[dict]:
    """Extract contested claims from ALL studies for a topic using the 8b model."""
    if not all_studies:
        return []

    client = _get_client()
    user_prompt = _build_contested_user_prompt(topic_key, topic_config, all_studies)

    messages = [
        {"role": "system", "content": CONTESTED_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    response = client.chat.completions.create(
        model=GROQ_STATS_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
        response_format={"type": "json_object"},
    )
    raw_text = response.choices[0].message.content or ""
    result = _parse_json_response(raw_text)

    if result is None or "contested" not in result:
        print(f"    [WARN] Contested JSON parse failed for {topic_key}, retrying...")
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({
            "role": "user",
            "content": (
                "Your previous response could not be parsed. "
                "Please respond ONLY with a valid JSON object containing exactly one key: "
                "\"contested\" whose value is an array of contested study objects. "
                "No markdown, no code blocks, no extra text."
            ),
        })
        retry_response = client.chat.completions.create(
            model=GROQ_STATS_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        raw_text = retry_response.choices[0].message.content or ""
        result = _parse_json_response(raw_text)

    if result is None or "contested" not in result:
        print(f"    [ERROR] Could not parse contested JSON for {topic_key}, returning empty list.")
        return []

    contested_list = result["contested"]
    if not isinstance(contested_list, list):
        return []
    return contested_list


def extract_contested_for_all_topics(
    conn: sqlite3.Connection,
    topics_to_update: list[str],
    force_all: bool = False,
) -> None:
    """Extract and store contested claims for topics that need updating."""
    if force_all:
        topics = list(TOPICS.keys())
        print(f"  Force-extracting contested claims for all {len(topics)} topics...")
    else:
        topics = topics_to_update
        print(f"  Extracting contested claims for {len(topics)} topics with new studies...")

    for topic_key in topics:
        topic_config = TOPICS.get(topic_key)
        if topic_config is None:
            print(f"  [WARN] Unknown topic key: {topic_key}")
            continue

        print(f"  Extracting contested claims for: {topic_config['name']}")

        # All tiers, capped — prioritise tier 1-2 first so counter-evidence
        # candidates are included, then fill remaining slots with others
        all_studies = get_studies_for_topic(conn, topic_key, min_quality_tier=5)
        all_studies = sorted(all_studies, key=lambda s: (s.get("quality_tier") or 5, -(s.get("pub_year") or 0)))
        all_studies = all_studies[:MAX_STUDIES_PER_EXTRACTION]

        if not all_studies:
            print(f"    No studies found for {topic_key}, skipping.")
            insert_contested_for_topic(conn, topic_key, [])
            continue

        print(f"    Sending top {len(all_studies)} studies to Groq...")

        try:
            contested = extract_contested_for_topic(topic_key, topic_config, all_studies)
        except Exception as exc:
            print(f"    [ERROR] Contested extraction failed for {topic_key}: {exc}")
            continue

        insert_contested_for_topic(conn, topic_key, contested)
        print(f"    Saved {len(contested)} contested claims for {topic_key}.")
        time.sleep(EXTRACTION_CALL_DELAY)
