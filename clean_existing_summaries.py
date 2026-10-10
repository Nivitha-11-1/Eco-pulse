
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from ai.summarizer import _clean_article_text

DB_PATH = Path("data/news.db")


def clean_summary(text):
    text = _clean_article_text(text or "")

    # Remove weekday + date + optional time wherever it occurs.
    text = re.sub(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
        r"[a-z]*,?\s+"
        r"\d{1,2}/\d{1,2}/\d{4}"
        r"\s*(?:[-–|]\s*\d{1,2}:\d{2})?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove leftover standalone CMS tokens.
    text = re.sub(
        r"\blkh\d+\b",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Normalize whitespace and punctuation spacing.
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    backup_path = DB_PATH.with_name(
        "news_backup_before_cleaning_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".db"
    )
    shutil.copy2(DB_PATH, backup_path)
    print("Backup created:", backup_path)

    conn = sqlite3.connect(DB_PATH)

    try:
        rows = conn.execute(
            """
            SELECT id, summary
            FROM articles
            WHERE is_relevant = 1
              AND summary IS NOT NULL
              AND TRIM(summary) != ''
            """
        ).fetchall()

        updated = 0

        for article_id, old_summary in rows:
            new_summary = clean_summary(old_summary)

            if new_summary != old_summary:
                conn.execute(
                    "UPDATE articles SET summary = ? WHERE id = ?",
                    (new_summary, article_id),
                )
                updated += 1

        conn.commit()

        missing = conn.execute(
            """
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1
              AND (summary IS NULL OR TRIM(summary) = '')
            """
        ).fetchone()[0]

        print("Summaries cleaned:", updated)
        print("Relevant articles missing summaries:", missing)
        print("\nSample summaries:")

        samples = conn.execute(
            """
            SELECT id, title, summary
            FROM articles
            WHERE is_relevant = 1
            ORDER BY id DESC
            LIMIT 5
            """
        ).fetchall()

        for article_id, title, summary in samples:
            print("\nID:", article_id)
            print("Title:", title)
            print("Summary:", summary)

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()