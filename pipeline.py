
"""
EcoPulse News Ingestion Pipeline

Flow:
RSS -> Cleaning -> Deduplication -> Quick Keyword Filter
    -> AI Relevance -> AI Classification -> AI Summary
    -> SQLite Database
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Union

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from collectors.source_config import get_active_sources
from collectors.rss_collector import collect_news

from database.database import (
    initialize_database,
    insert_articles,
    get_statistics,
    get_all_article_signatures,
)

from processors.cleaner import clean_article
from processors.deduplicator import ArticleDeduplicator

from ai.relevance_filter import (
    check_relevance,
    get_ai_provider,
    quick_relevance_check,
)

from ai.classifier import get_classifier
from ai.summarizer import get_summarizer


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("EcoPulse.Pipeline")

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_print(*args, **kwargs):
    """Safely print text handling Windows charmap / CP1252 encoding gracefully."""
    end = kwargs.get("end", "\n")
    sep = kwargs.get("sep", " ")
    text = sep.join(str(arg) for arg in args) + end
    try:
        sys.stdout.write(text)
        sys.stdout.flush()
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        sanitized = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        sys.stdout.write(sanitized)
        sys.stdout.flush()


AI_ERROR_MARKERS = (
    "error",
    "failure",
    "not configured",
    "quota exceeded",
    "timed out",
    "timeout",
    "rate limit",
    "429",
    "api key",
    "exception",
    "unavailable",
)


def ai_check_failed(reason: str) -> bool:
    """Identify common AI/API failure messages."""
    reason_lower = reason.lower()
    return any(marker in reason_lower for marker in AI_ERROR_MARKERS)


from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def run_pipeline(
    sources: Optional[List[Dict[str, Any]]] = None,
    db_path: Optional[Union[str, Path]] = None,
    verbose: bool = True,
    ai_provider=None,
    classifier=None,
    summarizer=None,
    enable_quick_filter: Optional[bool] = None,
) -> Dict[str, Any]:
    """Run the EcoPulse RSS-to-database pipeline."""
    start_utc = datetime.now(timezone.utc)
    start_ist = datetime.now(IST)

    if verbose:
        safe_print("\n" + "=" * 65)
        safe_print(" [EcoPulse] Pipeline Started")
        safe_print(f" Start Time (UTC): {start_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        safe_print(f" Start Time (IST): {start_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        safe_print(" (Quick Filter + AI Relevance + Classification + Summary)")
        safe_print("=" * 65)

    # 1. Initialize the database.
    target_db = initialize_database(db_path)

    if verbose:
        safe_print(f"[*] Database verified at: {target_db}")

    # 2. Load existing signatures for deduplication.
    existing_records = get_all_article_signatures(db_path=target_db)
    deduplicator = ArticleDeduplicator()

    for record in existing_records:
        deduplicator.register_article(record)

    if verbose:
        safe_print(
            f"[*] Loaded {len(existing_records)} existing article "
            "signature(s) for deduplication."
        )

    # 3. Load active RSS sources.
    if sources is None:
        sources = get_active_sources()

    total_sources = len(sources)

    if verbose:
        safe_print(f"[*] Loaded {total_sources} active RSS source(s).\n")

    # 4. Initialize AI components.
    active_ai = (
        ai_provider if ai_provider is not None else get_ai_provider()
    )
    active_classifier = (
        classifier if classifier is not None else get_classifier()
    )
    active_summarizer = (
        summarizer if summarizer is not None else get_summarizer()
    )
    if enable_quick_filter is None:
        enable_quick_filter = (ai_provider is None)

    # 5. Pipeline statistics.
    stats = {
        "sources_processed": 0,
        "sources_failed": 0,
        "articles_collected": 0,
        "articles_inserted": 0,
        "duplicate_urls_skipped": 0,
        "duplicate_titles_skipped": 0,
        "quick_filter_skipped": 0,
        "quick_filter_passed": 0,
        "ai_articles_processed": 0,
        "relevant_articles": 0,
        "irrelevant_articles": 0,
        "ai_failures": 0,
        "classified_articles": 0,
        "classification_failures": 0,
        "summarized_articles": 0,
        "summary_failures": 0,
    }

    collected_timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    # 6. Process each RSS source.
    for source_index, source in enumerate(sources, start=1):
        source_name = source.get("name", f"Source #{source_index}")
        source_url = source.get("url", "")
        source_location = source.get("location", "General")

        if verbose:
            safe_print(
                f"--> [{source_index}/{total_sources}] Fetching: "
                f"'{source_name}' ({source_url})"
            )

        # Collect RSS articles.
        try:
            raw_articles = collect_news(
                feed_url=source_url,
                source_name=source_name,
                location=source_location,
            )
            raw_articles = raw_articles or []

        except Exception as exc:
            stats["sources_failed"] += 1
            logger.exception(
                "Failed to collect from source '%s'", source_name
            )

            if verbose:
                safe_print(f"    [!] Source failed: {exc}\n")

            continue

        article_count = len(raw_articles)
        stats["articles_collected"] += article_count

        if not raw_articles:
            stats["sources_processed"] += 1

            if verbose:
                safe_print("    [-] No articles collected.\n")

            continue

        articles_to_insert: List[Dict[str, Any]] = []
        source_url_duplicates = 0
        source_title_duplicates = 0

        # Process individual articles.
        for raw_item in raw_articles:
            try:
                article = clean_article(raw_item)
            except Exception as exc:
                logger.warning(
                    "Skipping article that could not be cleaned: %s",
                    exc,
                )
                continue

            article["collected_at"] = collected_timestamp

            # Deduplicate articles.
            is_duplicate, duplicate_reason = (
                deduplicator.check_duplicate(article)
            )

            if is_duplicate:
                if duplicate_reason in ("exact_url", "normalized_url"):
                    source_url_duplicates += 1
                elif duplicate_reason == "normalized_title":
                    source_title_duplicates += 1
                continue

            # Register it to catch duplicates within this run.
            deduplicator.register_article(article)

            title = article.get("title", "")
            description = article.get("description", "")
            title_preview = title[:60]

            # PHASE A: Quick keyword filter.
            if enable_quick_filter and not quick_relevance_check(title, description):
                stats["quick_filter_skipped"] += 1
                stats["irrelevant_articles"] += 1

                article["is_relevant"] = 0
                article["reason"] = (
                    "Skipped by quick keyword filter: no matching "
                    "environmental, weather, water, sustainability, "
                    "or civic keywords."
                )
                article["category"] = "Other"
                article["priority"] = "LOW"
                article["location"] = source_location
                article["summary"] = ""
                article["recommended_action"] = (
                    "Stay informed and follow official updates."
                )

                articles_to_insert.append(article)

                if verbose:
                    safe_print(
                        f"    [Quick Filter] Skipped AI: "
                        f"'{title_preview}'"
                    )

                continue

            stats["quick_filter_passed"] += 1
            stats["ai_articles_processed"] += 1

            if verbose:
                safe_print(f"    [AI] Checking relevance: '{title_preview}'")

            # PHASE B: AI relevance check with fallback.
            relevance_reason = ""
            ai_failed = False

            try:
                relevance_result = check_relevance(
                    title=title,
                    description=description,
                    provider=active_ai,
                )

                relevance_reason = str(
                    relevance_result.get("reason", "")
                )

                ai_failed = ai_check_failed(relevance_reason)

                if ai_failed:
                    stats["ai_failures"] += 1
                    is_relevant = quick_relevance_check(
                        title, description
                    )
                    if is_relevant:
                        relevance_reason = (
                            "AI unavailable; retained by keyword "
                            "fallback. Original reason: "
                            + relevance_reason
                        )
                else:
                    is_relevant = bool(
                        relevance_result.get("is_relevant", False)
                    )

            except Exception as exc:
                ai_failed = True
                stats["ai_failures"] += 1

                logger.exception(
                    "Relevance check failed for '%s'", title_preview
                )

                # Do not discard a keyword-matched article just because
                # the AI service raised an exception.
                is_relevant = quick_relevance_check(
                    title, description
                )
                relevance_reason = (
                    "AI relevance check failed: "
                    f"{type(exc).__name__}; "
                    "keyword fallback used."
                )

            article["is_relevant"] = 1 if is_relevant else 0
            article["reason"] = relevance_reason

            if is_relevant:
                stats["relevant_articles"] += 1
            else:
                stats["irrelevant_articles"] += 1

            if verbose:
                safe_print(
                    f"    [AI] Relevant: "
                    f"{'YES' if is_relevant else 'NO'}"
                )
                safe_print(f"    [AI] Reason: {relevance_reason}")

            # PHASE C: Classification.
            if is_relevant:
                if verbose:
                    safe_print("    [AI] Classifying article...")

                try:
                    classification = active_classifier.classify(
                        title=title,
                        description=description,
                    )

                    article["category"] = classification.get(
                        "category", "Other"
                    )
                    article["priority"] = classification.get(
                        "priority", "LOW"
                    )
                    article["location"] = classification.get(
                        "location", source_location
                    )

                    stats["classified_articles"] += 1

                    if verbose:
                        safe_print(
                            f"    [AI] Category: "
                            f"{article['category']}"
                        )
                        safe_print(
                            f"    [AI] Priority: "
                            f"{article['priority']}"
                        )
                        safe_print(
                            f"    [AI] Location: "
                            f"{article['location']}"
                        )

                except Exception as exc:
                    stats["classification_failures"] += 1
                    logger.exception(
                        "Classification failed for '%s'",
                        title_preview,
                    )

                    article["category"] = "Other"
                    article["priority"] = "LOW"
                    article["location"] = source_location

                    if verbose:
                        safe_print(
                            "    [AI] Classification failed: "
                            f"{type(exc).__name__}"
                        )

                # PHASE D: Summary and recommended action.
                if verbose:
                    safe_print("    [AI] Generating summary...")

                try:
                    summary_result = active_summarizer.summarize(
                        title=title,
                        description=description,
                    )

                    article["summary"] = summary_result.get(
                        "summary", ""
                    )
                    article["recommended_action"] = (
                        summary_result.get("recommended_action")
                        or "Stay informed and follow official updates."
                    )

                    summary_reason = summary_result.get("reason")

                    if summary_reason:
                        stats["summary_failures"] += 1

                        if verbose:
                            safe_print(
                                f"    [AI] Summary warning: "
                                f"{summary_reason}"
                            )
                    else:
                        stats["summarized_articles"] += 1

                    if verbose:
                        safe_print(
                            f"    [AI] Summary: "
                            f"{article['summary']}"
                        )
                        safe_print(
                            f"    [AI] Action: "
                            f"{article['recommended_action']}"
                        )

                except Exception as exc:
                    stats["summary_failures"] += 1
                    logger.exception(
                        "Summarization failed for '%s'",
                        title_preview,
                    )

                    article["summary"] = ""
                    article["recommended_action"] = (
                        "Stay informed and follow official updates."
                    )

                    if verbose:
                        safe_print(
                            "    [AI] Summarization failed: "
                            f"{type(exc).__name__}"
                        )

            else:
                article["category"] = "Other"
                article["priority"] = "LOW"
                article["location"] = source_location
                article["summary"] = ""
                article["recommended_action"] = (
                    "Stay informed and follow official updates."
                )

            articles_to_insert.append(article)

        # Insert processed articles into SQLite.
        inserted_count = 0

        if articles_to_insert:
            try:
                db_result = insert_articles(
                    articles_to_insert,
                    db_path=target_db,
                )

                inserted_count = db_result.get("inserted", 0)
                source_url_duplicates += db_result.get("duplicates", 0)

            except Exception:
                logger.exception(
                    "Database insertion failed for '%s'", source_name
                )

                if verbose:
                    safe_print("    [!] Database insertion failed.")

        stats["articles_inserted"] += inserted_count
        stats["duplicate_urls_skipped"] += source_url_duplicates
        stats["duplicate_titles_skipped"] += source_title_duplicates
        stats["sources_processed"] += 1

        if verbose:
            safe_print(f"    [+] Articles collected:              {article_count}")
            safe_print(f"    [+] New articles inserted:           {inserted_count}")
            safe_print(
                f"    [*] Duplicate URLs skipped:          "
                f"{source_url_duplicates}"
            )
            safe_print(
                f"    [*] Duplicate titles/content skipped: "
                f"{source_title_duplicates}\n"
            )

    # Final pipeline summary.
    if verbose:
        safe_print("=" * 65)
        safe_print(" [EcoPulse] Pipeline Completed")
        safe_print("=" * 65)

        safe_print(
            f"  Total Articles Collected:           "
            f"{stats['articles_collected']}"
        )
        safe_print(
            f"  New Articles Inserted:              "
            f"{stats['articles_inserted']}"
        )
        safe_print(
            f"  Duplicate URLs Skipped:             "
            f"{stats['duplicate_urls_skipped']}"
        )
        safe_print(
            f"  Duplicate Titles/Content Skipped:   "
            f"{stats['duplicate_titles_skipped']}"
        )
        safe_print(
            f"  Quick Filter Skipped (no AI):       "
            f"{stats['quick_filter_skipped']}"
        )
        safe_print(
            f"  Quick Filter Passed:                "
            f"{stats['quick_filter_passed']}"
        )
        safe_print(
            f"  AI Articles Processed:              "
            f"{stats['ai_articles_processed']}"
        )
        safe_print(
            f"  Relevant Articles:                  "
            f"{stats['relevant_articles']}"
        )
        safe_print(
            f"  Irrelevant Articles:                "
            f"{stats['irrelevant_articles']}"
        )
        safe_print(f"  AI Failures:                        {stats['ai_failures']}")
        safe_print(
            f"  Classified Articles:                "
            f"{stats['classified_articles']}"
        )
        safe_print(
            f"  Classification Failures:            "
            f"{stats['classification_failures']}"
        )
        safe_print(
            f"  Summarized Articles:                "
            f"{stats['summarized_articles']}"
        )
        safe_print(
            f"  Summary Failures:                   "
            f"{stats['summary_failures']}"
        )
        safe_print(
            f"  Sources Processed:                  "
            f"{stats['sources_processed']}/{total_sources}"
        )
        safe_print(
            f"  Sources Failed:                     {stats['sources_failed']}"
        )

        database_stats = get_statistics(db_path=target_db)
        from database.database import get_regional_statistics
        regional_breakdown = get_regional_statistics(db_path=target_db)

        end_utc = datetime.now(timezone.utc)
        end_ist = datetime.now(IST)
        duration_sec = (end_utc - start_utc).total_seconds()

        safe_print(
            f"  Total Articles in Database Now:     "
            f"{database_stats.get('total_articles', 0)}"
        )
        safe_print(
            f"  Total Relevant Alerts in DB:        "
            f"{database_stats.get('relevant_articles', 0)}"
        )
        safe_print(
            f"    - High Priority Alerts:           "
            f"{database_stats.get('high_priority_count', 0)}"
        )
        safe_print(
            f"    - Medium Priority Alerts:         "
            f"{database_stats.get('medium_priority_count', 0)}"
        )
        safe_print(
            f"    - Low Priority Alerts:            "
            f"{database_stats.get('low_priority_count', 0)}"
        )
        safe_print("  Regional Focus Breakdown:")
        safe_print(f"    - Chennai Local Alerts:          {regional_breakdown.get('chennai', 0)}")
        safe_print(f"    - Tamil Nadu State Alerts:       {regional_breakdown.get('tamil_nadu', 0)}")
        safe_print(f"    - India National Alerts:         {regional_breakdown.get('india', 0)}")
        safe_print(f"    - Other Global Alerts:           {regional_breakdown.get('global', 0)}")
        safe_print(f"  Completion Time (UTC):              {end_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        safe_print(f"  Completion Time (IST):              {end_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        safe_print(f"  Execution Duration:                 {duration_sec:.2f} seconds")
        safe_print("=" * 65 + "\n")

    # Automatically sync seed file if using SQLite and new articles were added to primary database
    if stats["articles_inserted"] > 0 and db_path is None:
        try:
            import json, sqlite3
            seed_file = BASE_DIR / "data" / "seed_articles.json"
            if Path(target_db).exists():
                conn = sqlite3.connect(str(target_db))
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM articles ORDER BY id ASC")
                all_rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                with open(seed_file, "w", encoding="utf-8") as sf:
                    json.dump(all_rows, sf, indent=2, ensure_ascii=False)
                if verbose:
                    safe_print(f"[*] Synchronized {len(all_rows)} articles with seed_articles.json.")
        except Exception as sync_err:
            logger.warning("Could not sync seed_articles.json: %s", sync_err)

    return stats


if __name__ == "__main__":
    try:
        pipeline_stats = run_pipeline()
        if pipeline_stats.get("sources_failed", 0) > 0 and pipeline_stats.get("sources_processed", 0) == 0:
            logger.error("All sources failed to collect articles.")
            sys.exit(1)
        sys.exit(0)
    except Exception as exc:
        logger.exception("Pipeline execution failed fatally: %s", exc)
        sys.exit(1)