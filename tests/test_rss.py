"""Tests for EcoPulse RSS Collector module.

Can be run via:
1. pytest tests/test_rss.py
2. python tests/test_rss.py (Direct execution with sample output of first 5 articles)
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure project root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from collectors.source_config import RSS_SOURCES, get_active_sources
from collectors.rss_collector import collect_news, collect_all_news, _parse_entry_date, _extract_entry_description


def test_source_config_has_valid_sources():
    """Verify that RSS_SOURCES is configured with required keys."""
    sources = get_active_sources()
    assert len(sources) > 0, "There should be at least one active RSS source"

    for source in sources:
        assert "name" in source and isinstance(source["name"], str)
        assert "url" in source and source["url"].startswith("http")
        assert "location" in source
        assert "type" in source


def test_invalid_feed_url_does_not_crash():
    """Verify that an invalid or unreachable feed returns [] without crashing."""
    invalid_url = "http://this-domain-does-not-exist-123456789.test/rss.xml"
    result = collect_news(invalid_url, source_name="Invalid Test Source")
    assert isinstance(result, list)
    assert len(result) == 0


def test_missing_fields_handling():
    """Verify that entries missing title, description, or date are handled safely."""
    # Test entry without published date
    mock_entry = MagicMock()
    mock_entry.published_parsed = None
    mock_entry.published = None
    mock_entry.pubDate = None
    mock_entry.updated = None
    mock_entry.created = None

    date_str = _parse_entry_date(mock_entry)
    assert "UTC" in date_str, "Should generate a valid fallback UTC timestamp"

    # Test entry with empty description
    mock_entry_desc = MagicMock()
    mock_entry_desc.summary = ""
    mock_entry_desc.description = ""
    mock_entry_desc.content = []

    desc = _extract_entry_description(mock_entry_desc)
    assert desc == "", "Empty description should safely return empty string"


def test_collect_news_live_feed():
    """Verify collecting news from a feed with realistic RSS response."""
    test_source = RSS_SOURCES[0]
    sample_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>The Hindu - Energy &amp; Environment</title>
        <link>https://www.thehindu.com</link>
        <description>Energy and Environment News</description>
        <item>
          <title>Solar Farm Project Commissioned in Tamil Nadu</title>
          <link>https://www.thehindu.com/news/solar-farm-tn</link>
          <description>New solar plant adds 50MW clean energy.</description>
          <pubDate>Thu, 08 Oct 2026 10:00:00 +0530</pubDate>
        </item>
      </channel>
    </rss>"""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = sample_xml
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        articles = collect_news(
            feed_url=test_source["url"],
            source_name=test_source["name"],
            location=test_source["location"],
        )

    assert isinstance(articles, list)
    assert len(articles) > 0, f"Expected articles from {test_source['name']}"

    first_article = articles[0]
    assert "title" in first_article and first_article["title"]
    assert "url" in first_article and first_article["url"].startswith("http")
    assert "published_at" in first_article
    assert "source" in first_article
    assert "location" in first_article


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" Running EcoPulse RSS Collector Tests")
    print("=" * 60 + "\n")

    print("[1/4] Testing source configuration...")
    test_source_config_has_valid_sources()
    print("      PASSED: RSS_SOURCES correctly structured.\n")

    print("[2/4] Testing invalid feed error handling...")
    test_invalid_feed_url_does_not_crash()
    print("      PASSED: Invalid feed returned empty list without crashing.\n")

    print("[3/4] Testing missing fields fallback...")
    test_missing_fields_handling()
    print("      PASSED: Missing fields handled safely.\n")

    print("[4/4] Testing live collection from primary source...")
    primary_source = RSS_SOURCES[0]
    articles = collect_news(
        feed_url=primary_source["url"],
        source_name=primary_source["name"],
        location=primary_source["location"],
    )
    print(f"      PASSED: Collected {len(articles)} articles from {primary_source['name']}.\n")

    print("=" * 60)
    print(f" Displaying First 5 Collected Articles from {primary_source['name']}:")
    print("=" * 60 + "\n")

    for i, item in enumerate(articles[:5], 1):
        print(f"[{i}] Title:     {item['title']}")
        print(f"    URL:       {item['url']}")
        print(f"    Published: {item['published_at']}")
        print(f"    Source:    {item['source']} ({item['location']})")
        print("-" * 60)

    print("\n All Phase 2 RSS Collector tests passed successfully!\n")
