
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
        r"\b(cyclone|flood warning|heatwave|heat wave|red alert|"
        r"orange alert|severe weather|environmental emergency|"
        r"inundation|toxic leak|chemical spill|wildfire|"
        r"building collapse|sinkhole|road cave)\b"
    ):
        category = "Environmental Alert"
        priority = "HIGH"

    elif has(
        r"\b(climate change|global warming|greenhouse gas|"
        r"carbon emissions|net[- ]zero|extreme weather|"
        r"climate crisis|climate goals|monsoon forecast|weather forecast)\b"
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
        r"\b(c&d waste|construction and demolition waste|biomining|"
        r"perungudi|kodungaiyur|dumpyard|recycling|recyclable|recycle|"
        r"waste management|waste disposal|garbage collection|landfill|"
        r"plastic waste|e-waste|sewage treatment|illegal waste|"
        r"waste segregation|solid waste)\b"
    ):
        category = "Waste Management"

    elif has(
        r"\b(water pollution|air pollution|water contamination|water tank|"
        r"drinking water|water shortage|water supply|reservoir|dam|"
        r"groundwater|river pollution|contaminated water|sewage pollution|"
        r"piped water|canal desilting|desilting|stormwater drain|storm water drain|"
        r"chembarambakkam|poondi|veeranam|cooum|buckingham canal)\b"
    ):
        category = "Water & Pollution"
        if has(r"\b(contamination|faeces|toxic|poison|severe shortage|crisis)\b"):
            priority = "HIGH"

    elif has(
        r"\b(sustainable development goals|SDGs|community development|"
        r"community-led|sustainable tourism|responsible tourism|"
        r"community project|local development|environmental sustainability|"
        r"biodiversity conservation|habitat restoration|wildlife conservation|"
        r"tree planting|forest conservation|cleanliness drive|clean-up drive)\b"
    ):
        category = "Community Development"

    elif has(
        r"\b(ngt|national green tribunal|chennai corporation|"
        r"greater chennai corporation|gcc|drain work|drainage work|"
        r"public notice|civic announcement|municipal announcement|"
        r"civic services|government notice|public consultation|"
        r"ward committee|corporation directs|civic body)\b"
    ):
        category = "Civic Announcement"

    elif has(
        r"\b(fatal accident|serious accident|public safety alert|"
        r"emergency evacuation|dengue outbreak|health advisory)\b"
    ):
        category = "Public Safety"
        priority = "HIGH"

    # Refine priorities based on urgency keywords
    if category in {
        "Environmental Alert",
        "Climate & Weather",
        "Water & Pollution",
        "Public Safety",
    } and has(r"\b(warning|emergency|severe|critical|dangerous|red alert|evacuat\w*|hazard)\b"):
        priority = "HIGH"
    elif category != "Other" and priority != "HIGH":
        priority = "MEDIUM"

    # Extract a location with Indian and Tamil Nadu granularity
    location = "India"
    tn_localities = [
        ("Madhavaram", "Chennai, Tamil Nadu"),
        ("Tondiarpet", "Chennai, Tamil Nadu"),
        ("Adyar", "Chennai, Tamil Nadu"),
        ("Velachery", "Chennai, Tamil Nadu"),
        ("Tambaram", "Chennai, Tamil Nadu"),
        ("Guindy", "Chennai, Tamil Nadu"),
        ("Perungudi", "Chennai, Tamil Nadu"),
        ("Kodungaiyur", "Chennai, Tamil Nadu"),
        ("Ennore", "Chennai, Tamil Nadu"),
        ("Chennai", "Chennai, Tamil Nadu"),
        ("Coimbatore", "Coimbatore, Tamil Nadu"),
        ("Madurai", "Madurai, Tamil Nadu"),
        ("Tiruchirappalli", "Tiruchirappalli, Tamil Nadu"),
        ("Trichy", "Tiruchirappalli, Tamil Nadu"),
        ("Salem", "Salem, Tamil Nadu"),
        ("Tirunelveli", "Tirunelveli, Tamil Nadu"),
        ("Thiruvallur", "Thiruvallur, Tamil Nadu"),
        ("Kanchipuram", "Kanchipuram, Tamil Nadu"),
        ("Dindigul", "Dindigul, Tamil Nadu"),
        ("Erode", "Erode, Tamil Nadu"),
        ("Vellore", "Vellore, Tamil Nadu"),
        ("Tamil Nadu", "Tamil Nadu"),
    ]
    other_places = [
        ("Delhi", "Delhi, India"),
        ("Mumbai", "Mumbai, India"),
        ("Bengaluru", "Bengaluru, India"),
        ("Bangalore", "Bengaluru, India"),
        ("Kolkata", "Kolkata, India"),
        ("Hyderabad", "Hyderabad, India"),
        ("Kerala", "Kerala, India"),
        ("India", "India"),
    ]

    matched_loc = False
    for loc_keyword, loc_display in tn_localities:
        if re.search(r"\b" + re.escape(loc_keyword) + r"\b", text, re.I):
            location = loc_display
            matched_loc = True
            break

    if not matched_loc:
        for loc_keyword, loc_display in other_places:
            if re.search(r"\b" + re.escape(loc_keyword) + r"\b", text, re.I):
                location = loc_display
                matched_loc = True
                break

    if not matched_loc:
        if has(r"\b(bbc|uk|united states|un news|europe|global|world|international)\b"):
            location = "Global"
        else:
            location = "India"

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