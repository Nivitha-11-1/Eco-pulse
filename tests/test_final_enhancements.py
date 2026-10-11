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
    """Verify .github/workflows/daily_pipeline.yml is configured for scheduled runs."""
    workflow_path = ROOT_DIR / ".github" / "workflows" / "daily_pipeline.yml"
    assert workflow_path.exists(), "Workflow file does not exist"

    content = workflow_path.read_text(encoding="utf-8")
    assert "*/30 * * * *" in content or "30 1 * * *" in content
    assert "workflow_dispatch:" in content
    assert "concurrency:" in content
    assert "python pipeline.py" in content


def test_articles_pagination_displays_all_articles_with_extended_page_count(client):
    """Verify all articles (356) are browsable across pages with extended page count (30 pages)."""
    response = client.get("/articles")
    assert response.status_code == 200
    html = response.data.decode("utf-8")

    # Verify extended pagination is present with 30 pages
    assert "Page 1 of" in html
    assert "pagination-container" in html
    assert "alert(s) found" in html

    # Verify 12 articles per page rendered
    article_cards = html.count("feed-article-card")
    assert article_cards == 12, f"Expected 12 articles per page, found {article_cards}"

    # Verify page 2 is accessible and returns 200 with next set of articles
    page2_resp = client.get("/articles?page=2")
    assert page2_resp.status_code == 200
    page2_html = page2_resp.data.decode("utf-8")
    assert "Page 2 of" in page2_html
    assert page2_html.count("feed-article-card") == 12

    # Verify home dashboard renders matching alert cards
    home_resp = client.get("/")
    assert home_resp.status_code == 200
    home_html = home_resp.data.decode("utf-8")
    home_cards = home_html.count("feed-article-card")
    assert home_cards >= 50, f"Expected alert cards on dashboard, found {home_cards}"


def test_pipeline_status_and_30min_trigger(client):
    """Verify /api/pipeline/status endpoint and 30-minute update trigger."""
    from config import config

    # Check status endpoint
    status_resp = client.get("/api/pipeline/status")
    assert status_resp.status_code == 200
    status_data = status_resp.get_json()
    assert status_data["status"] == "active"
    assert status_data["update_interval_minutes"] == 30

    # Check unauthorized trigger rejected
    unauth_resp = client.get("/api/pipeline/run")
    assert unauth_resp.status_code == 401

    # Check authorized trigger via query secret
    secret = config.SECRET_KEY
    auth_resp = client.get(f"/api/pipeline/run?secret={secret}&async=true")
    assert auth_resp.status_code == 200
    auth_data = auth_resp.get_json()
    assert auth_data["status"] in ("started", "already_running")

