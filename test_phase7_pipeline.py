import os
from dotenv import load_dotenv

from database.database import insert_article
from ai.classifier import get_classifier

load_dotenv()

print("===================================================")
print(" EcoPulse Phase 7 - Pipeline Classification Test")
print("===================================================")

# Create classifier
classifier = get_classifier()

# Test article
title = "Heavy rainfall causes flooding in Chennai"

description = """
Heavy rainfall has caused flooding and severe waterlogging
in several parts of Chennai. Authorities have issued safety
warnings and advised residents to avoid low-lying areas.
"""

print("\nTest Article:")
print("Title:", title)

print("\nSending article to Gemini for classification...")

# Classify article
result = classifier.classify(title, description)

print("\nGemini Classification:")
print("Category :", result.get("category"))
print("Priority :", result.get("priority"))
print("Location :", result.get("location"))

if result.get("reason"):
    print("Reason   :", result.get("reason"))

# Create test article
article = {
    "title": title,
    "description": description,
    "url": "https://ecopulse-test.local/phase7-test-chennai-20261008",
    "source": "EcoPulse Phase 7 Test",
    "published": "2026-10-08",
    "category": result.get("category", "Other"),
    "priority": result.get("priority", "LOW"),
    "location": result.get("location", "Unknown"),
}

print("\nSaving classified article to database...")

try:
    insert_article(article)
    print("[OK] Article inserted into database.")
except Exception as e:
    print("[ERROR] Could not insert article:", e)

print("\n===================================================")
print(" Phase 7 Test Completed")
print("===================================================")