"""EcoPulse - SQLite to PostgreSQL Database Migration Script.

Migrates all historical articles and classifications from local SQLite (data/news.db)
or data/seed_articles.json to a persistent shared PostgreSQL database (Neon, Supabase,
or Render PostgreSQL).

Usage:
    python migrate_sqlite_to_postgres.py --url "postgresql://user:pass@host/dbname?sslmode=require"
Or with environment variable:
    set DATABASE_URL=postgresql://...
    python migrate_sqlite_to_postgres.py
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("EcoPulse.Migrate")

BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "data" / "news.db"
SEED_JSON = BASE_DIR / "data" / "seed_articles.json"


def get_sqlite_articles():
    """Load articles from SQLite or seed_articles.json fallback."""
    if SQLITE_DB.exists():
        logger.info("Reading historical articles from SQLite database: %s", SQLITE_DB)
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM articles ORDER BY id ASC")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    elif SEED_JSON.exists():
        logger.info("Reading historical articles from JSON fallback: %s", SEED_JSON)
        with open(SEED_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        logger.error("No source data found at %s or %s", SQLITE_DB, SEED_JSON)
        return []


def create_postgres_schema(pg_conn):
    """Create articles table and indexes in PostgreSQL if they don't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS articles (
        id SERIAL PRIMARY KEY,
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
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_articles_url ON articles(url);",
        "CREATE INDEX IF NOT EXISTS idx_articles_priority ON articles(priority);",
        "CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);",
        "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_articles_is_relevant ON articles(is_relevant);",
    ]

    with pg_conn.cursor() as cur:
        cur.execute(create_table_sql)
        for idx in indexes:
            cur.execute(idx)
        pg_conn.commit()
    logger.info("PostgreSQL schema and indexes verified.")


def migrate_to_postgres(database_url: str):
    """Migrate articles to PostgreSQL target database."""
    try:
        import psycopg2
    except ImportError:
        logger.error(
            "psycopg2 is required for PostgreSQL migration. "
            "Please install it with: pip install psycopg2-binary"
        )
        return False

    articles = get_sqlite_articles()
    if not articles:
        logger.warning("No articles found to migrate.")
        return False

    logger.info("Connecting to target PostgreSQL database...")
    # Normalize postgres:// to postgresql:// for psycopg2
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    try:
        pg_conn = psycopg2.connect(database_url)
    except Exception as e:
        logger.error("Failed to connect to PostgreSQL: %s", e)
        return False

    try:
        create_postgres_schema(pg_conn)

        insert_sql = """
        INSERT INTO articles (
            title, description, url, source, published_at, collected_at,
            category, priority, location, summary, reason,
            keywords, recommended_action, is_relevant
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING;
        """

        inserted_count = 0
        duplicate_count = 0

        with pg_conn.cursor() as cur:
            for art in articles:
                url = (art.get("url") or "").strip()
                title = (art.get("title") or "").strip()
                if not url or not title:
                    continue

                keywords_val = art.get("keywords")
                if isinstance(keywords_val, list):
                    keywords_str = json.dumps(keywords_val)
                else:
                    keywords_str = str(keywords_val or "")

                params = (
                    title,
                    art.get("description", ""),
                    url,
                    art.get("source", "Unknown"),
                    art.get("published_at", ""),
                    art.get("collected_at", ""),
                    art.get("category", "Other"),
                    art.get("priority", "LOW"),
                    art.get("location", "India"),
                    art.get("summary", ""),
                    art.get("reason", ""),
                    keywords_str,
                    art.get("recommended_action", ""),
                    int(art.get("is_relevant", 0)),
                )
                cur.execute(insert_sql, params)
                if cur.rowcount > 0:
                    inserted_count += 1
                else:
                    duplicate_count += 1

            pg_conn.commit()

        logger.info(
            "Migration completed: %d new articles inserted, %d duplicates skipped out of %d total.",
            inserted_count,
            duplicate_count,
            len(articles),
        )
        return True
    finally:
        pg_conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate EcoPulse database to PostgreSQL")
    parser.add_argument(
        "--url",
        default=os.getenv("DATABASE_URL", ""),
        help="Target PostgreSQL database URL",
    )
    args = parser.parse_args()

    db_url = args.url.strip()
    if not db_url:
        print("ERROR: DATABASE_URL not provided.")
        print("Pass --url or set the DATABASE_URL environment variable.")
        print("Example: python migrate_sqlite_to_postgres.py --url 'postgresql://user:pass@host/dbname'")
        sys.exit(1)

    success = migrate_to_postgres(db_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
