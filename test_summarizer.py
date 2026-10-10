import os

from dotenv import load_dotenv

from ai.summarizer import get_summarizer


load_dotenv()


print("===================================================")
print(" EcoPulse Phase 8 - AI Summary Test")
print("===================================================")


api_key = (
    os.getenv("AI_API_KEY")
    or os.getenv("GEMINI_API_KEY")
)


print(
    "API key:",
    "PRESENT" if api_key else "MISSING"
)

print(
    "Model:",
    os.getenv(
        "GEMINI_MODEL",
        "gemini-3.8-flash"
    )
)


summarizer = get_summarizer()


title = "Heavy rainfall causes flooding in Chennai"


description = """
Heavy rainfall has caused flooding and severe
waterlogging in several parts of Chennai.
Authorities have issued safety warnings and
advised residents to avoid low-lying areas.
"""


print("\nTesting article:")
print("Title:", title)


print("\nSending article to Gemini...")


result = summarizer.summarize(
    title,
    description
)


print("\nAI Summary Result:")

print(
    "Summary :",
    result.get("summary")
)

print(
    "Action  :",
    result.get("recommended_action")
)


if result.get("reason"):
    print(
        "Reason  :",
        result.get("reason")
    )


print("\n===================================================")
print(" Test Completed")
print("===================================================")