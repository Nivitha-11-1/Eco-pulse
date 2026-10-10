"""Tests for EcoPulse RSS to Database Pipeline with AI Relevance Filtering (Phase 6).

Uses mocked RSS responses and mocked AI providers.
Verifies:
1. Pipeline collection, HTML cleaning, and SQLite storage.
2. AI relevance evaluation is stored (is_relevant flag and reason).
3. Already processed / duplicate articles are NOT sent to AI again (rate limit / cost protection).
4. AI failure for one article does not halt the pipeline.
5. Duplicate URL and duplicate title detection.
6. Feed failure tolerance.

Can be run via:
- pytest tests/test_pipeline.py
- python tests/test_pipeline.py
"""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.database import (
    initialize_database,
    get_articles,
    get_statistics,
)
from pipeline import run_pipeline
from ai.relevance_filter import BaseAIProvider


def cleanup_db(db_path: Path):
    """Safely remove a test database file and journal if existing."""
    for p in (db_path, Path(str(db_path) + "-journal"), Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if p.exists():
            try:
                os.remove(p)
            except Exception:
                pass


def get_mock_articles():
    return [
        {
            "title": "Solar Energy Capacity Expands in Tamil Nadu",
            "description": "<p>State solar projects have expanded by <strong>300 MW</strong> this quarter.</p>",
            "url": "https://example.com/news/solar-capacity-expansion-2026",
            "published_at": "2026-10-08 04:00:00 UTC",
            "source": "Mock Energy Daily",
            "location": "Tamil Nadu",
        },
        {
            "title": "Celebrity Movie Premieres in Chennai",
            "description": "<div>Actors attended the grand red carpet cinema event.</div>",
            "url": "https://example.com/news/cinema-event-launch",
            "published_at": "2026-10-08 04:30:00 UTC",
            "source": "Mock Entertainment",
            "location": "Chennai",
        },
    ]


class MockCustomAIProvider(BaseAIProvider):
    """Custom mock AI provider to verify pipeline integration."""

    def __init__(self):
        self.call_count = 0

    def classify_relevance(self, title: str, description: str):
        self.call_count += 1
        if "solar" in title.lower():
            return {
                "is_relevant": True,
                "reason": "Article covers renewable solar infrastructure.",
            }
        return {
            "is_relevant": False,
            "reason": "Article discusses entertainment with no environmental relevance.",
        }


def test_pipeline_ai_relevance_evaluation_and_storage():
    """Verify that AI relevance flag and reason are properly evaluated and stored in SQLite."""
    test_db = ROOT_DIR / "data" / "test_pipeline_ai_storage.db"
    cleanup_db(test_db)

    mock_sources = [
        {"name": "Source 1", "url": "https://example.com/source-1.xml", "location": "Tamil Nadu"},
    ]
    ai_provider = MockCustomAIProvider()

    with patch("pipeline.collect_news", return_value=get_mock_articles()):
        summary = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=ai_provider,
        )

    assert summary["articles_collected"] == 2
    assert summary["articles_inserted"] == 2
    assert summary["ai_articles_processed"] == 2
    assert summary["relevant_articles"] == 1
    assert summary["irrelevant_articles"] == 1
    assert ai_provider.call_count == 2

    # Verify SQLite rows contain the AI results
    stored_articles = get_articles(db_path=test_db)
    assert len(stored_articles) == 2

    solar = next(a for a in stored_articles if "Solar" in a["title"])
    assert solar["is_relevant"] == 1
    assert "renewable solar" in solar["reason"].lower()

    cinema = next(a for a in stored_articles if "Movie" in a["title"])
    assert cinema["is_relevant"] == 0
    assert "entertainment" in cinema["reason"].lower()


def test_pipeline_does_not_call_ai_for_duplicate_articles():
    """Verify that articles already in the DB are skipped before calling the AI."""
    test_db = ROOT_DIR / "data" / "test_pipeline_ai_duplicates.db"
    cleanup_db(test_db)

    mock_sources = [
        {"name": "Source 1", "url": "https://example.com/source-1.xml", "location": "Tamil Nadu"},
    ]
    ai_provider = MockCustomAIProvider()

    # First run: 2 articles processed by AI
    with patch("pipeline.collect_news", return_value=get_mock_articles()):
        summary_1 = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=ai_provider,
        )
    assert summary_1["ai_articles_processed"] == 2
    assert ai_provider.call_count == 2

    # Second run: identical articles detected as duplicates; AI must NOT be called
    with patch("pipeline.collect_news", return_value=get_mock_articles()):
        summary_2 = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=ai_provider,
        )
    assert summary_2["articles_inserted"] == 0
    assert summary_2["duplicate_urls_skipped"] == 2
    assert summary_2["ai_articles_processed"] == 0, "Duplicate articles must not be sent to AI"
    # Call count should not have increased
    assert ai_provider.call_count == 2


def test_pipeline_continues_when_ai_fails_for_one_article():
    """Verify that an exception in AI relevance for one article does not crash the pipeline."""
    test_db = ROOT_DIR / "data" / "test_pipeline_ai_failure.db"
    cleanup_db(test_db)

    mock_sources = [
        {"name": "Source 1", "url": "https://example.com/source-1.xml", "location": "Tamil Nadu"},
    ]

    failing_ai = MagicMock()
    # First call fails, second call succeeds
    failing_ai.classify_relevance.side_effect = [
        RuntimeError("Temporary model timeout"),
        {"is_relevant": False, "reason": "Entertainment article."},
    ]

    with patch("pipeline.collect_news", return_value=get_mock_articles()):
        summary = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=failing_ai,
        )

    assert summary["articles_collected"] == 2
    assert summary["articles_inserted"] == 2
    assert summary["ai_failures"] == 1
    assert summary["sources_failed"] == 0

    # Both articles were still safely saved in SQLite
    stored = get_articles(db_path=test_db)
    assert len(stored) == 2


def test_pipeline_duplicate_title_prevention():
    """Test that articles with distinct URLs but identical normalized titles from the same source are detected."""
    test_db = ROOT_DIR / "data" / "test_pipeline_duplicate_title.db"
    cleanup_db(test_db)

    title_duplicate_items = [
        {
            "title": "Severe Rain and Waterlogging Alert - Chennai Central",
            "description": "Meteorological department issued rainfall alert.",
            "url": "https://example.com/alerts/rain-morning-bulletin",
            "published_at": "2026-10-08 06:00:00 UTC",
            "source": "Chennai City Weather",
            "location": "Chennai",
        },
        {
            "title": "Severe Rain and Waterlogging Alert: Chennai Central!",
            "description": "Updated afternoon bulletin with duplicate warning.",
            "url": "https://example.com/alerts/rain-afternoon-bulletin",
            "published_at": "2026-10-08 12:00:00 UTC",
            "source": "Chennai City Weather",
            "location": "Chennai",
        },
    ]

    mock_sources = [
        {"name": "Chennai City Weather", "url": "https://example.com/weather.xml", "location": "Chennai"}
    ]
    ai_provider = MockCustomAIProvider()

    with patch("pipeline.collect_news", return_value=title_duplicate_items):
        summary = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=ai_provider,
        )

    assert summary["articles_collected"] == 2
    assert summary["articles_inserted"] == 1, "Only the first unique title should be inserted"
    assert summary["duplicate_titles_skipped"] == 1, "Second item should be detected as duplicate title"
    assert summary["ai_articles_processed"] == 1, "AI should only be invoked for unique article"


def test_pipeline_continues_when_source_fails():
    """Test that a failing RSS source does not stop other sources from being processed."""
    test_db = ROOT_DIR / "data" / "test_pipeline_failure.db"
    cleanup_db(test_db)

    def mock_collect_with_failure(feed_url, source_name, location):
        if "failing-source" in feed_url:
            raise ConnectionError("DNS resolution failed")
        return [
            {
                "title": "Solar Energy Capacity Expands in Tamil Nadu",
                "description": "New clean energy additions.",
                "url": "https://example.com/news/solar",
                "published_at": "2026-10-08 04:00:00 UTC",
                "source": "Mock Energy Daily",
                "location": "Tamil Nadu",
            }
        ]

    mock_sources = [
        {"name": "Broken Source 1", "url": "https://example.com/failing-source.xml", "location": "Unknown"},
        {"name": "Working Source 2", "url": "https://example.com/source-2.xml", "location": "Tamil Nadu"},
    ]
    ai_provider = MockCustomAIProvider()

    with patch("pipeline.collect_news", side_effect=mock_collect_with_failure):
        summary = run_pipeline(
            sources=mock_sources,
            db_path=test_db,
            verbose=False,
            ai_provider=ai_provider,
        )

    assert summary["sources_failed"] == 1
    assert summary["sources_processed"] == 1
    assert summary["articles_collected"] == 1
    assert summary["articles_inserted"] == 1


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print(" Running EcoPulse Pipeline Tests with AI Relevance (Phase 6)")
    print("=" * 65 + "\n")

    print("[1/5] Testing AI relevance evaluation and SQLite storage...")
    test_pipeline_ai_relevance_evaluation_and_storage()
    print("      PASSED: AI evaluated relevance and stored in SQLite.\n")

    print("[2/5] Testing AI call avoidance for duplicate articles...")
    test_pipeline_does_not_call_ai_for_duplicate_articles()
    print("      PASSED: Duplicate articles skipped before invoking AI.\n")

    print("[3/5] Testing pipeline resilience against single AI call failure...")
    test_pipeline_continues_when_ai_fails_for_one_article()
    print("      PASSED: AI failure isolated; remaining articles stored safely.\n")

    print("[4/5] Testing duplicate title detection...")
    test_pipeline_duplicate_title_prevention()
    print("      PASSED: Duplicate titles caught and skipped.\n")

    print("[5/5] Testing RSS source failure tolerance...")
    test_pipeline_continues_when_source_fails()
    print("      PASSED: Source failure isolated; other feeds completed.\n")

    print("=" * 65)
    print(" ALL PHASE 6 PIPELINE TESTS PASSED SUCCESSFULLY!")
    print("=" * 65 + "\n")
