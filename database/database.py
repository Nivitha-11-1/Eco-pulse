"""Database management module for EcoPulse.

Handles SQLite connection, schema creation, parameterized queries,
deduplication on URLs, and article retrieval.
"""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging
logger = logging.getLogger("EcoPulse.Database")

# Determine default database path
_BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = _BASE_DIR / "data" / "news.db"


def get_db_path(custom_path: Optional[Union[str, Path]] = None) -> Path:
    """Resolve database path, falling back to config or default."""
    if custom_path:
        return Path(custom_path)

    try:
        from config import config
        return Path(config.DATABASE_PATH)
    except Exception:
        return DEFAULT_DB_PATH


from contextlib import contextmanager


def get_connection(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    """Create and return a SQLite database connection with row factory enabled."""
    target_path = get_db_path(db_path)
    # Ensure parent data directory exists
    os.makedirs(target_path.parent, exist_ok=True)

    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    # Enable foreign keys and WAL mode for better concurrency
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_db_connection(db_path: Optional[Union[str, Path]] = None):
    """Context manager that ensures the SQLite connection is committed and closed."""
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def initialize_database(
    db_path: Optional[Union[str, Path]] = None,
    auto_seed: bool = False,
) -> Path:
    """Initialize SQLite database and create the 'articles' table if it doesn't exist.

    Args:
        db_path: Optional custom path to database file.
        auto_seed: If True and database is empty, seed with seed_articles.json.

    Returns:
        Path to the initialized database file.
    """
    target_path = get_db_path(db_path)
    os.makedirs(target_path.parent, exist_ok=True)

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        url TEXT UNIQUE NOT NULL,
        source TEXT,
        published_at TEXT,
        collected_at TEXT,
        category TEXT,
        priority TEXT,
        location TEXT,
        summary TEXT,
        reason TEXT,
        keywords TEXT,
        recommended_action TEXT,
        is_relevant INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    create_indexes_sql = [
        "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);",
        "CREATE INDEX IF NOT EXISTS idx_articles_priority ON articles(priority);",
        "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);",
        "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_articles_is_relevant ON articles(is_relevant);",
    ]

    with get_db_connection(target_path) as conn:
        conn.execute(create_table_sql)
        for index_sql in create_indexes_sql:
            conn.execute(index_sql)
        conn.commit()

        # Auto-seed if requested and table is empty
        if auto_seed:
            try:
                count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                seed_file = target_path.parent / "seed_articles.json"
                if not seed_file.exists():
                    seed_file = _BASE_DIR / "data" / "seed_articles.json"
                if count == 0 and seed_file.exists():
                    with open(seed_file, "r", encoding="utf-8") as f:
                        seed_data = json.load(f)
                    for art in seed_data:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO articles (
                                id, title, description, url, source, published_at, collected_at,
                                category, priority, location, summary, reason, keywords,
                                recommended_action, is_relevant, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                art.get("id"),
                                art.get("title", ""),
                                art.get("description", ""),
                                art.get("url", ""),
                                art.get("source", ""),
                                art.get("published_at"),
                                art.get("collected_at"),
                                art.get("category"),
                                art.get("priority"),
                                art.get("location"),
                                art.get("summary"),
                                art.get("reason"),
                                _prepare_keywords(art.get("keywords")),
                                art.get("recommended_action"),
                                art.get("is_relevant", 0),
                                art.get("created_at"),
                            ),
                        )
                    conn.commit()
                    logger.info("Auto-seeded %d articles into %s", len(seed_data), target_path)
            except Exception as e:
                logger.warning("Could not auto-seed database: %s", e)

    logger.info("Database initialized successfully at: %s", target_path)
    return target_path


def _prepare_keywords(keywords_val: Any) -> str:
    """Convert keywords into stored string representation."""
    if isinstance(keywords_val, list):
        return json.dumps(keywords_val)
    if keywords_val is None:
        return ""
    return str(keywords_val)


def insert_article(
    article: Dict[str, Any],
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[int]:
    """Insert a single article into the database.

    Safely handles duplicate URLs: if the URL already exists,
    the insertion is skipped and None is returned.

    Args:
        article: Dictionary of article attributes.
        db_path: Optional database path.

    Returns:
        The integer article ID if inserted, or None if skipped (duplicate/error).
    """
    url = article.get("url", "").strip()
    title = article.get("title", "").strip()

    if not url or not title:
        logger.warning("Skipping article with missing title or URL: %s", article)
        return None

    collected_at = article.get("collected_at")
    if not collected_at:
        collected_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    keywords_str = _prepare_keywords(article.get("keywords"))

    insert_sql = """
    INSERT OR IGNORE INTO articles (
        title, description, url, source, published_at, collected_at,
        category, priority, location, summary, reason,
        keywords, recommended_action, is_relevant
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """

    params = (
        title,
        article.get("description", ""),
        url,
        article.get("source", "Unknown"),
        article.get("published_at", ""),
        collected_at,
        article.get("category", "Other"),
        article.get("priority", "LOW"),
        article.get("location", "General"),
        article.get("summary", ""),
        article.get("reason", ""),
        keywords_str,
        article.get("recommended_action", ""),
        int(article.get("is_relevant", 0)),
    )

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(insert_sql, params)
        conn.commit()

        # If rowcount == 0, article was already present (duplicate URL ignored)
        if cursor.rowcount > 0:
            return cursor.lastrowid
        else:
            logger.debug("Article with URL '%s' already exists. Skipped duplicate.", url)
            return None


def insert_articles(
    articles: List[Dict[str, Any]],
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, int]:
    """Insert multiple articles in a single batch transaction.

    Args:
        articles: List of article dictionaries.
        db_path: Optional database path.

    Returns:
        Summary dict: {"inserted": count, "duplicates": count, "total": total}
    """
    target_path = get_db_path(db_path)
    inserted_count = 0
    duplicate_count = 0

    with get_db_connection(target_path) as conn:
        cursor = conn.cursor()
        insert_sql = """
        INSERT OR IGNORE INTO articles (
            title, description, url, source, published_at, collected_at,
            category, priority, location, summary, reason,
            keywords, recommended_action, is_relevant
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """

        for item in articles:
            url = item.get("url", "").strip()
            title = item.get("title", "").strip()
            if not url or not title:
                continue

            collected_at = item.get("collected_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            keywords_str = _prepare_keywords(item.get("keywords"))

            params = (
                title,
                item.get("description", ""),
                url,
                item.get("source", "Unknown"),
                item.get("published_at", ""),
                collected_at,
                item.get("category", "Other"),
                item.get("priority", "LOW"),
                item.get("location", "General"),
                item.get("summary", ""),
                item.get("reason", ""),
                keywords_str,
                item.get("recommended_action", ""),
                int(item.get("is_relevant", 0)),
            )

            cursor.execute(insert_sql, params)
            if cursor.rowcount > 0:
                inserted_count += 1
            else:
                duplicate_count += 1

        conn.commit()

    return {
        "inserted": inserted_count,
        "duplicates": duplicate_count,
        "total": len(articles),
    }


def get_region_condition(region: Optional[str]) -> Tuple[str, List[Any]]:
    """Generate SQL clause and parameters for regional filtering."""
    if not region or region.lower() == "all":
        return "", []
    r = region.strip().lower()
    if r == "chennai":
        return (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)",
            ["%chennai%", "%chennai%", "%chennai%", "%madhavaram%", "%tondiarpet%"],
        )
    elif r == "tamil_nadu":
        return (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)",
            [
                "%tamil nadu%", "%tamil nadu%", "%tamil nadu%",
                "%chennai%", "%coimbatore%", "%madurai%",
                "%salem%", "%tiruchirappalli%", "%tirunelveli%",
                "%dindigul%", "%thiruvallur%",
            ],
        )
    elif r == "india":
        return (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)",
            [
                "%india%", "%india%", "%the hindu%",
                "%times of india%", "%et infra%", "%indian express%",
                "%delhi%", "%mumbai%", "%bengaluru%",
                "%chennai%", "%tamil nadu%",
            ],
        )
    elif r == "global":
        return (
            "(LOWER(location) = ? OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(source) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)",
            ["global", "%bbc%", "%un news%", "%cornell%", "%uk%", "%wales%"],
        )
    return "", []


def get_articles(
    limit: int = 100,
    offset: int = 0,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    location: Optional[str] = None,
    region: Optional[str] = None,
    sort_by: str = "priority",
    is_relevant: Optional[int] = None,
    search: Optional[str] = None,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve articles from database matching optional search filters.

    Args:
        limit: Max number of records to return.
        offset: Offset for pagination.
        category: Filter by exact category.
        priority: Filter by priority (HIGH, MEDIUM, LOW).
        location: Filter by location substring.
        region: Filter by geographical region ('chennai', 'tamil_nadu', 'india', 'global').
        sort_by: Sort order ('priority' for High-first, 'newest' for latest date).
        is_relevant: Filter by relevance flag (1 or 0).
        search: Filter by substring in title, description, or summary.
        db_path: Optional custom database path.

    Returns:
        List of article dictionaries.
    """
    conditions: List[str] = []
    params: List[Any] = []

    if category and category.lower() != "all":
        conditions.append("category = ?")
        params.append(category)

    if priority and priority.upper() != "ALL":
        conditions.append("priority = ?")
        params.append(priority.upper())

    if location and location.lower() != "all":
        conditions.append("location LIKE ?")
        params.append(f"%{location}%")

    if region and region.lower() != "all":
        reg_sql, reg_params = get_region_condition(region)
        if reg_sql:
            conditions.append(reg_sql)
            params.extend(reg_params)

    if is_relevant is not None:
        conditions.append("is_relevant = ?")
        params.append(int(is_relevant))

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(title LIKE ? OR description LIKE ? OR summary LIKE ?)")
        params.extend([term, term, term])

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    if sort_by == "newest":
        order_by = "ORDER BY COALESCE(NULLIF(published_at, ''), NULLIF(collected_at, '')) DESC, id DESC"
    else:
        order_by = """
        ORDER BY
            CASE UPPER(priority)
                WHEN 'HIGH' THEN 1
                WHEN 'MEDIUM' THEN 2
                WHEN 'LOW' THEN 3
                ELSE 4
            END ASC,
            COALESCE(NULLIF(published_at, ''), NULLIF(collected_at, '')) DESC,
            id DESC
        """

    query = f"""
    SELECT * FROM articles
    {where_clause}
    {order_by}
    LIMIT ? OFFSET ?;
    """
    params.extend([limit, offset])

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_article_by_id(
    article_id: int,
    db_path: Optional[Union[str, Path]] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a single article by its primary key ID."""
    query = "SELECT * FROM articles WHERE id = ?;"
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (article_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_today_articles(
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve articles collected today (based on date part of created_at)."""
    query = """
    SELECT * FROM articles
    WHERE date(created_at) = date('now')
    ORDER BY id DESC;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_high_priority_articles(
    limit: int = 50,
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve all high-priority alerts."""
    query = """
    SELECT * FROM articles
    WHERE priority = 'HIGH'
    ORDER BY id DESC
    LIMIT ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_statistics(
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Calculate aggregated dashboard statistics from the database.

    Returns:
        Dictionary containing counts for total, today, priority levels,
        and category breakdowns.
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Total count
        cursor.execute("SELECT COUNT(*) FROM articles;")
        total_count = cursor.fetchone()[0]

        # 2. Today's count
        cursor.execute("SELECT COUNT(*) FROM articles WHERE date(created_at) = date('now');")
        today_count = cursor.fetchone()[0]

        # 3. Priority counts
        cursor.execute("""
            SELECT priority, COUNT(*) FROM articles
            GROUP BY priority;
        """)
        priority_rows = cursor.fetchall()
        priority_counts = {row[0]: row[1] for row in priority_rows if row[0]}

        # 4. Relevant count
        cursor.execute("SELECT COUNT(*) FROM articles WHERE is_relevant = 1;")
        relevant_count = cursor.fetchone()[0]

        # 5. Category breakdown
        cursor.execute("""
            SELECT category, COUNT(*) FROM articles
            GROUP BY category;
        """)
        category_rows = cursor.fetchall()
        category_counts = {row[0]: row[1] for row in category_rows if row[0]}

        # 6. Source breakdown
        cursor.execute("""
            SELECT source, COUNT(*) FROM articles
            GROUP BY source;
        """)
        source_rows = cursor.fetchall()
        source_counts = {row[0]: row[1] for row in source_rows if row[0]}

    return {
        "total_articles": total_count,
        "today_articles": today_count,
        "high_priority_count": priority_counts.get("HIGH", 0),
        "medium_priority_count": priority_counts.get("MEDIUM", 0),
        "low_priority_count": priority_counts.get("LOW", 0),
        "relevant_articles": relevant_count,
        "category_breakdown": category_counts,
        "source_breakdown": source_counts,
    }


def get_regional_statistics(
    db_path: Optional[Union[str, Path]] = None,
) -> Dict[str, int]:
    """Calculate counts of relevant articles across the 4 geographical categories.

    Categories:
        1. Chennai — Local Alerts
        2. Tamil Nadu — State Alerts
        3. India — National Alerts
        4. Other Relevant Global Alerts
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Chennai Local
        cursor.execute("""
            SELECT COUNT(*) FROM articles
            WHERE is_relevant = 1
              AND (LOWER(location) LIKE '%chennai%' OR LOWER(title) LIKE '%chennai%'
                   OR LOWER(source) LIKE '%chennai%' OR LOWER(location) LIKE '%madhavaram%'
                   OR LOWER(location) LIKE '%tondiarpet%');
        """)
        chennai_count = cursor.fetchone()[0]

        # Tamil Nadu State (all TN including Chennai)
        cursor.execute("""
            SELECT COUNT(*) FROM articles
            WHERE is_relevant = 1
              AND (LOWER(location) LIKE '%tamil nadu%' OR LOWER(title) LIKE '%tamil nadu%'
                   OR LOWER(source) LIKE '%tamil nadu%' OR LOWER(location) LIKE '%chennai%'
                   OR LOWER(location) LIKE '%coimbatore%' OR LOWER(location) LIKE '%madurai%'
                   OR LOWER(location) LIKE '%salem%' OR LOWER(location) LIKE '%tiruchirappalli%'
                   OR LOWER(location) LIKE '%tirunelveli%' OR LOWER(location) LIKE '%dindigul%'
                   OR LOWER(location) LIKE '%thiruvallur%');
        """)
        tn_count = cursor.fetchone()[0]

        # India National
        cursor.execute("""
            SELECT COUNT(*) FROM articles
            WHERE is_relevant = 1
              AND (LOWER(location) LIKE '%india%' OR LOWER(title) LIKE '%india%'
                   OR LOWER(source) LIKE '%the hindu%' OR LOWER(source) LIKE '%times of india%'
                   OR LOWER(source) LIKE '%et infra%' OR LOWER(source) LIKE '%indian express%'
                   OR LOWER(location) LIKE '%delhi%' OR LOWER(location) LIKE '%mumbai%'
                   OR LOWER(location) LIKE '%bengaluru%' OR LOWER(location) LIKE '%chennai%'
                   OR LOWER(location) LIKE '%tamil nadu%');
        """)
        india_count = cursor.fetchone()[0]

        # Global
        cursor.execute("""
            SELECT COUNT(*) FROM articles
            WHERE is_relevant = 1
              AND (LOWER(location) = 'global' OR LOWER(source) LIKE '%bbc%'
                   OR LOWER(source) LIKE '%un news%' OR LOWER(source) LIKE '%cornell%'
                   OR LOWER(location) LIKE '%uk%' OR LOWER(location) LIKE '%wales%');
        """)
        global_count = cursor.fetchone()[0]

    return {
        "chennai": chennai_count,
        "tamil_nadu": tn_count,
        "india": india_count,
        "global": global_count,
    }


def get_all_article_signatures(
    db_path: Optional[Union[str, Path]] = None,
) -> List[Dict[str, str]]:
    """Retrieve lightweight signatures (url, title, source) of all stored articles.

    Used by the deduplication processor for fast in-memory matching.
    """
    query = "SELECT url, title, source FROM articles;"
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def update_article_relevance(
    article_id: int,
    is_relevant: Union[bool, int],
    reason: str,
    db_path: Optional[Union[str, Path]] = None,
) -> bool:
    """Update the is_relevant flag and reason for a specific article ID.

    Preserves original title, description, url, source, and timestamps.
    """
    query = """
    UPDATE articles
    SET is_relevant = ?, reason = ?
    WHERE id = ?;
    """
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (1 if is_relevant else 0, reason, article_id))
        conn.commit()
        return cursor.rowcount > 0


if __name__ == "__main__":
    # Test script when executed directly
    print("Initializing EcoPulse SQLite database...")
    db_file = initialize_database()
    print(f"Database ready at: {db_file}")
    stats = get_statistics(db_file)
    print(f"Current database stats: {stats}")
