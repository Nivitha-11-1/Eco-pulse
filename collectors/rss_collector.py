"""RSS Collector Module for EcoPulse.

Fetches and normalizes news articles from RSS feeds using feedparser.
Handles missing fields, malformed feeds, and network connectivity errors safely.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List
import feedparser
import requests

import sys
from pathlib import Path

# Ensure root directory is in Python path for direct script execution
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

try:
    from collectors.source_config import RSS_SOURCES, get_active_sources
except ImportError:
    from source_config import RSS_SOURCES, get_active_sources  # type: ignore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("EcoPulse.RSSCollector")

# Standard headers to ensure respectful requests and avoid 403 Forbidden errors
DEFAULT_HEADERS = {
    "User-Agent": "EcoPulse-Community-Aggregator/1.0 (+https://github.com/ecopulse)"
}
REQUEST_TIMEOUT = 12  # seconds


def _parse_entry_date(entry: Any) -> str:
    """Safely extracts and formats the publication date of an RSS entry.

    Falls back to current UTC timestamp if missing.
    """
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    # Alternative date fields
    for field in ("published", "pubDate", "updated", "created"):
        val = getattr(entry, field, None) or entry.get(field)
        if val and isinstance(val, str) and val.strip():
            return val.strip()

    # Fallback if no publication date is present in feed
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _extract_entry_description(entry: Any) -> str:
    """Safely extracts description or summary text from an RSS entry."""
    # Check 'summary' first
    summary = getattr(entry, "summary", "") or entry.get("summary", "")
    if summary and isinstance(summary, str) and summary.strip():
        return summary.strip()

    # Check 'description'
    desc = getattr(entry, "description", "") or entry.get("description", "")
    if desc and isinstance(desc, str) and desc.strip():
        return desc.strip()

    # Check 'content' list if available
    content_list = getattr(entry, "content", None) or entry.get("content", [])
    if isinstance(content_list, list) and len(content_list) > 0:
        first_content = content_list[0]
        if isinstance(first_content, dict) and "value" in first_content:
            return str(first_content["value"]).strip()

    return ""


def collect_news(
    feed_url: str,
    source_name: str = "Unknown Source",
    location: str = "General",
) -> List[Dict[str, Any]]:
    """Fetch and parse articles from a single RSS feed URL.

    Args:
        feed_url: The URL of the RSS feed.
        source_name: The display name of the news provider.
        location: The geographic focus or 'Global'/'General'.

    Returns:
        List of structured article dictionaries.
        Returns an empty list on failure without crashing.
    """
    if not feed_url or not isinstance(feed_url, str):
        logger.warning("Empty or invalid feed URL provided: %s", feed_url)
        return []

    articles: List[Dict[str, Any]] = []

    try:
        logger.info("Fetching RSS feed: '%s' (%s)", source_name, feed_url)

        # Use requests with timeout and custom User-Agent to avoid blocking
        response = requests.get(
            feed_url,
            headers=DEFAULT_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        raw_content = response.content

        # Parse XML content with feedparser
        feed = feedparser.parse(raw_content)

    except requests.exceptions.RequestException as net_err:
        logger.error(
            "Network error fetching feed '%s' from %s: %s",
            source_name,
            feed_url,
            str(net_err),
        )
        # Try direct feedparser parse as a graceful fallback
        try:
            logger.info("Attempting direct feedparser fallback for %s...", feed_url)
            feed = feedparser.parse(feed_url)
        except Exception as fallback_err:
            logger.error("Fallback also failed for %s: %s", feed_url, str(fallback_err))
            return []
    except Exception as err:
        logger.error("Unexpected error fetching feed '%s': %s", source_name, str(err))
        return []

    # Check if feed parsed any entries
    entries = getattr(feed, "entries", [])
    if not entries:
        # Check if feedparser reported a bozo (malformed XML) error
        bozo_msg = getattr(feed, "bozo_exception", "No entries found")
        logger.warning(
            "Feed '%s' returned 0 entries. Details: %s", source_name, bozo_msg
        )
        return []

    for entry in entries:
        # 1. Safely extract title
        raw_title = getattr(entry, "title", "") or entry.get("title", "")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else "Untitled Article"

        # 2. Safely extract URL
        raw_url = getattr(entry, "link", "") or entry.get("link", "")
        if not raw_url:
            raw_url = getattr(entry, "id", "") or entry.get("id", "")
        url = raw_url.strip() if isinstance(raw_url, str) else ""

        # Skip entries with no URL
        if not url:
            continue

        # 3. Safely extract description
        description = _extract_entry_description(entry)

        # 4. Safely extract publication date
        published_at = _parse_entry_date(entry)

        articles.append(
            {
                "title": title,
                "description": description,
                "url": url,
                "published_at": published_at,
                "source": source_name,
                "location": location,
            }
        )

    logger.info(
        "Successfully collected %d articles from '%s'.", len(articles), source_name
    )
    return articles


def collect_all_news(sources: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Collect news from all configured active RSS sources.

    Continues processing remaining feeds even if one or more feeds fail.

    Args:
        sources: Optional custom source list. Defaults to active sources in source_config.

    Returns:
        Combined list of all extracted articles.
    """
    if sources is None:
        sources = get_active_sources()

    all_articles: List[Dict[str, Any]] = []

    logger.info("Starting collection across %d RSS sources...", len(sources))

    for source in sources:
        s_name = source.get("name", "Unknown Source")
        s_url = source.get("url", "")
        s_location = source.get("location", "General")

        try:
            items = collect_news(
                feed_url=s_url,
                source_name=s_name,
                location=s_location,
            )
            all_articles.extend(items)
        except Exception as exc:
            # Shield entire pipeline from unhandled exceptions in a single source
            logger.error(
                "Critical error while processing source '%s' (%s): %s. Continuing...",
                s_name,
                s_url,
                str(exc),
            )

    logger.info("Total articles collected across all sources: %d", len(all_articles))
    return all_articles


if __name__ == "__main__":
    print("\n=======================================================")
    print(" EcoPulse RSS News Collector (Test Run)")
    print("=======================================================\n")

    results = collect_all_news()

    print(f"\nTotal articles fetched: {len(results)}\n")
    print("-------------------------------------------------------")
    print(" Displaying the First 5 Collected Articles:")
    print("-------------------------------------------------------\n")

    for idx, article in enumerate(results[:5], 1):
        print(f"[{idx}] {article['title']}")
        print(f"    URL:          {article['url']}")
        print(f"    Published:    {article['published_at']}")
        print(f"    Source:       {article['source']} ({article['location']})")
        print("-------------------------------------------------------")
