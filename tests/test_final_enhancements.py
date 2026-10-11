"""Comprehensive Tests for EcoPulse Final Enhancements.

Verifies:
1. Homepage branding: "Community Eco Alerts" and "Developed by Nivitha R" directly below the heading.
2. Removal of overt RSS promotional banners and UI labels.
3. Geographical regional alert categorization (India, Tamil Nadu, Chennai, Global).
4. Regional, category, priority, and keyword search filters.
5. Priority sorting (High first) vs Newest date sorting.
6. Preservation of 350+ historical articles in database with duplicate prevention.
7. GitHub Actions daily 7:00 AM IST workflow cron schedule (30 1 * * *) and manual dispatch.
"""

from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app, get_dashboard_stats, get_articles, count_articles, get_regional_counts
from database.database import insert_article, get_connection


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_homepage_branding_and_developer_credit(client):
    """Verify 'Community Eco Alerts' and 'Developed by Nivitha R' appear prominently."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Main heading
    assert "Community Eco Alerts" in html

    # Developer credit
    assert "Developed by" in html
    assert "Nivitha R" in html
    assert "developer-credit" in html

    # Order check: "Developed by Nivitha R" directly follows "Community Eco Alerts"
    heading_pos = html.find("<h1>Community Eco Alerts</h1>")
    credit_pos = html.find("Nivitha R")
    assert heading_pos != -1
    assert credit_pos != -1
    assert credit_pos > heading_pos
    # Credit should appear within 200 characters directly below the heading
    assert (credit_pos - heading_pos) < 200


def test_rss_promotional_banners_removed_from_ui(client):
    """Verify that RSS implementation details are hidden from the user interface."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # The promotional banner must NOT be present
    assert "Live RSS Feed Aggregation • Automated AI Analysis" not in html
    assert "7 RSS Feeds Monitored" not in html

    # Accurate, user-facing label is used instead
    assert "Multiple Environmental Information Sources" in html or "Environmental Information Sources" in html


def test_geographical_categories_present(client):
    """Verify the 4 geographical categories are configured and prioritized."""
    response = client.get("/articles")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # 4 Geographical categories in the region filter
    assert "Chennai — Local Alerts" in html
    assert "Tamil Nadu — State Alerts" in html
    assert "India — National Alerts" in html
    assert "Other Relevant Global Alerts" in html


def test_region_filtering_functional(client):
    """Verify filtering articles by specific geographical region works."""
    for region in ("chennai", "tamil_nadu", "india", "global"):
        response = client.get(f"/?region={region}")
        assert response.status_code == 200
        assert b"Community Eco Alerts" in response.data

    # Count functions return non-negative counts
    counts = get_regional_counts()
    assert "chennai" in counts
    assert "tamil_nadu" in counts
    assert "india" in counts
    assert "global" in counts
    assert counts["india"] > 0
    assert counts["chennai"] > 0


def test_sort_order_options(client):
    """Verify sorting by highest priority and newest publication date."""
    resp_priority = client.get("/?sort_by=priority")
    assert resp_priority.status_code == 200

    resp_newest = client.get("/?sort_by=newest")
    assert resp_newest.status_code == 200

    # In database query, verify priority sort places HIGH ahead of LOW
    high_first = get_articles(sort_by="priority", limit=15)
    assert len(high_first) > 0
    priorities = [a["priority"].upper() for a in high_first if a["priority"]]
    if "HIGH" in priorities and "LOW" in priorities:
        assert priorities.index("HIGH") < priorities.index("LOW")


def test_article_card_metadata_displayed(client):
    """Verify location, category, priority, and date metadata are rendered on cards."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "feed-location" in html
    assert "category-badge" in html
    assert "priority-pill" in html
    assert "feed-meta-row" in html or "feed-time-block" in html


def test_database_preserves_historical_records_and_deduplication():
    """Verify historical articles are preserved (>= 350) and duplicate URLs are prevented."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM articles")
        total = cur.fetchone()[0]
        assert total >= 350, f"Expected at least 350 historical articles, found {total}"

        # Deduplication check: inserting existing URL must return None and keep count identical
        cur.execute("SELECT url, title FROM articles LIMIT 1")
        existing = cur.fetchone()
        existing_url = existing["url"]

        dup_result = insert_article({
            "title": "Duplicate Article Test",
            "url": existing_url,
            "source": "Test",
        })
        assert dup_result is None

        cur.execute("SELECT COUNT(*) FROM articles")
        total_after = cur.fetchone()[0]
        assert total_after == total
    finally:
        conn.close()


def test_github_actions_workflow_cron_schedule():
    """Verify .github/workflows/daily_pipeline.yml is configured for 7:00 AM IST (01:30 UTC)."""
    workflow_path = ROOT_DIR / ".github" / "workflows" / "daily_pipeline.yml"
    assert workflow_path.exists(), "Workflow file does not exist"

    content = workflow_path.read_text(encoding="utf-8")
    # Expected cron schedule: '30 1 * * *' (01:30 UTC = 07:00 IST)
    assert "cron: '30 1 * * *'" in content or "cron: \"30 1 * * *\"" in content
    # Manual trigger
    assert "workflow_dispatch:" in content
    # Concurrency control
    assert "concurrency:" in content
    # Pipeline execution
    assert "python pipeline.py" in content
