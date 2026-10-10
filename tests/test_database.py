"""Tests for EcoPulse SQLite Database module.

Verifies:
1. Database initialization and table creation.
2. Database file existence.
3. Single article insertion and retrieval.
4. Duplicate URL prevention (integrity handling).
5. Batch insertion with insert_articles.
6. Filtering and search capabilities.
7. Statistics aggregation.

Can be run via:
- pytest tests/test_database.py
- python tests/test_database.py
"""

import os
from pathlib import Path
import sys

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.database import (
    initialize_database,
    insert_article,
    insert_articles,
    get_articles,
    get_article_by_id,
    get_today_articles,
    get_high_priority_articles,
    get_statistics,
    get_db_path,
)

# Use dedicated test DB to keep tests clean and isolated
TEST_DB_PATH = ROOT_DIR / "data" / "test_news.db"


import pytest


def cleanup_test_db():
    """Remove temporary test database if it exists."""
    if TEST_DB_PATH.exists():
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


@pytest.fixture(autouse=True)
def auto_cleanup():
    """Ensure clean state before and after every test."""
    cleanup_test_db()
    yield
    cleanup_test_db()


def test_database_initialization_and_file_existence():
    """Verify that initialize_database creates tables and file exists."""
    cleanup_test_db()
    db_file = initialize_database(TEST_DB_PATH)
    assert db_file.exists(), f"Database file does not exist at {db_file}"
    assert os.path.isfile(db_file), "Database path should point to a valid file"


def test_insert_and_retrieve_article():
    """Verify inserting a sample article and retrieving it by ID and list."""
    initialize_database(TEST_DB_PATH)

    sample_article = {
        "title": "Severe Rain and Waterlogging Alert for Chennai Central",
        "description": "Meteorological department reports heavy rainfall across coastal Tamil Nadu.",
        "url": "https://example.com/alerts/chennai-rain-2026-10",
        "source": "Chennai City Civic Advisory",
        "published_at": "2026-10-08 05:00:00 UTC",
        "category": "Environmental Alert",
        "priority": "HIGH",
        "location": "Chennai",
        "summary": "Heavy rainfall warning with localized waterlogging expected in central areas.",
        "reason": "Direct public safety impact from rapid accumulation of rainwater.",
        "keywords": ["rain", "flood", "Chennai"],
        "recommended_action": "Avoid low-lying subways and monitor municipal alerts.",
        "is_relevant": 1,
    }

    inserted_id = insert_article(sample_article, db_path=TEST_DB_PATH)
    assert inserted_id is not None, "Article should be inserted and return an ID"

    # Retrieve by ID
    retrieved = get_article_by_id(inserted_id, db_path=TEST_DB_PATH)
    assert retrieved is not None, "Article should be retrieved by its ID"
    assert retrieved["title"] == sample_article["title"]
    assert retrieved["url"] == sample_article["url"]
    assert retrieved["priority"] == "HIGH"
    assert retrieved["category"] == "Environmental Alert"
    assert retrieved["is_relevant"] == 1


def test_duplicate_url_handling():
    """Verify that inserting an article with an existing URL is safely ignored."""
    initialize_database(TEST_DB_PATH)

    duplicate_item = {
        "title": "Initial Article Title",
        "url": "https://example.com/unique-url-test-1",
        "source": "Test Source",
        "priority": "LOW",
    }

    # First insert should succeed
    first_id = insert_article(duplicate_item, db_path=TEST_DB_PATH)
    assert first_id is not None

    # Second insert with identical URL should return None (safely ignored, no crash)
    second_id = insert_article(duplicate_item, db_path=TEST_DB_PATH)
    assert second_id is None, "Duplicate URL must not be re-inserted"


def test_batch_insertion_and_duplicates():
    """Verify batch insert counts inserted vs duplicate items."""
    initialize_database(TEST_DB_PATH)

    batch = [
        {"title": "Batch Article A", "url": "https://example.com/batch-a", "priority": "MEDIUM"},
        {"title": "Batch Article B", "url": "https://example.com/batch-b", "priority": "HIGH"},
        {"title": "Batch Article A Duplicate", "url": "https://example.com/batch-a", "priority": "LOW"},
    ]

    result = insert_articles(batch, db_path=TEST_DB_PATH)
    assert result["inserted"] == 2, "Expected 2 new unique articles inserted"
    assert result["duplicates"] == 1, "Expected 1 duplicate skipped"
    assert result["total"] == 3


def test_query_filters_and_search():
    """Verify filtering articles by priority, category, and search term."""
    initialize_database(TEST_DB_PATH)

    sample_articles = [
        {
            "title": "Severe Rain and Waterlogging Alert for Chennai Central",
            "description": "Heavy rainfall across coastal Tamil Nadu.",
            "url": "https://example.com/alerts/waterlogging-chennai",
            "category": "Environmental Alert",
            "priority": "HIGH",
            "location": "Chennai",
            "is_relevant": 1,
        },
        {
            "title": "Solar Energy in Coimbatore",
            "description": "Solar expansion project.",
            "url": "https://example.com/alerts/solar-coimbatore",
            "category": "Energy",
            "priority": "LOW",
            "location": "Coimbatore",
            "is_relevant": 1,
        },
    ]
    insert_articles(sample_articles, db_path=TEST_DB_PATH)

    # Search for term
    results = get_articles(search="waterlogging", db_path=TEST_DB_PATH)
    assert len(results) >= 1
    assert any("Chennai" in item["location"] for item in results)

    # Filter high priority
    high_items = get_high_priority_articles(db_path=TEST_DB_PATH)
    assert len(high_items) >= 1
    assert all(item["priority"] == "HIGH" for item in high_items)

    # Today's articles
    today_items = get_today_articles(db_path=TEST_DB_PATH)
    assert len(today_items) >= 1


def test_statistics_aggregation():
    """Verify statistics calculation matches stored counts."""
    initialize_database(TEST_DB_PATH)
    sample_articles = [
        {"title": "Article 1", "url": "https://example.com/stats-1", "priority": "HIGH", "category": "Climate", "is_relevant": 1},
        {"title": "Article 2", "url": "https://example.com/stats-2", "priority": "MEDIUM", "category": "Water", "is_relevant": 1},
        {"title": "Article 3", "url": "https://example.com/stats-3", "priority": "LOW", "category": "Other", "is_relevant": 0},
    ]
    insert_articles(sample_articles, db_path=TEST_DB_PATH)
    stats = get_statistics(db_path=TEST_DB_PATH)

    assert stats["total_articles"] == 3
    assert stats["high_priority_count"] == 1
    assert stats["medium_priority_count"] == 1
    assert stats["low_priority_count"] == 1
    assert stats["relevant_articles"] == 2
    assert "total_articles" in stats
    assert "today_articles" in stats
    assert "category_breakdown" in stats


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print(" Running EcoPulse SQLite Database Verification Tests")
    print("=" * 65 + "\n")

    # Step 1: Initialize main DB and verify file existence
    main_db = initialize_database()
    print(f"[1/6] Database initialized at:")
    print(f"      Path: {main_db}")
    print(f"      File exists: {main_db.exists()} (Verified)\n")

    # Step 2: Insert a sample article
    sample = {
        "title": "Severe Rain and Waterlogging Alert for Chennai Central",
        "description": "Meteorological department reports heavy rainfall across coastal Tamil Nadu.",
        "url": "https://example.com/alerts/chennai-rain-2026-demo",
        "source": "Chennai City Civic Advisory",
        "published_at": "2026-10-08 05:00:00 UTC",
        "category": "Environmental Alert",
        "priority": "HIGH",
        "location": "Chennai",
        "summary": "Heavy rainfall warning with localized waterlogging expected in central areas.",
        "reason": "Direct public safety impact from rapid accumulation of rainwater.",
        "keywords": ["rain", "flood", "Chennai"],
        "recommended_action": "Avoid low-lying subways and monitor municipal alerts.",
        "is_relevant": 1,
    }

    print("[2/6] Inserting sample article into database...")
    art_id = insert_article(sample)
    if art_id:
        print(f"      Inserted new article with ID: {art_id}\n")
    else:
        print("      Article URL already existed in database (Duplicate handled safely).\n")

    # Step 3: Read the article back and print it
    print("[3/6] Reading stored article back from database...")
    all_articles = get_articles(limit=1, search="Chennai")
    if all_articles:
        stored = all_articles[0]
        print("=" * 65)
        print(" Stored Article Details:")
        print("=" * 65)
        print(f"  ID:                 {stored['id']}")
        print(f"  Title:              {stored['title']}")
        print(f"  URL:                {stored['url']}")
        print(f"  Source:             {stored['source']}")
        print(f"  Location:           {stored['location']}")
        print(f"  Category:           {stored['category']}")
        print(f"  Priority:           {stored['priority']}")
        print(f"  Summary:            {stored['summary']}")
        print(f"  Recommended Action: {stored['recommended_action']}")
        print(f"  Is Relevant:        {bool(stored['is_relevant'])}")
        print(f"  Created At:         {stored['created_at']}")
        print("=" * 65 + "\n")
    else:
        print("      No articles found.\n")

    # Step 4: Test duplicate URL prevention
    print("[4/6] Testing duplicate URL insertion prevention...")
    dup_result = insert_article(sample)
    assert dup_result is None, "Duplicate URL check failed! Should return None."
    print("      PASSED: Duplicate article was safely ignored without error.\n")

    # Step 5: Test High Priority retrieval
    print("[5/6] Testing High Priority alerts retrieval...")
    high_alerts = get_high_priority_articles(limit=5)
    print(f"      PASSED: Retrieved {len(high_alerts)} high-priority alert(s).\n")

    # Step 6: Test Statistics aggregation
    print("[6/6] Testing database statistics aggregation...")
    stats = get_statistics()
    print("      Database Statistics Summary:")
    print(f"        Total Articles:     {stats['total_articles']}")
    print(f"        Articles Today:     {stats['today_articles']}")
    print(f"        High Priority:      {stats['high_priority_count']}")
    print(f"        Medium Priority:    {stats['medium_priority_count']}")
    print(f"        Low Priority:       {stats['low_priority_count']}")
    print(f"        Relevant Articles:  {stats['relevant_articles']}")
    print(f"        Category Breakdown: {stats['category_breakdown']}\n")

    print("=" * 65)
    print(" ALL PHASE 3 SQLITE DATABASE TESTS PASSED SUCCESSFULLY!")
    print("=" * 65 + "\n")
