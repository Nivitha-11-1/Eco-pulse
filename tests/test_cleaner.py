"""Tests for EcoPulse Text Cleaner and Normalization Processor.

Verifies:
1. HTML tag removal from titles and descriptions.
2. HTML entity decoding (&amp;, &quot;, &#39;, &nbsp;).
3. Whitespace normalization (collapsing extra spaces and newlines).
4. Safe handling of empty, None, and whitespace-only content.
5. Article dictionary cleaning in-place preserving original metadata.
6. Title normalization for duplicate detection.
7. URL normalization (stripping tracking parameters and fragments).

Can be run via:
- pytest tests/test_cleaner.py
- python tests/test_cleaner.py
"""

from pathlib import Path
import sys

# Ensure root directory is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from processors.cleaner import (
    clean_html,
    clean_article,
    normalize_title,
    normalize_url,
)


def test_html_tag_removal():
    """Verify that all HTML tags are stripped from text."""
    raw = "<p>Heavy rainfall warning for <strong>coastal districts</strong>. <a href='https://example.com'>Read more</a></p>"
    cleaned = clean_html(raw)
    assert "<p>" not in cleaned
    assert "<strong>" not in cleaned
    assert "</a>" not in cleaned
    assert cleaned == "Heavy rainfall warning for coastal districts. Read more"


def test_html_entity_decoding():
    """Verify that HTML entities are converted to normal characters."""
    raw = "Environment &amp; Climate: It&#39;s &quot;urgent&quot; &ndash; action required &nbsp; now!"
    cleaned = clean_html(raw)
    assert "&amp;" not in cleaned
    assert "&quot;" not in cleaned
    assert "&#39;" not in cleaned
    assert "Environment & Climate: It's \"urgent\" – action required now!" in cleaned


def test_whitespace_cleanup():
    """Verify that multiple spaces, tabs, and newlines are collapsed into single spaces."""
    raw = "   Flood   advisory    \n\n   issued   by   \t  city   authorities.   "
    cleaned = clean_html(raw)
    assert cleaned == "Flood advisory issued by city authorities."


def test_empty_content_handling():
    """Verify that empty, None, or pure-whitespace strings return empty string safely."""
    assert clean_html("") == ""
    assert clean_html(None) == ""
    assert clean_html("    ") == ""
    assert clean_html("<p></p>") == ""
    assert clean_html("<div>  <span> </span>  </div>") == ""


def test_clean_article_helper():
    """Verify that clean_article cleans both title and description while keeping other fields."""
    raw_article = {
        "title": "<strong>Alert:</strong> Severe Rain in Chennai &amp; Suburbs",
        "description": "<p>Municipal corporations have deployed <em>water pumps</em>.</p>",
        "url": "https://example.com/alerts/rain-chennai",
        "source": "Chennai Weather",
        "location": "Chennai",
    }

    cleaned = clean_article(raw_article)
    assert cleaned["title"] == "Alert: Severe Rain in Chennai & Suburbs"
    assert cleaned["description"] == "Municipal corporations have deployed water pumps."
    assert cleaned["url"] == raw_article["url"]
    assert cleaned["source"] == "Chennai Weather"
    assert cleaned["location"] == "Chennai"


def test_title_normalization():
    """Verify title normalization for comparison and duplicate detection."""
    # Test case sensitivity and punctuation
    title_1 = "Severe Flood Alert: Chennai Central (High Priority!)"
    title_2 = "  severe flood alert chennai central high priority   "

    norm_1 = normalize_title(title_1)
    norm_2 = normalize_title(title_2)

    assert norm_1 == "severe flood alert chennai central high priority"
    assert norm_1 == norm_2, "Titles should normalize to identical strings for duplicate matching"

    # Test hyphens and special quotes
    title_3 = "Eco-Friendly Campus &mdash; Green Initiatives"
    assert normalize_title(title_3) == "eco friendly campus green initiatives"


def test_url_normalization():
    """Verify URL normalization strips tracking parameters while keeping original content params."""
    # Tracking parameters to be removed
    tracking_url = "https://example.com/news/rain-alert?utm_source=rss&utm_medium=feed&at_campaign=daily#comments"
    norm = normalize_url(tracking_url)
    assert norm == "https://example.com/news/rain-alert"

    # Legitimate non-tracking parameters should be preserved
    content_url = "https://example.com/search?q=flood&page=2&utm_medium=rss"
    norm_content = normalize_url(content_url)
    assert "q=flood" in norm_content
    assert "page=2" in norm_content
    assert "utm_medium" not in norm_content

    # Trailing slash removal
    slash_url = "https://example.com/article/"
    assert normalize_url(slash_url) == "https://example.com/article"


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print(" Running EcoPulse Cleaner & Normalization Tests (Phase 5)")
    print("=" * 65 + "\n")

    print("[1/7] Testing HTML tag removal...")
    test_html_tag_removal()
    print("      PASSED: All tags stripped successfully.\n")

    print("[2/7] Testing HTML entity decoding...")
    test_html_entity_decoding()
    print("      PASSED: Entities (&amp;, &quot;, &#39;) decoded.\n")

    print("[3/7] Testing whitespace cleanup...")
    test_whitespace_cleanup()
    print("      PASSED: Whitespace collapsed to single spaces.\n")

    print("[4/7] Testing empty content handling...")
    test_empty_content_handling()
    print("      PASSED: Empty inputs handled without errors.\n")

    print("[5/7] Testing clean_article helper...")
    test_clean_article_helper()
    print("      PASSED: Article dictionary fields sanitized.\n")

    print("[6/7] Testing title normalization for duplicate matching...")
    test_title_normalization()
    print("      PASSED: Titles normalized accurately.\n")

    print("[7/7] Testing URL normalization (tracking param removal)...")
    test_url_normalization()
    print("      PASSED: Tracking parameters stripped cleanly.\n")

    print("=" * 65)
    print(" ALL CLEANER TESTS PASSED SUCCESSFULLY!")
    print("=" * 65 + "\n")
