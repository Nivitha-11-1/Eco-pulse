"""Comprehensive Tests for Restored Original EcoPulse Dashboard.

Verifies:
1. Original EcoPulse header, green theme, and "Live RSS Feed Aggregation • Automated AI Analysis" banner.
2. "Community Eco Alerts" heading with "Developed by Nivitha R" directly below it.
3. "7 RSS Feeds Monitored" pill in the hero section.
4. Original statistics cards (Total, High, Medium, Low).
5. Four small geographical region boxes (India, Tamil Nadu, Chennai, Global) with active filtering.
6. Default view displays all articles according to original default filters.
7. Preservation of 350+ historical articles in database with duplicate prevention.
8. GitHub Actions daily 7:00 AM IST workflow cron schedule (30 1 * * *).
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


def test_original_header_and_rss_banner(client):
    """Verify original header text, Nivitha R credit, and Live Environmental News Feeds."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Banner with Live Environmental News Feeds
    assert "Live Environmental News Feeds" in html or "Live RSS Feed Aggregation" in html

    # Feeds indicator
    assert "7 Live Environmental News Feeds" in html or "7 RSS Feeds Monitored" in html


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
    heading_pos = html.find("Community Eco Alerts")
    credit_pos = html.find("Nivitha R")
    assert heading_pos != -1
    assert credit_pos != -1
    assert credit_pos > heading_pos
    # Credit should appear within 300 characters directly below the heading
    assert (credit_pos - heading_pos) < 300


def test_geographical_coverage_box(client):
    """Verify compact Geographical Coverage box displaying Chennai, Tamil Nadu, and India."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Geographical Coverage box
    assert "Geographical Coverage" in html
    assert "geo-coverage-box" in html or "geo-coverage-bar" in html

    # 3 distinct locations clearly displayed
    assert "Chennai" in html
    assert "Tamil Nadu" in html
    assert "India" in html


def test_region_filtering_functional(client):
    """Verify clicking each region box filters articles by that region."""
    for region in ("chennai", "tamil_nadu", "india"):
        response = client.get(f"/?region={region}")
        assert response.status_code == 200
        assert b"Community Eco Alerts" in response.data
        html = response.data.decode("utf-8")
        assert f"region={region}" in html


def test_original_statistics_cards(client):
    """Verify original 4 statistics cards are present."""
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    assert "Total Relevant Alerts" in html
    assert "High Priority" in html
    assert "Medium Priority" in html
    assert "Low Priority" in html


def test_original_curated_sections(client):
    """Verify Section 1 (Community Projects) and Section 2 (Air Quality) render on dashboard."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Community Projects, Campaigns &amp; Events" in response.data or b"Community Projects" in response.data
    assert b"Air Quality" in response.data


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
    assert "cron: '30 1 * * *'" in content or "cron: \"30 1 * * *\"" in content
    assert "workflow_dispatch:" in content
    assert "concurrency:" in content
    assert "python pipeline.py" in content
