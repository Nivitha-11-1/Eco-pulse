import sqlite3

conn = sqlite3.connect("data/news.db")

cursor = conn.cursor()

cursor.execute(
    "DELETE FROM articles WHERE source = ?",
    ("EcoPulse Phase 8 Test",)
)

print("Deleted test articles:", cursor.rowcount)

conn.commit()
conn.close()
