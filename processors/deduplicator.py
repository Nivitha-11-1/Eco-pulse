"""Deduplication processor for EcoPulse.

Provides multi-layer duplicate detection:
1. Exact and normalized URL matching (strips tracking parameters).
2. Normalized title matching within same/similar source and across identical content.
3. In-batch and database-level duplicate filtering.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from processors.cleaner import normalize_title, normalize_url


class ArticleDeduplicator:
    """Manages duplicate detection for news articles."""

    def __init__(
        self,
        existing_urls: Optional[Set[str]] = None,
        existing_normalized_urls: Optional[Set[str]] = None,
        existing_titles: Optional[Set[Tuple[str, str]]] = None,
    ):
        """Initialize deduplicator with optional sets of known article signatures.

        Args:
            existing_urls: Set of exact raw URLs already stored.
            existing_normalized_urls: Set of canonical/cleaned URLs already stored.
            existing_titles: Set of (source_key, normalized_title) tuples already stored.
        """
        self.seen_raw_urls: Set[str] = set(existing_urls or [])
        self.seen_normalized_urls: Set[str] = set(existing_normalized_urls or [])
        self.seen_titles: Set[Tuple[str, str]] = set(existing_titles or [])

    def register_article(self, article: Dict[str, Any]) -> None:
        """Register an accepted article's signatures to prevent subsequent duplicates."""
        raw_url = article.get("url", "").strip()
        norm_url = normalize_url(raw_url)
        norm_title = normalize_title(article.get("title", ""))
        source_key = (article.get("source", "") or "").strip().lower()

        if raw_url:
            self.seen_raw_urls.add(raw_url)
        if norm_url:
            self.seen_normalized_urls.add(norm_url)
        if norm_title:
            self.seen_titles.add((source_key, norm_title))

    def check_duplicate(self, article: Dict[str, Any]) -> Tuple[bool, str]:
        """Check if an article is a duplicate based on URL or title similarity.

        Args:
            article: Article dictionary with 'title', 'url', and 'source'.

        Returns:
            Tuple of (is_duplicate: bool, reason: str).
            Reason can be 'exact_url', 'normalized_url', 'normalized_title', or ''.
        """
        raw_url = article.get("url", "").strip()
        norm_url = normalize_url(raw_url)
        norm_title = normalize_title(article.get("title", ""))
        source_key = (article.get("source", "") or "").strip().lower()

        # 1. Exact URL match
        if raw_url and raw_url in self.seen_raw_urls:
            return True, "exact_url"

        # 2. Normalized URL match (e.g., same destination, different tracking query params)
        if norm_url and norm_url in self.seen_normalized_urls:
            return True, "normalized_url"

        # 3. Normalized title match within the same source or empty source
        if norm_title and (source_key, norm_title) in self.seen_titles:
            return True, "normalized_title"

        return False, ""

    def filter_batch(
        self,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Filter a list of articles, separating new unique articles from duplicates.

        Args:
            articles: List of candidate article dictionaries.

        Returns:
            Dictionary with:
              - 'unique_articles': list of articles to proceed with
              - 'url_duplicates_count': number of duplicate URLs skipped
              - 'title_duplicates_count': number of duplicate titles skipped
              - 'total_duplicates_count': total duplicates
        """
        unique_articles: List[Dict[str, Any]] = []
        url_duplicates_count = 0
        title_duplicates_count = 0

        for item in articles:
            is_dup, reason = self.check_duplicate(item)
            if is_dup:
                if reason in ("exact_url", "normalized_url"):
                    url_duplicates_count += 1
                elif reason == "normalized_title":
                    title_duplicates_count += 1
            else:
                self.register_article(item)
                unique_articles.append(item)

        return {
            "unique_articles": unique_articles,
            "url_duplicates_count": url_duplicates_count,
            "title_duplicates_count": title_duplicates_count,
            "total_duplicates_count": url_duplicates_count + title_duplicates_count,
        }


def deduplicate_articles(
    articles: List[Dict[str, Any]],
    existing_articles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Convenience helper to deduplicate a list of articles against an optional existing set.

    Args:
        articles: List of incoming articles.
        existing_articles: Optional list of articles already in the database.

    Returns:
        Summary dictionary with 'unique_articles', 'url_duplicates_count',
        and 'title_duplicates_count'.
    """
    deduplicator = ArticleDeduplicator()

    if existing_articles:
        for ex in existing_articles:
            deduplicator.register_article(ex)

    return deduplicator.filter_batch(articles)
