
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path

from ai.summarizer import _fallback_summary, _fallback_action

DB_PATH = Path("data/news.db")


def main():
    if not DB_PATH.exists():
        print("Database not found:", DB_PATH)
        return

    # Back up the database before making changes.
    backup_path = DB_PATH.with_name(
        "news_backup_before_summary_repair_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".db"
    )
    shutil.copy2(DB_PATH, backup_path)
    print("Backup created:", backup_path)

    conn = sqlite3.connect(DB_PATH)

    try:
        rows = conn.execute(
            """
            SELECT id, title, description
            FROM articles
            WHERE is_relevant = 1
              AND (summary IS NULL OR TRIM(summary) = '')
            ORDER BY id
            """
        ).fetchall()

        updated = 0
        title_only = 0

        for article_id, title, description in rows:
            title = title or ""
            description = description or ""

            summary = _fallback_summary(title, description)
            action = _fallback_action(title, description)

            # Do not save an empty summary.
            if not summary.strip():
                summary = (
                    "Summary unavailable because article details "
                    "are missing."
                )

            if not description.strip():
                title_only += 1

            conn.execute(
                """
                UPDATE articles
                SET summary = ?,
                    recommended_action = ?
                WHERE id = ?
                """,
                (summary, action, article_id),
            )
            updated += 1

        conn.commit()

        remaining = conn.execute(
            """
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1
              AND (summary IS NULL OR TRIM(summary) = '')
            """
        ).fetchone()[0]

        print("Articles repaired:", updated)
        print("Title-only or missing-description cases:", title_only)
        print("Relevant articles still missing summaries:", remaining)

        print("\nSample repaired summaries:")
        samples = conn.execute(
            """
            SELECT id, title, summary
            FROM articles
            WHERE is_relevant = 1
            ORDER BY id DESC
            LIMIT 5
            """
        ).fetchall()

        for row in samples:
            print("\nID:", row[0])
            print("Title:", row[1])
            print("Summary:", row[2])

    finally:
        conn.close()


if __name__ == "__main__":
    main()