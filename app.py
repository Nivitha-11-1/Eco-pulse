
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Flask, render_template, request

from config import config


app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

DATABASE_PATH = Path(config.DATABASE_PATH)
IST = ZoneInfo("Asia/Kolkata")


def get_articles(category=None, priority=None, date_range="all"):
    """Fetch articles using category, priority, and date filters."""

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    query = """
        SELECT
            id,
            title,
            description,
            url,
            source,
            published_at,
            category,
            priority,
            location,
            summary,
            recommended_action,
            is_relevant,
            reason
        FROM articles
        WHERE 1 = 1
    """

    parameters = []

    # Show relevant articles by default.
    # If a category is selected, filter by that category.
    if category:
        query += " AND LOWER(TRIM(category)) = LOWER(TRIM(?))"
        parameters.append(category)
    else:
        query += " AND is_relevant = 1"

    if priority:
        query += " AND UPPER(TRIM(priority)) = UPPER(TRIM(?))"
        parameters.append(priority)

    # Use publication date, falling back to collection date.
    if date_range in ("today", "7days"):
        now = datetime.now(IST)

        if date_range == "today":
            start = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            start = (now - timedelta(days=6)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        # Store comparison boundaries in UTC because RSS dates
        # in this database are generally stored in UTC.
        start_utc = start.astimezone(ZoneInfo("UTC"))
        end_utc = now.astimezone(ZoneInfo("UTC"))

        date_expression = """
            COALESCE(
                NULLIF(published_at, ''),
                NULLIF(collected_at, '')
            )
        """

        query += f" AND {date_expression} >= ? AND {date_expression} <= ?"
        parameters.extend([
            start_utc.strftime("%Y-%m-%d %H:%M:%S"),
            end_utc.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    query += " ORDER BY id DESC"

    try:
        return conn.execute(query, parameters).fetchall()
    finally:
        conn.close()


def get_dashboard_stats():
    """Get counts of relevant articles by priority."""

    conn = sqlite3.connect(DATABASE_PATH)

    try:
        total = conn.execute("""
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1
        """).fetchone()[0]

        high = conn.execute("""
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1 AND UPPER(priority) = 'HIGH'
        """).fetchone()[0]

        medium = conn.execute("""
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1 AND UPPER(priority) = 'MEDIUM'
        """).fetchone()[0]

        low = conn.execute("""
            SELECT COUNT(*)
            FROM articles
            WHERE is_relevant = 1 AND UPPER(priority) = 'LOW'
        """).fetchone()[0]

        return {
            "total": total,
            "high": high,
            "medium": medium,
            "low": low,
        }
    finally:
        conn.close()


@app.route("/")
def dashboard():
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    date_range = request.args.get("date_range", "all").strip().lower()

    if date_range not in ("today", "7days", "all"):
        date_range = "all"

    articles = get_articles(
        category=category or None,
        priority=priority or None,
        date_range=date_range,
    )

    stats = get_dashboard_stats()

    return render_template(
        "index.html",
        articles=articles,
        selected_category=category,
        selected_priority=priority,
        selected_date_range=date_range,
        categories=config.CATEGORIES,
        priorities=config.PRIORITIES,
        stats=stats,
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=config.PORT,
        debug=config.DEBUG,
    )