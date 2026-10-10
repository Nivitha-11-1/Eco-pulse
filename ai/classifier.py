
import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger("EcoPulse.AIClassifier")


CATEGORIES = {
    "Environmental Alert",
    "Climate & Weather",
    "Waste Management",
    "Water & Pollution",
    "Public Transport",
    "Civic Announcement",
    "Public Safety",
    "Campus Sustainability",
    "Energy",
    "Community Development",
    "Other",
}

CLASSIFICATION_SYSTEM_PROMPT = """
You classify news for EcoPulse, a community news and eco-alert aggregator.

Choose exactly one category:
Environmental Alert, Climate & Weather, Waste Management,
Water & Pollution, Public Transport, Civic Announcement,
Public Safety, Campus Sustainability, Energy,
Community Development, Other.

Rules:
- Public Transport: public buses, bus routes, metro, public transit,
  suburban trains, transport services and transport disruptions.
- Campus Sustainability: environmental or sustainability projects
  specifically at schools, colleges or universities.
- Energy: solar power, renewable energy, electricity and energy policy.
- Waste Management: recycling, garbage collection, waste disposal.
- Water & Pollution: water supply, water conservation, air or water pollution.
- Climate & Weather: climate change, extreme weather and forecasts.
- Environmental Alert: urgent environmental threats and hazards.
- Community Development: sustainable development, community projects,
  responsible tourism and local environmental initiatives.
- Civic Announcement: government notices and civic service updates.
- Public Safety: accidents, crime and immediate public safety issues.
- Other: stories that do not fit the categories above.

HIGH priority: emergencies and serious hazards.
MEDIUM priority: significant public services or environmental developments.
LOW priority: general awareness, education and minor updates.

Return only JSON:
{"category":"category","priority":"HIGH, MEDIUM, or LOW",
 "location":"city, town, district, state, region, or Unknown"}
"""


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def local_classify(title: str, description: str) -> Dict[str, Any]:
    """Classify obvious topics locally when the AI service is unavailable."""
    text = f"{title or ''} {description or ''}".lower()
    text = re.sub(r"\s+", " ", text).strip()

    def has(pattern: str) -> bool:
        return bool(re.search(pattern, text, re.I))

    category = "Other"
    priority = "LOW"

    # Campus-specific environmental projects take priority over general topics.
    campus_context = has(
        r"\b(campus|college|university|school|students|student)\b"
    )
    campus_action = has(
        r"\b(sustainab\w*|recycl\w*|solar|renewable energy|"
        r"waste management|plastic-free|tree planting|water conservation|"
        r"green initiative|environmental project|eco[- ]club)\b"
    )

    # Match real transport-service stories, not every story mentioning a bus.
    transport_topic = has(
        r"\b(public transport|public transit|bus route|bus service|"
        r"electric buses|electric bus|metro rail|metro service|"
        r"suburban train|commuter rail|mass transit|"
        r"Chennai Metro|MTC bus|transport network|"
        r"transport service|transport disruption|"
        r"new bus|bus fleet|metro extension)\b"
    )

    if campus_context and campus_action:
        category = "Campus Sustainability"

    elif transport_topic:
        category = "Public Transport"
        if has(r"\b(accident|collision|crash|derailment|emergency)\b"):
            priority = "HIGH"
        elif has(r"\b(disruption|suspended|cancell?ed|delay|closure)\b"):
            priority = "MEDIUM"

    elif has(
        r"\b(cyclone|flood warning|heatwave|heat wave|"
        r"severe weather|environmental emergency|"
        r"toxic leak|chemical spill|wildfire)\b"
    ):
        category = "Environmental Alert"
        priority = "HIGH"

    elif has(
        r"\b(climate change|global warming|greenhouse gas|"
        r"carbon emissions|net[- ]zero|extreme weather|"
        r"climate crisis|climate goals)\b"
    ):
        category = "Climate & Weather"

    elif has(
        r"\b(solar|solar panel|solar tiles|renewable energy|"
        r"wind power|wind energy|clean energy|"
        r"energy storage|energy efficiency|electricity generation|"
        r"battery storage|green hydrogen)\b"
    ):
        category = "Energy"

    elif has(
        r"\b(recycling|recyclable|recycle|waste management|"
        r"waste disposal|garbage collection|landfill|"
        r"plastic waste|e-waste|sewage treatment|"
        r"illegal waste|waste segregation)\b"
    ):
        category = "Waste Management"

    elif has(
        r"\b(water pollution|air pollution|water contamination|"
        r"water conservation|water shortage|water supply|"
        r"groundwater|river pollution|contaminated water|"
        r"sewage pollution|piped water)\b"
    ):
        category = "Water & Pollution"

    elif has(
        r"\b(sustainable development goals|SDGs|"
        r"community development|community-led|"
        r"sustainable tourism|responsible tourism|"
        r"community project|local development|"
        r"environmental sustainability|biodiversity conservation|"
        r"habitat restoration|wildlife conservation|"
        r"tree planting|forest conservation)\b"
    ):
        category = "Community Development"

    elif has(
        r"\b(public notice|civic announcement|"
        r"municipal announcement|civic services|"
        r"government notice|public consultation)\b"
    ):
        category = "Civic Announcement"

    elif has(
        r"\b(fatal accident|serious accident|"
        r"public safety alert|building collapse|"
        r"emergency evacuation)\b"
    ):
        category = "Public Safety"
        priority = "HIGH"

    if category in {
        "Environmental Alert",
        "Climate & Weather",
        "Water & Pollution",
    } and has(r"\b(warning|emergency|severe|critical|dangerous)\b"):
        priority = "HIGH"

    elif category != "Other" and priority != "HIGH":
        priority = "MEDIUM"

    # Extract a location only when a known place is explicitly mentioned.
    location = "Unknown"
    known_places = [
        "Chennai", "Coimbatore", "Madurai", "Tiruchirappalli",
        "Salem", "Tirunelveli", "Thiruvallur", "Tamil Nadu",
        "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Kolkata",
        "Visakhapatnam", "India",
    ]

    for place in known_places:
        if re.search(r"\b" + re.escape(place) + r"\b", text, re.I):
            location = place
            break

    return {
        "category": category,
        "priority": priority,
        "location": location,
    }


class GeminiClassifier:
    def __init__(self, api_key: str, model: str = "gemini-3.8-flash"):
        self.api_key = api_key
        self.model = model
        self.endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

    def classify(self, title: str, description: str) -> Dict[str, Any]:
        fallback = local_classify(title, description)

        if not self.api_key:
            fallback["reason"] = "AI_API_KEY is not configured; local rules used."
            return fallback

        payload = {
            "contents": [{
                "parts": [
                    {"text": CLASSIFICATION_SYSTEM_PROMPT},
                    {"text": f"Title:\n{title}\n\nDescription:\n{description}"},
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        for attempt in range(3):
            try:
                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30,
                )

                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2 and response.status_code != 429:
                        time.sleep(2 * (attempt + 1))
                        continue
                    fallback["reason"] = (
                        f"Gemini returned HTTP {response.status_code}; "
                        "local rules used."
                    )
                    return fallback

                response.raise_for_status()
                data = response.json()
                candidates = data.get("candidates", [])

                if not candidates:
                    fallback["reason"] = "Empty Gemini response; local rules used."
                    return fallback

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts or not parts[0].get("text"):
                    fallback["reason"] = "Missing AI response; local rules used."
                    return fallback

                parsed = json.loads(_clean_json_text(parts[0]["text"]))
                category = parsed.get("category", "Other")
                priority = str(parsed.get("priority", "LOW")).upper()
                location = str(parsed.get("location") or "Unknown")

                if category not in CATEGORIES:
                    category = "Other"
                if priority not in {"HIGH", "MEDIUM", "LOW"}:
                    priority = "LOW"

                # Prefer a clear local match when Gemini says "Other".
                if category == "Other" and fallback["category"] != "Other":
                    fallback["reason"] = (
                        "Local topic rules improved the generic AI classification."
                    )
                    return fallback

                return {
                    "category": category,
                    "priority": priority,
                    "location": location,
                }

            except requests.exceptions.RequestException as exc:
                logger.warning("Gemini request failed: %s", type(exc).__name__)
                fallback["reason"] = "Gemini request failed; local rules used."
                return fallback

            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                logger.warning("Invalid Gemini response; using local rules.")
                fallback["reason"] = "Invalid Gemini response; local rules used."
                return fallback

        fallback["reason"] = "Classification failed; local rules used."
        return fallback


def get_classifier() -> GeminiClassifier:
    api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    return GeminiClassifier(api_key=api_key or "", model=model)