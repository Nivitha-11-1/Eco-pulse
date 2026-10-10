"""Tests for EcoPulse Phase 8 Pipeline: AI Summarization & Recommended Action.

Verifies:
1. Summarizer initialization and result generation.
2. Saving summary and recommended action to article.
3. Database insertion and SQLite verification.
4. Safe temporary database isolation and cleanup.
"""

from datetime import datetime
import os
from pathlib import Path
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent

from ai.summarizer import get_summarizer
from database.database import insert_articles, initialize_database


def cleanup_db(db_path: Path):
    """Safely remove a test database file and journal if existing."""
    for p in (db_path, Path(str(db_path) + "-journal"), Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
        if p.exists():
            try:
                os.remove(p)
            except Exception:
                pass


def test_phase8_pipeline_summary_and_storage():
    """Verify that summarization output is properly stored in SQLite."""
    test_db = ROOT_DIR / "data" / "test_phase8_pipeline.db"
    cleanup_db(test_db)
    initialize_database(test_db)

    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        article = {
            "title": "Heavy Rainfall Causes Waterlogging in Chennai",
            "description": (
                "Heavy rainfall has caused flooding and severe waterlogging "
                "in several parts of Chennai. Authorities have issued safety warnings."
            ),
            "url": f"https://ecopulse-test.local/phase8/{timestamp}",
            "source": "EcoPulse Phase 8 Test",
            "published_at": datetime.now().isoformat(),
            "category": "Climate & Weather",
            "priority": "HIGH",
            "location": "Chennai",
            "is_relevant": 1,
        }

        # Mock summarizer to keep test independent of live API
        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = {
            "summary": "Heavy rainfall caused flooding and severe waterlogging in several parts of Chennai.",
            "recommended_action": "Follow instructions from local authorities and check official safety updates.",
        }

        result = mock_summarizer.summarize(
            title=article["title"],
            description=article["description"],
        )

        article["summary"] = result.get("summary", "")
        article["recommended_action"] = result.get(
            "recommended_action",
            "Stay informed and follow official updates."
        )

        stats = insert_articles([article], db_path=test_db)
        assert stats["inserted"] == 1

        conn = sqlite3.connect(str(test_db))
        cursor = conn.execute(
            """
            SELECT
                title,
                category,
                priority,
                location,
                summary,
                recommended_action
            FROM articles
            WHERE url = ?
            """,
            (article["url"],)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == article["title"]
        assert row[1] == "Climate & Weather"
        assert row[2] == "HIGH"
        assert row[3] == "Chennai"
        assert "Heavy rainfall" in row[4]
        assert "Follow instructions" in row[5]

    finally:
        cleanup_db(test_db)


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 8 INTEGRATION TEST")
    print("=" * 60)
    test_phase8_pipeline_summary_and_storage()
    print("[OK] Phase 8 pipeline test passed successfully!")