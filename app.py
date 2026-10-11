"""
EcoPulse - Automated Community News & Eco-Alert Aggregator
Web Dashboard & API Application
"""

import math
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, abort, render_template, request

from collectors.source_config import RSS_SOURCES
from config import config
from database.database import initialize_database

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY

DATABASE_PATH = Path(config.DATABASE_PATH)
IST = ZoneInfo("Asia/Kolkata")

# Ensure database and articles table exist on app startup
try:
    initialize_database(DATABASE_PATH, auto_seed=True)
except Exception as e:
    app.logger.warning("Database init warning: %s", e)


def get_db_connection():
    """Create a sqlite3 connection with Row factory."""
    if not DATABASE_PATH.exists():
        initialize_database(DATABASE_PATH, auto_seed=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_region_clauses(region: str) -> tuple[str, list]:
    """Return SQL clause and parameters for geographical categorization."""
    if not region or region.lower() == "all":
        return "", []

    r = region.strip().lower()
    if r == "chennai":
        clause = (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)"
        )
        return clause, [
            "%chennai%", "%chennai%", "%chennai%", "%madhavaram%", "%tondiarpet%"
        ]
    elif r == "tamil_nadu":
        clause = (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)"
        )
        return clause, [
            "%tamil nadu%", "%tamil nadu%", "%tamil nadu%",
            "%chennai%", "%coimbatore%", "%madurai%",
            "%salem%", "%tiruchirappalli%", "%tirunelveli%",
            "%dindigul%", "%thiruvallur%",
        ]
    elif r == "india":
        clause = (
            "(LOWER(location) LIKE ? OR LOWER(title) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ? "
            "OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)"
        )
        return clause, [
            "%india%", "%india%", "%the hindu%",
            "%times of india%", "%et infra%", "%indian express%",
            "%delhi%", "%mumbai%", "%bengaluru%",
            "%chennai%", "%tamil nadu%",
        ]
    elif r == "global":
        clause = (
            "(LOWER(location) = ? OR LOWER(source) LIKE ? OR LOWER(source) LIKE ? "
            "OR LOWER(source) LIKE ? OR LOWER(location) LIKE ? OR LOWER(location) LIKE ?)"
        )
        return clause, [
            "global", "%bbc%", "%un news%", "%cornell%", "%uk%", "%wales%"
        ]
    return "", []


def build_filter_query(
    category=None,
    priority=None,
    date_range="all",
    search=None,
    region=None,
):
    """Construct SQL WHERE clause and parameters for article filtering."""
    clauses = ["1 = 1"]
    params = []

    if category:
        clauses.append("LOWER(TRIM(category)) = LOWER(TRIM(?))")
        params.append(category)
    else:
        clauses.append("is_relevant = 1")

    if priority:
        clauses.append("UPPER(TRIM(priority)) = UPPER(TRIM(?))")
        params.append(priority)

    if region and region.lower() != "all":
        reg_sql, reg_params = get_region_clauses(region)
        if reg_sql:
            clauses.append(reg_sql)
            params.extend(reg_params)

    if search:
        search_pattern = f"%{search.strip().lower()}%"
        clauses.append(
            "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR "
            "LOWER(summary) LIKE ? OR LOWER(location) LIKE ? OR "
            "LOWER(source) LIKE ?)"
        )
        params.extend([search_pattern] * 5)

    if date_range in ("today", "7days"):
        now = datetime.now(IST)
        if date_range == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start = (now - timedelta(days=6)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        start_utc = start.astimezone(ZoneInfo("UTC"))
        end_utc = now.astimezone(ZoneInfo("UTC"))

        date_expression = (
            "COALESCE(NULLIF(published_at, ''), NULLIF(collected_at, ''))"
        )
        clauses.append(f"{date_expression} >= ? AND {date_expression} <= ?")
        params.extend([
            start_utc.strftime("%Y-%m-%d %H:%M:%S"),
            end_utc.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    where_sql = " AND ".join(clauses)
    return where_sql, params


def get_articles(
    category=None,
    priority=None,
    date_range="all",
    search=None,
    region=None,
    sort_by="priority",
    limit=None,
    offset=0,
):
    """Fetch filtered articles from the database with regional & priority ordering."""
    try:
        where_sql, params = build_filter_query(
            category=category,
            priority=priority,
            date_range=date_range,
            search=search,
            region=region,
        )

        if sort_by == "newest":
            order_clause = (
                "ORDER BY COALESCE(NULLIF(published_at, ''), NULLIF(collected_at, '')) DESC, id DESC"
            )
        else:
            order_clause = """
                ORDER BY
                    CASE UPPER(priority)
                        WHEN 'HIGH' THEN 1
                        WHEN 'MEDIUM' THEN 2
                        WHEN 'LOW' THEN 3
                        ELSE 4
                    END ASC,
                    CASE
                        WHEN LOWER(location) LIKE '%chennai%' OR LOWER(title) LIKE '%chennai%' THEN 1
                        WHEN LOWER(location) LIKE '%tamil nadu%' OR LOWER(title) LIKE '%tamil nadu%' THEN 2
                        WHEN LOWER(location) LIKE '%india%' OR LOWER(source) LIKE '%hindu%' OR LOWER(source) LIKE '%times of india%' OR LOWER(source) LIKE '%indian express%' THEN 3
                        ELSE 4
                    END ASC,
                    COALESCE(NULLIF(published_at, ''), NULLIF(collected_at, '')) DESC,
                    id DESC
            """

        query = f"""
            SELECT
                id,
                title,
                description,
                url,
                source,
                published_at,
                collected_at,
                category,
                priority,
                location,
                summary,
                recommended_action,
                is_relevant,
                reason
            FROM articles
            WHERE {where_sql}
            {order_clause}
        """

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset)])

        conn = get_db_connection()
        try:
            return conn.execute(query, params).fetchall()
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Error in get_articles: %s", e)
        return []


def count_articles(
    category=None,
    priority=None,
    date_range="all",
    search=None,
    region=None,
):
    """Get count of filtered articles."""
    try:
        where_sql, params = build_filter_query(
            category=category,
            priority=priority,
            date_range=date_range,
            search=search,
            region=region,
        )

        query = f"SELECT COUNT(*) FROM articles WHERE {where_sql}"
        conn = get_db_connection()
        try:
            return conn.execute(query, params).fetchone()[0]
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Error in count_articles: %s", e)
        return 0


def get_regional_articles(region: str, limit: int = 8, sort_by: str = "priority"):
    """Fetch top articles dedicated to a specific region."""
    return get_articles(region=region, sort_by=sort_by, limit=limit)


def get_regional_counts():
    """Return counts for the 4 geographical categories."""
    return {
        "chennai": count_articles(region="chennai"),
        "tamil_nadu": count_articles(region="tamil_nadu"),
        "india": count_articles(region="india"),
        "global": count_articles(region="global"),
    }


def get_community_articles(limit=10):
    """Fetch genuine community, campus sustainability, civic and waste articles."""
    try:
        conn = get_db_connection()
        try:
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
                    recommended_action
                FROM articles
                WHERE is_relevant = 1
                  AND (
                      LOWER(category) IN (
                          'campus sustainability',
                          'community development',
                          'civic announcement',
                          'waste management'
                      )
                      OR LOWER(title) LIKE '%campus%'
                      OR LOWER(title) LIKE '%community%'
                      OR LOWER(title) LIKE '%campaign%'
                      OR LOWER(title) LIKE '%drive%'
                      OR LOWER(title) LIKE '%volunteer%'
                      OR LOWER(title) LIKE '%event%'
                  )
                ORDER BY id DESC
                LIMIT ?
            """
            return conn.execute(query, (limit,)).fetchall()
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Error in get_community_articles: %s", e)
        return []


def get_air_quality_articles(limit=6):
    """Fetch genuine air quality, pollution, and climate articles."""
    try:
        conn = get_db_connection()
        try:
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
                    recommended_action
                FROM articles
                WHERE is_relevant = 1
                  AND (
                      LOWER(category) = 'water & pollution'
                      OR LOWER(title) LIKE '%air%'
                      OR LOWER(title) LIKE '%pollution%'
                      OR LOWER(title) LIKE '%smog%'
                      OR LOWER(title) LIKE '%aqi%'
                      OR LOWER(summary) LIKE '%air%'
                  )
                ORDER BY id DESC
                LIMIT ?
            """
            return conn.execute(query, (limit,)).fetchall()
        finally:
            conn.close()
    except Exception as e:
        app.logger.error("Error in get_air_quality_articles: %s", e)
        return []


def get_dashboard_stats():
    """Get counts of relevant articles by priority."""
    try:
        conn = get_db_connection()
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
    except Exception as e:
        app.logger.error("Error in get_dashboard_stats: %s", e)
        return {
            "total": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
        }


@app.route("/")
def dashboard():
    """Home Dashboard: stats, highlights, carousels, and recent alerts."""
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    date_range = request.args.get("date_range", "all").strip().lower()
    search = request.args.get("search", "").strip()
    region = request.args.get("region", "all").strip().lower()
    sort_by = request.args.get("sort_by", "priority").strip().lower()

    if date_range not in ("today", "7days", "all"):
        date_range = "all"
    if sort_by not in ("priority", "newest"):
        sort_by = "priority"

    # Fetch filtered articles for main alerts section
    articles = get_articles(
        category=category or None,
        priority=priority or None,
        date_range=date_range,
        search=search or None,
        region=region if region != "all" else None,
        sort_by=sort_by,
        limit=60,
    )

    stats = get_dashboard_stats()
    regional_counts = get_regional_counts()
    chennai_alerts = get_regional_articles("chennai", limit=8, sort_by=sort_by)
    tn_alerts = get_regional_articles("tamil_nadu", limit=8, sort_by=sort_by)
    india_alerts = get_regional_articles("india", limit=8, sort_by=sort_by)
    global_alerts = get_regional_articles("global", limit=6, sort_by=sort_by)

    community_articles = get_community_articles(limit=10)
    air_quality_articles = get_air_quality_articles(limit=6)

    return render_template(
        "index.html",
        articles=articles,
        community_articles=community_articles,
        air_quality_articles=air_quality_articles,
        chennai_alerts=chennai_alerts,
        tn_alerts=tn_alerts,
        india_alerts=india_alerts,
        global_alerts=global_alerts,
        regional_counts=regional_counts,
        selected_category=category,
        selected_priority=priority,
        selected_date_range=date_range,
        selected_search=search,
        selected_region=region,
        selected_sort_by=sort_by,
        categories=config.CATEGORIES,
        priorities=config.PRIORITIES,
        regions=config.REGIONS,
        stats=stats,
    )


@app.route("/articles")
def articles_page():
    """Dedicated Articles page with search, filters, and pagination."""
    category = request.args.get("category", "").strip()
    priority = request.args.get("priority", "").strip()
    date_range = request.args.get("date_range", "all").strip().lower()
    search = request.args.get("search", "").strip()
    region = request.args.get("region", "all").strip().lower()
    sort_by = request.args.get("sort_by", "priority").strip().lower()

    if date_range not in ("today", "7days", "all"):
        date_range = "all"
    if sort_by not in ("priority", "newest"):
        sort_by = "priority"

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    per_page = 12
    total_count = count_articles(
        category=category or None,
        priority=priority or None,
        date_range=date_range,
        search=search or None,
        region=region if region != "all" else None,
    )

    total_pages = max(1, math.ceil(total_count / per_page))
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page
    articles = get_articles(
        category=category or None,
        priority=priority or None,
        date_range=date_range,
        search=search or None,
        region=region if region != "all" else None,
        sort_by=sort_by,
        limit=per_page,
        offset=offset,
    )

    # Calculate pagination range (e.g. 1 2 3 4 5)
    page_numbers = list(range(max(1, page - 2), min(total_pages + 1, page + 3)))

    return render_template(
        "articles.html",
        articles=articles,
        selected_category=category,
        selected_priority=priority,
        selected_date_range=date_range,
        selected_search=search,
        selected_region=region,
        selected_sort_by=sort_by,
        categories=config.CATEGORIES,
        priorities=config.PRIORITIES,
        regions=config.REGIONS,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        page_numbers=page_numbers,
    )


@app.route("/article/<int:article_id>")
def article_detail(article_id):
    """Article details view."""
    conn = get_db_connection()
    try:
        article = conn.execute(
            """
            SELECT * FROM articles WHERE id = ?
            """,
            (article_id,),
        ).fetchone()
        if not article:
            abort(404)
        return render_template("article_detail.html", article=article)
    finally:
        conn.close()


@app.route("/about")
def about_page():
    """About Page: Project purpose, pipeline, RSS feeds, tech stack, and limitations."""
    feeds = RSS_SOURCES
    stats = get_dashboard_stats()
    return render_template(
        "about.html",
        feeds=feeds,
        stats=stats,
    )


@app.route("/health")
def healthcheck():
    """Cloud health check endpoint."""
    return {
        "status": "healthy",
        "service": "EcoPulse",
        "timestamp": datetime.now(ZoneInfo("UTC")).isoformat(),
    }


@app.route("/api/pipeline/run", methods=["POST"])
def trigger_pipeline():
    """Secure webhook to trigger pipeline run from scheduled runner."""
    auth_header = request.headers.get("Authorization", "")
    secret = auth_header.replace("Bearer ", "").strip()
    expected_secret = os.getenv("PIPELINE_SECRET", config.SECRET_KEY)

    if not secret or secret != expected_secret:
        return {"status": "error", "message": "Unauthorized"}, 401

    try:
        from pipeline import run_pipeline
        stats = run_pipeline()
        return {"status": "success", "results": stats}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


@app.errorhandler(500)
def internal_server_error(e):
    import traceback
    app.logger.error("Unhandled Server Error: %s\n%s", e, traceback.format_exc())
    return render_template("500.html", error=str(e)), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", config.PORT))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(
        host=host,
        port=port,
        debug=config.DEBUG,
    )