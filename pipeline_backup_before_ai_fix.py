
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

# Ensure project root is in Python's import path.
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


def run_pipeline(
    sources: Optional[List[Dict[str, Any]]] = None,
    db_path: Optional[Union[str, Path]] = None,
    verbose: bool = True,
    ai_provider=None,
) -> Dict[str, Any]:
    """Run the EcoPulse RSS-to-database pipeline."""

    if verbose:
        print("\n" + "=" * 65)
        print(" [EcoPulse] Pipeline Started")
        print(" (Quick Filter + AI Relevance + Classification + Summary)")
        print("=" * 65)

    # 1. Initialize database.
    target_db = initialize_database(db_path)

    if verbose:
        print(f"[*] Database verified at: {target_db}")

    # 2. Load existing article signatures for deduplication.
    existing_records = get_all_article_signatures(db_path=target_db)

    deduplicator = ArticleDeduplicator()

    for record in existing_records:
        deduplicator.register_article(record)

    if verbose:
        print(
            f"[*] Loaded {len(existing_records)} existing article "
            "signature(s) for deduplication."
        )

    # 3. Load active RSS sources.
    if sources is None:
        sources = get_active_sources()

    total_sources = len(sources)

    if verbose:
        print(f"[*] Loaded {total_sources} active RSS source(s).\n")

    # 4. Initialize AI components.
    active_ai = ai_provider if ai_provider is not None else get_ai_provider()
    classifier = get_classifier()
    summarizer = get_summarizer()

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
            print(
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
                print(f"    [!] Source failed: {exc}\n")

            continue

        article_count = len(raw_articles)
        stats["articles_collected"] += article_count

        if not raw_articles:
            stats["sources_processed"] += 1

            if verbose:
                print("    [-] No articles collected.\n")

            continue

        articles_to_insert: List[Dict[str, Any]] = []
        source_url_duplicates = 0
        source_title_duplicates = 0

        # Process individual articles.
        for raw_item in raw_articles:
            # Clean HTML and normalize article fields.
            try:
                article = clean_article(raw_item)
            except Exception as exc:
                logger.warning("Skipping article that could not be cleaned: %s", exc)
                continue

            article["collected_at"] = collected_timestamp

            # Check for duplicates.
            is_duplicate, duplicate_reason = (
                deduplicator.check_duplicate(article)
            )

            if is_duplicate:
                if duplicate_reason in ("exact_url", "normalized_url"):
                    source_url_duplicates += 1
                elif duplicate_reason == "normalized_title":
                    source_title_duplicates += 1
                continue

            # Register article immediately to catch duplicates within this run.
            deduplicator.register_article(article)

            title = article.get("title", "")
            description = article.get("description", "")
            title_preview = title[:60]

            # -------------------------------------------------
            # PHASE A: QUICK KEYWORD FILTER (NO API CALL)
            # -------------------------------------------------
            if not quick_relevance_check(title, description):
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
                    print(
                        f"    [Quick Filter] Skipped AI: "
                        f"'{title_preview}'"
                    )

                continue

            stats["quick_filter_passed"] += 1

            # -------------------------------------------------
            # PHASE B: AI RELEVANCE CHECK
            # -------------------------------------------------
            stats["ai_articles_processed"] += 1

            if verbose:
                print(
                    f"    [AI] Checking relevance: '{title_preview}'"
                )

            try:
                relevance_result = check_relevance(
                    title=title,
                    description=description,
                    provider=active_ai,
                )

                is_relevant = bool(
                    relevance_result.get("is_relevant", False)
                )
                relevance_reason = str(
                    relevance_result.get("reason", "")
                )

                article["is_relevant"] = 1 if is_relevant else 0
                article["reason"] = relevance_reason

                if is_relevant:
                    stats["relevant_articles"] += 1
                else:
                    stats["irrelevant_articles"] += 1

                reason_lower = relevance_reason.lower()
                if any(
                    marker in reason_lower
                    for marker in (
                        "error",
                        "failure",
                        "not configured",
                        "quota exceeded",
                        "timed out",
                        "timeout",
                    )
                ):
                    stats["ai_failures"] += 1

                if verbose:
                    print(
                        f"    [AI] Relevant: "
                        f"{'YES' if is_relevant else 'NO'}"
                    )
                    print(f"    [AI] Reason: {relevance_reason}")

                # -------------------------------------------------
                # PHASE C: CLASSIFICATION
                # -------------------------------------------------
                if is_relevant:
                    if verbose:
                        print("    [AI] Classifying article...")

                    try:
                        classification = classifier.classify(
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
                            print(
                                f"    [AI] Category: {article['category']}"
                            )
                            print(
                                f"    [AI] Priority: {article['priority']}"
                            )
                            print(
                                f"    [AI] Location: {article['location']}"
                            )

                    except Exception as exc:
                        stats["classification_failures"] += 1
                        logger.exception(
                            "Classification failed for '%s'", title_preview
                        )

                        article["category"] = "Other"
                        article["priority"] = "LOW"
                        article["location"] = source_location

                        if verbose:
                            print(
                                f"    [AI] Classification failed: "
                                f"{type(exc).__name__}"
                            )

                    # -------------------------------------------------
                    # PHASE D: AI SUMMARY AND RECOMMENDED ACTION
                    # -------------------------------------------------
                    if verbose:
                        print("    [AI] Generating summary...")

                    try:
                        summary_result = summarizer.summarize(
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
                                print(
                                    f"    [AI] Summary warning: {summary_reason}"
                                )
                        else:
                            stats["summarized_articles"] += 1

                        if verbose:
                            print(
                                f"    [AI] Summary: {article['summary']}"
                            )
                            print(
                                f"    [AI] Action: "
                                f"{article['recommended_action']}"
                            )

                    except Exception as exc:
                        stats["summary_failures"] += 1
                        logger.exception(
                            "Summarization failed for '%s'", title_preview
                        )

                        article["summary"] = ""
                        article["recommended_action"] = (
                            "Stay informed and follow official updates."
                        )

                        if verbose:
                            print(
                                f"    [AI] Summarization failed: "
                                f"{type(exc).__name__}"
                            )

                else:
                    # Defaults for AI-rejected articles.
                    article["category"] = "Other"
                    article["priority"] = "LOW"
                    article["location"] = source_location
                    article["summary"] = ""
                    article["recommended_action"] = (
                        "Stay informed and follow official updates."
                    )

            except Exception as exc:
                stats["ai_failures"] += 1
                stats["irrelevant_articles"] += 1

                logger.exception(
                    "Relevance check failed for '%s'", title_preview
                )

                article["is_relevant"] = 0
                article["reason"] = (
                    f"AI relevance check failed: {type(exc).__name__}"
                )
                article["category"] = "Other"
                article["priority"] = "LOW"
                article["location"] = source_location
                article["summary"] = ""
                article["recommended_action"] = (
                    "Stay informed and follow official updates."
                )

                if verbose:
                    print(
                        f"    [AI] Relevance check failed: "
                        f"{type(exc).__name__}"
                    )

            articles_to_insert.append(article)

        # -------------------------------------------------
        # INSERT PROCESSED ARTICLES INTO SQLITE
        # -------------------------------------------------
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
                    print("    [!] Database insertion failed.")

        stats["articles_inserted"] += inserted_count
        stats["duplicate_urls_skipped"] += source_url_duplicates
        stats["duplicate_titles_skipped"] += source_title_duplicates
        stats["sources_processed"] += 1

        if verbose:
            print(f"    [+] Articles collected:              {article_count}")
            print(f"    [+] New articles inserted:           {inserted_count}")
            print(
                f"    [*] Duplicate URLs skipped:          "
                f"{source_url_duplicates}"
            )
            print(
                f"    [*] Duplicate titles/content skipped: "
                f"{source_title_duplicates}\n"
            )

    # -------------------------------------------------
    # FINAL PIPELINE SUMMARY
    # -------------------------------------------------
    if verbose:
        print("=" * 65)
        print(" [EcoPulse] Pipeline Completed")
        print("=" * 65)

        print(
            f"  Total Articles Collected:           "
            f"{stats['articles_collected']}"
        )
        print(
            f"  New Articles Inserted:              "
            f"{stats['articles_inserted']}"
        )
        print(
            f"  Duplicate URLs Skipped:             "
            f"{stats['duplicate_urls_skipped']}"
        )
        print(
            f"  Duplicate Titles/Content Skipped:   "
            f"{stats['duplicate_titles_skipped']}"
        )
        print(
            f"  Quick Filter Skipped (no AI):       "
            f"{stats['quick_filter_skipped']}"
        )
        print(
            f"  Quick Filter Passed:                "
            f"{stats['quick_filter_passed']}"
        )
        print(
            f"  AI Articles Processed:              "
            f"{stats['ai_articles_processed']}"
        )
        print(
            f"  Relevant Articles:                  "
            f"{stats['relevant_articles']}"
        )
        print(
            f"  Irrelevant Articles:                "
            f"{stats['irrelevant_articles']}"
        )
        print(
            f"  AI Failures:                        "
            f"{stats['ai_failures']}"
        )
        print(
            f"  Classified Articles:                "
            f"{stats['classified_articles']}"
        )
        print(
            f"  Classification Failures:            "
            f"{stats['classification_failures']}"
        )
        print(
            f"  Summarized Articles:                "
            f"{stats['summarized_articles']}"
        )
        print(
            f"  Summary Failures:                   "
            f"{stats['summary_failures']}"
        )
        print(
            f"  Sources Processed:                  "
            f"{stats['sources_processed']}/{total_sources}"
        )
        print(
            f"  Sources Failed:                     "
            f"{stats['sources_failed']}"
        )

        database_stats = get_statistics(db_path=target_db)

        print(
            f"  Total Articles in Database Now:     "
            f"{database_stats.get('total_articles', 0)}"
        )
        print(
            f"  Total Relevant Articles in DB:      "
            f"{database_stats.get('relevant_articles', 0)}"
        )
        print("=" * 65 + "\n")

    return stats


if __name__ == "__main__":
    run_pipeline()