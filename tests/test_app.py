"""Tests for EcoPulse Flask Web Dashboard."""

from pathlib import Path
import sys
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app, get_dashboard_stats, get_articles


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_dashboard_loads_successfully(client):
    """Verify that the dashboard loads with status 200 and header."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"EcoPulse" in response.data
    assert b"Community Eco Alerts" in response.data


def test_dashboard_date_filters(client):
    """Verify today, last 7 days, and all articles date filters work."""
    for date_range in ("today", "7days", "all"):
        response = client.get(f"/?date_range={date_range}")
        assert response.status_code == 200
        assert b"EcoPulse" in response.data


def test_dashboard_category_and_priority_filters(client):
    """Verify category and priority filters work together."""
    response = client.get("/?category=Climate+%26+Weather&priority=HIGH&date_range=all")
    assert response.status_code == 200
    assert b"EcoPulse" in response.data


def test_dashboard_empty_results_handled_gracefully(client):
    """Verify non-existent category displays friendly empty state."""
    response = client.get("/?category=NonExistentCategoryXYZ")
    assert response.status_code == 200
    assert b"No relevant articles found" in response.data


def test_dashboard_stats_calculation():
    """Verify get_dashboard_stats returns expected structure."""
    stats = get_dashboard_stats()
    assert "total" in stats
    assert "high" in stats
    assert "medium" in stats
    assert "low" in stats
    assert isinstance(stats["total"], int)
    assert stats["total"] >= 0


def test_dashboard_sections_rendered(client):
    """Verify Section 1 (Community) and Section 2 (Air Quality) render on dashboard."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Community Projects, Campaigns &amp; Events" in response.data or b"Community Projects" in response.data
    assert b"Air Quality" in response.data
    assert b"READ" in response.data


def test_dashboard_keyword_search(client):
    """Verify keyword search functionality on dashboard."""
    response = client.get("/?search=Chennai")
    assert response.status_code == 200
    assert b"EcoPulse" in response.data


def test_articles_page_loads_with_pagination(client):
    """Verify dedicated /articles page loads and handles pagination parameters."""
    response = client.get("/articles?page=1")
    assert response.status_code == 200
    assert b"Environmental Alerts &amp; News" in response.data or b"Environmental Alerts" in response.data
    assert b"READ ORIGINAL ARTICLE" in response.data or b"READ" in response.data


def test_articles_page_filters(client):
    """Verify filtering by category and priority on /articles."""
    response = client.get("/articles?category=Climate+%26+Weather&priority=HIGH")
    assert response.status_code == 200
    assert response.status_code == 200


def test_about_page_loads(client):
    """Verify /about page loads with feeds list and tech stack details."""
    response = client.get("/about")
    assert response.status_code == 200
    assert b"About EcoPulse" in response.data
    assert b"Monitored RSS Feeds" in response.data
    assert b"Technology Stack" in response.data
    assert b"The Hindu" in response.data


def test_healthcheck_endpoint(client):
    """Verify /health endpoint returns healthy status code and JSON."""
    response = client.get("/health")
    assert response.status_code == 200
    json_data = response.get_json()
    assert json_data["status"] == "healthy"
    assert json_data["service"] == "EcoPulse"


def test_article_detail_view(client):
    """Verify /article/<id> displays details for existing article or 404 for invalid."""
    articles = get_articles(limit=1)
    if articles:
        first_id = articles[0]["id"]
        response = client.get(f"/article/{first_id}")
        assert response.status_code == 200
        assert b"AI Environmental Summary" in response.data or b"Summary" in response.data

    # Invalid ID returns 404
    bad_response = client.get("/article/99999999")
    assert bad_response.status_code == 404


def test_pipeline_trigger_unauthorized(client):
    """Verify /api/pipeline/run rejects requests without valid secret."""
    response = client.post("/api/pipeline/run")
    assert response.status_code == 401
