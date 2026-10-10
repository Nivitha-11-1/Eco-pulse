
import re
import shutil
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "news.db"


# Categories are checked in order.
# Specific topics come before general climate topics.
RULES = [
    (
        "Campus Sustainability",
        [r"\bcampus\b", r"\bcollege\b", r"\buniversity\b", r"\bschool\b"],
        [
            r"\bsustainab\w*\b",
            r"\brecycl\w*\b",
            r"\bsolar energy\b",
            r"\brenewable energy\b",
            r"\bgreen campus\b",
            r"\btree planting\b",
            r"\bplastic-free\b",
            r"\benergy conservation\b",
            r"\bwater conservation\b",
            r"\bcompost\w*\b",
        ],
    ),
    (
        "Public Safety",
        [],
        [
            r"\bemergency alert\b",
            r"\bevacuati\w*\b",
            r"\brescue operation\b",
            r"\bsafety warning\b",
            r"\bpublic safety\b",
            r"\bbuilding collapse\b",
            r"\broad collapse\b",
            r"\bsinkhole\b",
            r"\bdisaster warning\b",
            r"\bchemical leak\b",
            r"\bunsafe drinking water\b",
            r"\bfire alert\b",
            r"\bpeople with breathing difficulties\b",
        ],
    ),
    (
        "Water & Pollution",
        [],
        [
            r"\bwater pollution\b",
            r"\bair pollution\b",
            r"\bair quality\b",
            r"\bwater quality\b",
            r"\bwater contamination\b",
            r"\bcontaminated water\b",
            r"\bsewage\b",
            r"\bsewer\b",
            r"\bgroundwater\b",
            r"\bdrinking water\b",
            r"\bwater shortage\b",
            r"\bwater supply\b",
            r"\bwater conservation\b",
            r"\bwater crisis\b",
            r"\bwater treatment\b",
            r"\btoxic pollution\b",
            r"\bpollution limits?\b",
            r"\bdesalination\b",
            r"\bfreshwater reserves?\b",
            r"\bwater reservoir(?:s)?\b",
        ],
    ),
    (
        "Waste Management",
        [],
        [
            r"\bwaste management\b",
            r"\bsolid waste\b",
            r"\bgarbage collection\b",
            r"\brecycling\b",
            r"\brecycle\b",
            r"\bplastic waste\b",
            r"\bplastic pollution\b",
            r"\bcomposting\b",
            r"\blandfill\b",
            r"\bgarbage dump\b",
            r"\bwaste disposal\b",
            r"\blitter\b",
            r"\bwaste segregation\b",
        ],
    ),
    (
        "Energy",
        [],
        [
            r"\bsolar energy\b",
            r"\brenewable energy\b",
            r"\bwind energy\b",
            r"\bpower outage\b",
            r"\belectricity supply\b",
            r"\benergy conservation\b",
            r"\bclean energy\b",
            r"\bsolar power\b",
            r"\bwind energy capacity\b",
            r"\bnet[- ]zero\b",
        ],
    ),
    (
        "Public Transport",
        [],
        [
            r"\bpublic transport\b",
            r"\bmetro service\b",
            r"\bbus service\b",
            r"\btrain service\b",
            r"\btraffic disruption\b",
            r"\btraffic diversion\b",
            r"\btransport disruption\b",
            r"\broad closure\b",
            r"\btransport services?\b",
        ],
    ),
    (
        "Civic Announcement",
        [],
        [
            r"\bmunicipal announcement\b",
            r"\bcivic announcement\b",
            r"\bpublic notice\b",
            r"\bcivic notice\b",
            r"\bcorporation announces\b",
            r"\bmunicipality\b",
            r"\bgarbage collection schedule\b",
            r"\bwater supply schedule\b",
            r"\broad closure notice\b",
            r"\bpublic works\b",
            r"\bcivic body\b",
            r"\bmonsoon preparedness\b",
            r"\bdesilting\b",
        ],
    ),
    (
        "Environmental Alert",
        [],
        [
            r"\benvironmental damage\b",
            r"\benvironmental alert\b",
            r"\bdeforestation\b",
            r"\bwildlife conservation\b",
            r"\bbiodiversity\b",
            r"\bforest conservation\b",
            r"\bforest fire\b",
            r"\boil spill\b",
            r"\bcoastal erosion\b",
            r"\bprotected species\b",
            r"\bgrassland loss\b",
            r"\bheat deaths?\b",
            r"\bhabitat loss\b",
            r"\bspecies decline\b",
            r"\bcoral bleaching\b",
            r"\becologists?\b",
            r"\bwildlife population\b",
        ],
    ),
    (
        "Climate & Weather",
        [],
        [
            r"\bheavy rain(?:fall)?\b",
            r"\bcyclone\b",
            r"\bflood(?:s|ing|ed)?\b",
            r"\bwaterlogging\b",
            r"\bheatwaves?\b",
            r"\bdrought\b",
            r"\bmonsoon\b",
            r"\brainfall\b",
            r"\blandslide\b",
            r"\bweather warning\b",
            r"\bweather alert\b",
            r"\bextreme weather\b",
            r"\bstorm surge\b",
            r"\bel ni[nñ]o\b",
            r"\bclimate change\b",
            r"\bglobal warming\b",
            r"\brising temperatures?\b",
            r"\bsea level rise\b",
            r"\bglacier(?:s)?\b",
        ],
    ),
    (
        "Community Development",
        [],
        [
            r"\bcommunity environmental initiative\b",
            r"\bcommunity clean-up\b",
            r"\bcommunity cleanup\b",
            r"\burban greening\b",
            r"\bpublic green space\b",
            r"\bcommunity tree planting\b",
        ],
    ),
]


HIGH_PRIORITY = re.compile(
    r"\b(cyclone|flood|flooding|evacuation|emergency|"
    r"contamination|chemical leak|landslide|sinkhole|"
    r"forest fire|severe storm|disaster warning|"
    r"building collapse|road collapse|"
    r"breathing difficulties|heatwave)\b",
    re.IGNORECASE,
)


# Prevent known unrelated articles from being recovered.
EXCLUDE_PATTERNS = [
    r"\burban spider\b",
    r"\bwildlife photography exhibition\b",
    r"\bphotography exhibition\b",
    r"\baavin annex laboratory\b",
    r"\bshops in chennai have almost everything\b",
    r"\bdengue cases\b",
    r"\bcapacity building programme for wrd engineers\b",
]


def matches_any(patterns, text):
    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def classify_locally(title, description):
    text = f"{title or ''} {description or ''}"

    # Ignore known unrelated articles.
    if matches_any(EXCLUDE_PATTERNS, text):
        return None

    for category, required_context, topic_patterns in RULES:
        if required_context and not matches_any(
            required_context, text
        ):
            continue

        if matches_any(topic_patterns, text):
            priority = (
                "HIGH"
                if HIGH_PRIORITY.search(text)
                else "MEDIUM"
            )

            return {
                "category": category,
                "priority": priority,
                "reason": (
                    "Matched local topic keywords; manually "
                    "review the original article."
                ),
            }

    return None


def main():
    apply_changes = "--apply" in sys.argv

    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Check that this script is in your EcoPulse folder.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(articles)"
            ).fetchall()
        }

        required = {
            "id", "title", "description",
            "category", "is_relevant"
        }
        missing = required - columns

        if missing:
            print(
                "The database is missing expected columns:",
                ", ".join(sorted(missing)),
            )
            return

        rows = conn.execute("""
            SELECT id, title, description
            FROM articles
            WHERE COALESCE(is_relevant, 0) = 0
              AND (
                  category IS NULL
                  OR TRIM(category) = ''
                  OR LOWER(TRIM(category)) = 'other'
              )
            ORDER BY id
        """).fetchall()

        candidates = []

        for row in rows:
            result = classify_locally(
                row["title"], row["description"]
            )

            if result:
                candidates.append(
                    (row["id"], row["title"], result)
                )

        print(f"\nDatabase: {DB_PATH}")
        print(f"Articles checked: {len(rows)}")
        print(f"Possible matches: {len(candidates)}")

        counts = Counter(
            item[2]["category"] for item in candidates
        )

        for category, count in sorted(counts.items()):
            print(f"  {category}: {count}")

        print("\nPreview (up to 100 articles):")

        for article_id, title, result in candidates[:100]:
            print(
                f"  ID {article_id} | {result['category']} | "
                f"{result['priority']} | {title}"
            )

        # Without --apply, do not change the database.
        if not apply_changes:
            print("\nPREVIEW ONLY — the database was not changed.")
            print("Review the matches before applying recovery.")
            print("To apply: python recover_articles.py --apply")
            return

        if not candidates:
            print("\nNo matching articles found. No changes made.")
            return

        # Close the database before making the backup.
        conn.close()

        backup_path = DB_PATH.with_name(
            "news_backup_before_recovery_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        shutil.copy2(DB_PATH, backup_path)

        conn = sqlite3.connect(DB_PATH)
        updated = 0

        try:
            for article_id, title, result in candidates:
                assignments = [
                    "category = ?",
                    "priority = ?",
                    "is_relevant = 1",
                ]

                values = [
                    result["category"],
                    result["priority"],
                ]

                if "reason" in columns:
                    assignments.append("reason = ?")
                    values.append(result["reason"])

                if "recommended_action" in columns:
                    assignments.append("recommended_action = ?")
                    values.append(
                        "Read the original report and follow "
                        "relevant official guidance."
                    )

                values.append(article_id)

                cursor = conn.execute(
                    f"UPDATE articles SET {', '.join(assignments)} "
                    "WHERE id = ? AND COALESCE(is_relevant, 0) = 0",
                    values,
                )
                updated += cursor.rowcount

            conn.commit()

            print(
                f"\nRecovery complete. Articles updated: {updated}"
            )
            print(f"Database backup saved at:\n{backup_path}")

        except Exception:
            conn.rollback()
            print("\nRecovery failed. Changes were rolled back.")
            raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()