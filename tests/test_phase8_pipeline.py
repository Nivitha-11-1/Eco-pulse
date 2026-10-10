import sqlite3
from datetime import datetime

from ai.summarizer import get_summarizer
from database.database import insert_articles


print("=" * 60)
print("PHASE 8 INTEGRATION TEST")
print("=" * 60)


# ---------------------------------------------------------
# 1. Create one test article
# ---------------------------------------------------------

timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

article = {
    "title": "Heavy Rainfall Causes Waterlogging in Chennai",
    "description": (
        "Heavy rainfall has caused flooding and severe waterlogging "
        "in several parts of Chennai. Authorities have issued safety warnings."
    ),
    "url": f"https://ecopulse-test.local/phase8/{timestamp}",
    "source": "EcoPulse Phase 8 Test",
    "published_at": datetime.now().isoformat(),
    "category": "Climate & Weather",
    "priority": "HIGH",
    "location": "Chennai",
    "is_relevant": 1,
}


# ---------------------------------------------------------
# 2. Initialize summarizer
# ---------------------------------------------------------

print("\nInitializing Gemini summarizer...")

summarizer = get_summarizer()

if summarizer is None:
    print("[ERROR] Summarizer could not be initialized.")
    raise SystemExit(1)

print("[OK] Summarizer initialized.")


# ---------------------------------------------------------
# 3. Generate summary and recommended action
# ---------------------------------------------------------

print("\nGenerating AI summary and recommended action...")

result = summarizer.summarize(
    title=article["title"],
    description=article["description"],
)

print("\nAI Result:")
print("Summary :", result.get("summary", ""))
print("Action  :", result.get("recommended_action", ""))

if result.get("reason"):
    print("Reason  :", result["reason"])


# ---------------------------------------------------------
# 4. Save AI results into article
# ---------------------------------------------------------

article["summary"] = result.get("summary", "")
article["recommended_action"] = result.get(
    "recommended_action",
    "Stay informed and follow official updates."
)


# ---------------------------------------------------------
# 5. Insert into database
# ---------------------------------------------------------

print("\nSaving article to database...")

stats = insert_articles([article])

print("[OK] Database insertion completed.")
print("Inserted:", stats)


# ---------------------------------------------------------
# 6. Verify stored data
# ---------------------------------------------------------

print("\nChecking database...")

conn = sqlite3.connect("data/news.db")

cursor = conn.execute(
    """
    SELECT
        title,
        category,
        priority,
        location,
        summary,
        recommended_action
    FROM articles
    WHERE url = ?
    """,
    (article["url"],)
)

row = cursor.fetchone()

conn.close()


# ---------------------------------------------------------
# 7. Display verification
# ---------------------------------------------------------

if row:
    print("\n" + "=" * 60)
    print("DATABASE VERIFICATION")
    print("=" * 60)

    print("Title              :", row[0])
    print("Category           :", row[1])
    print("Priority           :", row[2])
    print("Location           :", row[3])
    print("Summary            :", row[4])
    print("Recommended Action :", row[5])

    print("\n" + "=" * 60)
    print("PHASE 8 TEST PASSED")
    print("=" * 60)

else:
    print("\n[ERROR] Article was not found in the database.")