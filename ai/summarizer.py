
import json
import logging
import os
import re
import time
from html import unescape
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("EcoPulse.AISummarizer")

DEFAULT_ACTION = "Stay informed and follow official updates."

SUMMARY_SYSTEM_PROMPT = """
You are the AI summarization engine for EcoPulse, an automated
community news and eco-alert aggregator.

Produce a short, accurate summary and a practical recommended action.
Use only facts supported by the article. Do not invent information.
Keep the summary to 1-3 sentences.

Return ONLY valid JSON in this format:
{
  "summary": "short article summary",
  "recommended_action": "practical recommended action"
}
"""


def _clean_json_text(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*```$", "", text)

    return text.strip()


def _clean_article_text(text: str) -> str:
    """Remove HTML, CMS tokens, and leading date/time metadata."""
    text = unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Remove CMS tokens such as lkh9.
    text = re.sub(
        r"\blkh\d+\b",
        " ",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Remove leading weekday, date, and optional time.
    # Example: Thu, 04/30/2026 - 22:04
    text = re.sub(
        r"^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
        r"[a-z]*,?\s+)?"
        r"\d{1,2}/\d{1,2}/\d{4}"
        r"\s*(?:[-–|]\s*\d{1,2}:\d{2})?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return re.sub(r"\s+", " ", text).strip()


def _fallback_action(title: str, description: str) -> str:
    """Choose a cautious action based on article keywords."""
    text = f"{title} {description}".lower()

    emergency_terms = (
        "evacuation", "evacuate", "flood warning",
        "cyclone warning", "tsunami", "landslide warning",
        "earthquake", "fire alert", "gas leak",
        "emergency alert", "severe weather warning",
    )

    pollution_terms = (
        "pollution", "contamination", "contaminated",
        "toxic spill", "chemical spill", "unsafe water",
        "water quality",
    )

    waste_terms = (
        "waste", "garbage", "litter", "dumping",
        "recycling", "plastic pollution", "landfill",
    )

    transport_terms = (
        "bus route", "public transport", "metro service",
        "train service", "road closure", "traffic diversion",
        "transport service",
    )

    energy_terms = (
        "solar power", "solar energy", "renewable energy",
        "wind power", "energy efficiency", "electricity saving",
    )

    community_terms = (
        "community cleanup", "tree planting", "tree plantation",
        "community garden", "public park",
    )

    if any(term in text for term in emergency_terms):
        return (
            "Follow instructions from local authorities and "
            "check official safety updates."
        )

    if any(term in text for term in pollution_terms):
        return (
            "Follow official public-health guidance and report "
            "suspected pollution to the relevant local authority."
        )

    if any(term in text for term in waste_terms):
        return (
            "Dispose of waste responsibly and follow local waste "
            "collection and recycling guidance."
        )

    if any(term in text for term in transport_terms):
        return (
            "Check the transport operator's official updates "
            "before travelling."
        )

    if any(term in text for term in energy_terms):
        return (
            "Follow reliable energy guidance and consider practical "
            "ways to reduce unnecessary energy use."
        )

    if any(term in text for term in community_terms):
        return (
            "Check the official event or local-authority information "
            "before participating."
        )

    return DEFAULT_ACTION


def _fallback_summary(title: str, description: str) -> str:
    """Create a short summary from available article text."""
    title = _clean_article_text(title)
    description = _clean_article_text(description)

    if description:
        if title and description.lower() == title.lower():
            return title[:600]

        sentences = re.split(r"(?<=[.!?])\s+", description)
        sentences = [
            sentence.strip()
            for sentence in sentences
            if sentence.strip()
        ]

        summary = " ".join(sentences[:2]) if sentences else description

        if len(summary) > 600:
            shortened = summary[:597].rsplit(" ", 1)[0]
            summary = shortened + "..."

        return summary

    if title:
        return title[:600]

    return "A summary is unavailable because the article text is missing."


def _fallback_result(
    title: str,
    description: str,
    reason: str,
) -> Dict[str, Any]:
    return {
        "summary": _fallback_summary(title, description),
        "recommended_action": _fallback_action(title, description),
        "reason": reason,
    }


class GeminiSummarizer:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.8-flash",
    ):
        self.api_key = api_key
        self.model = model
        self.endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

    def summarize(
        self,
        title: str,
        description: str,
    ) -> Dict[str, Any]:
        if not self.api_key:
            return _fallback_result(
                title,
                description,
                "AI_API_KEY is not configured.",
            )

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        user_prompt = f"""
Title:
{title}

Description:
{description}
"""

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": SUMMARY_SYSTEM_PROMPT},
                        {"text": user_prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }

        max_attempts = 3
        retry_delays = [3, 6]

        for attempt in range(max_attempts):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=60,
                )

                if response.status_code == 429:
                    logger.warning(
                        "Gemini quota/rate limit reached; "
                        "using local summary fallback."
                    )
                    return _fallback_result(
                        title,
                        description,
                        "Gemini quota/rate limit exceeded; local fallback used.",
                    )

                if response.status_code == 503:
                    if attempt < max_attempts - 1:
                        time.sleep(retry_delays[attempt])
                        continue

                    return _fallback_result(
                        title,
                        description,
                        "Gemini temporarily unavailable; local fallback used.",
                    )

                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])

                if not candidates:
                    return _fallback_result(
                        title,
                        description,
                        "Empty Gemini response; local fallback used.",
                    )

                parts = candidates[0].get(
                    "content", {}
                ).get("parts", [])

                if not parts:
                    return _fallback_result(
                        title,
                        description,
                        "No Gemini text response; local fallback used.",
                    )

                raw_text = parts[0].get("text", "")
                parsed = json.loads(_clean_json_text(raw_text))

                summary = _clean_article_text(
                    parsed.get("summary", "")
                )
                recommended_action = _clean_article_text(
                    parsed.get("recommended_action", "")
                )

                if not summary:
                    summary = _fallback_summary(title, description)

                if not recommended_action:
                    recommended_action = _fallback_action(
                        title,
                        description,
                    )

                return {
                    "summary": summary,
                    "recommended_action": recommended_action,
                }

            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "Gemini request failed (%s); using local fallback.",
                    type(exc).__name__,
                )
                return _fallback_result(
                    title,
                    description,
                    "Gemini network/request error; local fallback used.",
                )

            except (
                json.JSONDecodeError,
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                logger.warning(
                    "Could not parse Gemini response (%s); "
                    "using local fallback.",
                    type(exc).__name__,
                )
                return _fallback_result(
                    title,
                    description,
                    "Invalid Gemini response; local fallback used.",
                )

        return _fallback_result(
            title,
            description,
            "Summarization failed; local fallback used.",
        )


def get_summarizer() -> GeminiSummarizer:
    api_key = (
        os.getenv("AI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
    )

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

    return GeminiSummarizer(
        api_key=api_key or "",
        model=model,
    )