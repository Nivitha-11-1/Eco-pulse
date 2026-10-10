import os
from dotenv import load_dotenv
from ai.classifier import get_classifier

load_dotenv()

print("==============================================")
print(" EcoPulse Phase 7 - AI Classification Test")
print("==============================================")

api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")

print("API key:", "PRESENT" if api_key else "MISSING")
print("Model:", os.getenv("GEMINI_MODEL", "gemini-3.8-flash"))

classifier = get_classifier()

title = "Heavy rainfall causes flooding and waterlogging in Chennai"

description = """
Heavy rainfall has caused flooding and waterlogging in several parts
of Chennai. Authorities have issued safety warnings and advised
residents to avoid low-lying areas.
"""

print("\nTesting article:")
print("Title:", title)

print("\nSending article to Gemini...")

result = classifier.classify(title, description)

print("\nClassification Result:")
print("Category :", result.get("category"))
print("Priority :", result.get("priority"))
print("Location :", result.get("location"))

if result.get("reason"):
    print("Reason   :", result.get("reason"))

print("\n==============================================")
print(" Test Completed")
print("==============================================")