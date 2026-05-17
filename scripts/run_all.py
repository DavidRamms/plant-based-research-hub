"""
Entry point for the Plant-Based Research Hub update pipeline.
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Add scripts dir to path so sibling modules can be imported directly
sys.path.insert(0, str(Path(__file__).parent))

from config import TOPICS
from database import get_connection, init_db, get_study_count
from fetch_studies import fetch_all_topics
from generate_summaries import update_summaries_for_topics
from build_site import build_static_site

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "studies.db"
DOCS_PATH = PROJECT_ROOT / "docs"


def main() -> None:
    parser = argparse.ArgumentParser(description="Plant-Based Research Hub update pipeline")
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help=f"First run: fetch last {5} years of studies instead of just the past year",
    )
    parser.add_argument(
        "--force-resynthesis",
        action="store_true",
        help="Regenerate all AI summaries regardless of whether new studies were found",
    )
    args = parser.parse_args()

    # Also check environment variable (set by GitHub Actions workflow_dispatch)
    force_resynthesis = args.force_resynthesis or (
        os.getenv("FORCE_RESYNTHESIS", "false").lower() == "true"
    )

    # Check if today is Sunday — always force full resynthesis on Sundays
    if datetime.now().weekday() == 6:
        print("It's Sunday — forcing full resynthesis of all summaries.")
        force_resynthesis = True

    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = get_connection(str(DB_PATH))
    init_db(conn)

    # Detect bootstrap condition: treat as bootstrap if DB is empty
    total_existing = sum(get_study_count(conn, t) for t in TOPICS)
    is_bootstrap = args.bootstrap or total_existing == 0

    if is_bootstrap:
        print(f"Bootstrap mode: fetching last 5 years of studies (DB currently has {total_existing} studies)...")

    # ------------------------------------------------------------------
    # Step 1: Fetch new studies from PubMed
    # ------------------------------------------------------------------
    print("\nStep 1: Fetching new studies from PubMed...")
    new_counts = fetch_all_topics(conn, is_bootstrap=is_bootstrap)

    topics_with_new = [t for t, count in new_counts.items() if count > 0]
    total_new = sum(new_counts.values())
    print(f"\n  {total_new} new studies found across {len(topics_with_new)} topics.")

    # ------------------------------------------------------------------
    # Step 2: Generate / update summaries
    # ------------------------------------------------------------------
    if topics_with_new or force_resynthesis:
        print("\nStep 2: Generating/updating summaries...")
        if not os.getenv("GROQ_API_KEY"):
            print("  WARNING: GROQ_API_KEY environment variable is not set. Skipping summary generation.")
        else:
            update_summaries_for_topics(conn, topics_with_new, force_all=force_resynthesis)
    else:
        print("\nStep 2: No new studies found and force_resynthesis is off — skipping summary generation.")

    # ------------------------------------------------------------------
    # Step 2b: Extract quotable statistics
    # ------------------------------------------------------------------
    # Bootstrap stats: if stats table is empty, treat as force_all so the
    # first deployment populates stats without needing a manual trigger.
    from database import get_all_stats
    stats_bootstrap = len(get_all_stats(conn)) == 0
    force_stats = force_resynthesis or stats_bootstrap

    print("\nStep 2b: Extracting quotable statistics...")
    if not os.getenv("GROQ_API_KEY"):
        print("  WARNING: GROQ_API_KEY not set, skipping stats extraction")
    else:
        from generate_summaries import extract_stats_for_all_topics
        extract_stats_for_all_topics(conn, topics_with_new, force_all=force_stats)

    # ------------------------------------------------------------------
    # Step 3: Build static site
    # ------------------------------------------------------------------
    print("\nStep 3: Building static site...")
    build_static_site(conn, DOCS_PATH)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
