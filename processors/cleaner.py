"""Text and HTML cleaning and normalization processor for EcoPulse.

Provides functions to:
- Strip HTML markup and decode HTML entities from titles and descriptions.
- Normalize excessive whitespace and line breaks.
- Handle empty descriptions gracefully.
- Normalize titles for content comparison and duplicate detection.
- Normalize URLs by stripping tracking parameters (UTM, campaign tags)
  while preserving the original URL for database persistence.
"""

import html
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from bs4 import BeautifulSoup

# Standard marketing and analytics tracking parameters to remove during comparison
TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "at_medium",
    "at_campaign",
    "fbclid",
    "gclid",
    "ref",
    "feedname",
    "feedtype",
}


def clean_html(raw_html: Optional[str]) -> str:
    """Strip HTML tags, decode entities, and normalize whitespace from text.

    Args:
        raw_html: Raw HTML snippet or string with potential tags.

    Returns:
        Clean, normalized plain text string, or empty string if input is empty.
    """
    if not raw_html or not isinstance(raw_html, str):
        return ""

    try:
        # 1. Parse with BeautifulSoup to strip all HTML tags cleanly
        soup = BeautifulSoup(raw_html, "html.parser")
        text = soup.get_text(separator=" ")

        # 2. Decode standard and numeric HTML entities (e.g. &amp;, &quot;, &#39;)
        text = html.unescape(text)

        # 3. Normalize spaces before punctuation (e.g. "word ." -> "word.")
        text = re.sub(r"\s+([.,!?;:)\]])", r"\1", text)
        text = re.sub(r"([(\[])\s+", r"\1", text)

        # 4. Collapse multiple whitespace characters and newlines into single spaces
        text = re.sub(r"\s+", " ", text).strip()
        return text
    except Exception:
        # Fallback regex tag stripping in case parser fails
        text = re.sub(r"<[^>]+>", " ", raw_html)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()


def clean_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Clean the title and description of an article dictionary.

    Preserves the original URL and all metadata fields.

    Args:
        article: Article dictionary with 'title' and 'description'.

    Returns:
        A new article dictionary with cleaned title and description.
    """
    cleaned = dict(article)
    cleaned["title"] = clean_html(article.get("title", ""))
    cleaned["description"] = clean_html(article.get("description", ""))
    return cleaned


def normalize_title(title: Optional[str]) -> str:
    """Normalize a title string for duplicate comparison.

    - Converts to lowercase
    - Normalizes HTML entities
    - Strips punctuation and symbols while keeping alphanumeric words
    - Collapses multiple spaces into a single space

    Args:
        title: The article title string.

    Returns:
        Normalized title suitable for exact content matching.
    """
    if not title or not isinstance(title, str):
        return ""

    # Clean HTML first if any
    cleaned = clean_html(title)
    # Convert to lowercase
    lowered = cleaned.lower()
    # Replace hyphens/underscores with spaces
    lowered = re.sub(r"[-_]", " ", lowered)
    # Remove all punctuation and special characters
    alphanumeric_only = re.sub(r"[^\w\s]", "", lowered)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", alphanumeric_only).strip()
    return normalized


def normalize_url(url: Optional[str]) -> str:
    """Normalize a URL for duplicate detection by removing tracking parameters and fragments.

    Does not modify the original URL stored in SQLite; this is used purely for comparison.

    Args:
        url: The web URL string.

    Returns:
        Canonical normalized URL string.
    """
    if not url or not isinstance(url, str):
        return ""

    url_str = url.strip()
    try:
        parsed = urlparse(url_str)
        # Filter out tracking query parameters
        filtered_params = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_params)

        # Normalize path: strip trailing slash if length > 1
        path = parsed.path
        if len(path) > 1 and path.endswith("/"):
            path = path.rstrip("/")

        # Reconstruct canonical URL without fragments or tracking params
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            "",  # Remove fragment (#...)
        ))
        return normalized
    except Exception:
        # If parsing fails, return trimmed original
        return url_str
