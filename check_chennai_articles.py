import sqlite3

conn = sqlite3.connect("data/news.db")
cursor = conn.cursor()

query = """
SELECT id, title, source, is_relevant
FROM articles
WHERE title LIKE ?
   OR title LIKE ?
   OR title LIKE ?
   OR title LIKE ?
   OR title LIKE ?
ORDER BY id DESC
"""

patterns = (
    "%Chennai%",
    "%rain%",
    "%flood%",
    "%waterlog%",
    "%water%"
)

rows = cursor.execute(query, patterns).fetchall()

print("Matching articles:", len(rows))
print()

for row in rows:
    print("ID:", row[0])
    print("TITLE:", row[1])
    print("SOURCE:", row[2])
    print("RELEVANT:", row[3])
    print("-" * 60)

conn.close()
