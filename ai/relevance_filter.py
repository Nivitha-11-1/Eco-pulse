
"""
EcoPulse - AI Relevance Filter

Checks whether an article is relevant to environmental,
climate, weather, civic, public transport, campus sustainability,
community development, and public safety topics.

Includes:
1. Quick keyword pre-filter (no API call)
2. Gemini AI provider
3. OpenAI provider
4. Mock heuristic provider for testing
"""

import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()


RELEVANCE_SYSTEM_PROMPT = """
You are the relevance filter for EcoPulse, a community news
and environmental alert aggregator.

Mark an article relevant when it concerns one or more of these areas:

1. Weather and disasters:
Heavy rain, rainfall, flooding, waterlogging, cyclones, storms,
heatwaves, drought, landslides, earthquakes, extreme weather,
disaster warnings, evacuations, rescue operations, and weather-related
public safety.

2. Water and pollution:
Water shortages, reservoirs, dams, lakes, rivers, drinking water,
water conservation, groundwater, air pollution, water pollution,
sewage, sanitation, and contamination.

3. Environment and climate:
Climate change, global warming, environmental damage, forests,
wildlife, biodiversity, conservation, coastal issues, sea-level rise,
renewable energy, solar energy, and carbon emissions.

4. Waste and sustainability:
Plastic waste, garbage, recycling, waste management, composting,
sustainable development, tree planting, and community environmental
initiatives.

5. Public transport and sustainable mobility:
Public bus services, new bus routes, metro rail, suburban trains,
public transport improvements, electric buses, sustainable mobility,
cycling lanes, pedestrian safety, and transport accessibility.
Ordinary transport stories should be relevant when they concern
public services, sustainability, safety, or community impact.

6. Campus sustainability:
Environmental initiatives at schools, colleges, and universities,
campus recycling, campus waste management, rainwater harvesting,
energy conservation, campus solar power, tree planting, and
sustainable campus projects.

7. Community development and civic services:
Community clean-up drives, public parks, local infrastructure
improvements, drainage, waste collection, street lighting,
public facilities, municipal projects, and civic improvements
that affect residents' quality of life or public safety.

8. Civic and community alerts:
Municipal announcements, environmental warnings, emergency notices,
public safety hazards, infrastructure problems, and transport
disruptions caused by weather, flooding, or environmental conditions.

Pay particular attention to Chennai, Tamil Nadu, and India-related
news and community initiatives.

An article is NOT relevant merely because it mentions a city or a
public figure. Ordinary entertainment, sports, unrelated politics,
general business news, and unrelated crime are not relevant unless
the story has a clear connection to the topics above.

Return only valid JSON in this format:
{
  "is_relevant": true,
  "reason": "Short explanation",
  "keywords": ["keyword1", "keyword2"]
}
"""


# ---------------------------------------------------------
# 1. QUICK KEYWORD PRE-FILTER
# ---------------------------------------------------------

def quick_relevance_check(title, description=""):
    """
    Check whether an article contains keywords related to
    environmental, civic, transport, campus, or community topics.

    This function makes NO API calls.

    True  = send article for further relevance checking
    False = skip the AI relevance check
    """

    text = f"{title or ''} {description or ''}".lower()

    keywords = [
        # Weather and disasters
        "rain", "rainfall", "flood", "flooding", "flooded",
        "waterlogging", "cyclone", "storm", "heatwave",
        "heat wave", "drought", "landslide", "earthquake",
        "extreme weather", "weather warning", "disaster warning",
        "heavy rainfall", "heavy rain", "evacuation",
        "weather alert", "safety warning", "emergency alert",

        # Water
        "water shortage", "water supply", "water conservation",
        "reservoir", "dam", "river", "lake", "drinking water",
        "groundwater", "water pollution", "water quality",
        "water level", "water crisis", "rainwater harvesting",
        "sewage", "sanitation", "drainage",

        # Environment and climate
        "climate", "global warming", "pollution", "air quality",
        "environment", "environmental", "forest", "wildlife",
        "biodiversity", "conservation", "sea level",
        "carbon emission", "renewable energy", "solar energy",
        "greenhouse gas", "emission", "ecosystem",

        # Waste and sustainability
        "waste", "recycling", "recycle", "plastic waste",
        "garbage", "solid waste", "compost", "sustainability",
        "sustainable", "green energy", "clean energy",
        "waste collection", "tree planting", "tree plantation",
        "clean-up drive", "cleanup drive", "cleanliness drive",

        # Public transport and sustainable mobility
        "public transport", "public transportation",
        "public transit", "bus service", "bus route",
        "bus services", "metro rail", "metro service",
        "suburban train", "suburban railway", "railway service",
        "transport service", "electric bus", "electric buses",
        "cycling lane", "cycle lane", "pedestrian safety",
        "traffic disruption", "traffic congestion",
        "transport accessibility", "sustainable mobility",

        # Campus sustainability
        "campus sustainability", "sustainable campus",
        "green campus", "college recycling", "school recycling",
        "university sustainability", "campus waste",
        "campus solar", "campus environment",
        "college environment", "school environment",
        "energy conservation", "campus initiative",

        # Community development and civic improvements
        "community development", "community project",
        "community cleanup", "community clean-up",
        "neighborhood cleanup", "neighbourhood cleanup",
        "public park", "parks development",
        "drainage improvement", "road repair",
        "civic infrastructure", "public facilities",
        "street lighting", "municipal project",
        "local infrastructure", "community initiative",
        "resident welfare", "public works",

        # Existing civic and public safety keywords
        "civic", "municipal", "public safety",
        "road flooded", "roads flooded",
        "school closed", "schools closed", "power outage",
        "emergency notice", "public warning",

        # India, Tamil Nadu & Chennai specific environmental & civic terms
        "ngt", "national green tribunal", "cpcb", "tnpcb", "pollution control board",
        "imd", "meteorological department", "weather warning", "red alert", "orange alert", "yellow alert",
        "ndma", "tnsdma", "disaster management",
        "chennai corporation", "greater chennai corporation", "gcc", "wrd",
        "water resources department", "pwd", "panchayat", "municipal corporation",
        "monsoon", "thunderstorm", "depression", "low pressure", "inundation",
        "sinkhole", "road cave", "road caves",
        "desilting", "canal", "stormwater drain", "storm water drain", "drain work",
        "water tank", "water contamination", "tanker water", "drinking water",
        "chembarambakkam", "poondi", "veeranam", "red hills reservoir",
        "cooum", "adyar river", "buckingham canal", "kosasthalaiyar",
        "c&d waste", "biomining", "perungudi", "kodungaiyur", "dumpyard", "landfill",
        "air quality index", "aqi", "smog", "toxic air", "pm2.5", "pm10",
        "mtc bus", "chennai metro", "cmrl",
        "green campus", "tree plantation", "sapling", "olive ridley", "mangrove",
        "wetland", "marshland", "pallikaranai", "reserve forest", "western ghats",
        "dengue", "vector-borne", "heat action plan", "heat advisory",
    ]

    return any(keyword in text for keyword in keywords)


# ---------------------------------------------------------
# 2. BASE AI PROVIDER INTERFACE
# ---------------------------------------------------------

class BaseAIProvider:
    """Base class for EcoPulse AI relevance providers.

    Subclasses can implement either check(title, description) or
    classify_relevance(title, description). BaseAIProvider ensures that
    calling either method works seamlessly across both interfaces.
    """

    def check(self, title: str, description: str = "") -> dict:
        """Evaluate article relevance. Delegates to classify_relevance if implemented."""
        subclass_classify = getattr(self.__class__, "classify_relevance", None)
        if subclass_classify is not None and subclass_classify is not BaseAIProvider.classify_relevance:
            return self.classify_relevance(title=title, description=description)
        raise NotImplementedError("Provider must implement check() or classify_relevance()")

    def classify_relevance(self, title: str, description: str = "") -> dict:
        """Evaluate article relevance (alias for check)."""
        subclass_check = getattr(self.__class__, "check", None)
        if subclass_check is not None and subclass_check is not BaseAIProvider.check:
            return self.check(title=title, description=description)
        raise NotImplementedError("Provider must implement check() or classify_relevance()")


# ---------------------------------------------------------
# 3. GEMINI AI PROVIDER
# ---------------------------------------------------------

class GeminiProvider(BaseAIProvider):
    """Uses Google's Gemini API to check article relevance."""

    def __init__(self, api_key=None, model=None):
        self.api_key = (
            api_key
            or os.getenv("AI_API_KEY")
            or os.getenv("GEMINI_API_KEY")
        )
        self.model = (
            model
            or os.getenv("GEMINI_MODEL")
            or "gemini-3.5-flash"
        )

    def check(self, title, description=""):
        if not self.api_key:
            return {
                "is_relevant": False,
                "reason": "Gemini API key is not configured.",
                "keywords": [],
            }

        url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            f"models/{self.model}:generateContent"
        )

        prompt = f"""
{RELEVANCE_SYSTEM_PROMPT}

ARTICLE TITLE:
{title}

ARTICLE DESCRIPTION:
{description}

Determine whether this article is relevant to EcoPulse.
Return only the JSON object.
"""

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        try:
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=25,
            )

            if response.status_code == 429:
                return {
                    "is_relevant": False,
                    "reason": "Gemini quota exceeded; retry later.",
                    "keywords": [],
                }

            if response.status_code >= 400:
                return {
                    "is_relevant": False,
                    "reason": (
                        f"Gemini API error {response.status_code}: "
                        f"{response.text[:300]}"
                    ),
                    "keywords": [],
                }

            data = response.json()
            candidates = data.get("candidates", [])

            if not candidates:
                return {
                    "is_relevant": False,
                    "reason": "Gemini returned no response.",
                    "keywords": [],
                }

            response_text = (
                candidates[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )

            result = json.loads(response_text)

            return {
                "is_relevant": bool(
                    result.get("is_relevant", False)
                ),
                "reason": str(result.get("reason", "")),
                "keywords": result.get("keywords", []),
            }

        except requests.Timeout:
            return {
                "is_relevant": False,
                "reason": "AI service network error: request timed out.",
                "keywords": [],
            }

        except requests.RequestException as exc:
            return {
                "is_relevant": False,
                "reason": f"AI service network error: {exc}",
                "keywords": [],
            }

        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return {
                "is_relevant": False,
                "reason": f"Could not parse Gemini response: {exc}",
                "keywords": [],
            }


# ---------------------------------------------------------
# 4. OPENAI PROVIDER
# ---------------------------------------------------------

class OpenAIProvider(BaseAIProvider):
    """Uses the OpenAI API to check article relevance."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv(
            "OPENAI_MODEL", "gpt-4o-mini"
        )

    def check(self, title, description=""):
        if not self.api_key:
            return {
                "is_relevant": False,
                "reason": "OpenAI API key is not configured.",
                "keywords": [],
            }

        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": RELEVANCE_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": (
                                f"Title: {title}\n"
                                f"Description: {description}\n"
                                "Return only the requested JSON."
                            ),
                        },
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
                timeout=25,
            )

            if response.status_code >= 400:
                return {
                    "is_relevant": False,
                    "reason": (
                        f"OpenAI API error {response.status_code}: "
                        f"{response.text[:300]}"
                    ),
                    "keywords": [],
                }

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            result = json.loads(content)

            return {
                "is_relevant": bool(
                    result.get("is_relevant", False)
                ),
                "reason": str(result.get("reason", "")),
                "keywords": result.get("keywords", []),
            }

        except requests.RequestException as exc:
            return {
                "is_relevant": False,
                "reason": f"OpenAI network error: {exc}",
                "keywords": [],
            }

        except (ValueError, KeyError, IndexError, TypeError) as exc:
            return {
                "is_relevant": False,
                "reason": f"Could not parse OpenAI response: {exc}",
                "keywords": [],
            }


# ---------------------------------------------------------
# 5. MOCK PROVIDER FOR TESTS
# ---------------------------------------------------------

class MockHeuristicProvider(BaseAIProvider):
    """Keyword-based provider for testing without API calls."""

    def __init__(self):
        self.relevant_keywords = [
            "environment", "environmental", "climate", "weather",
            "rain", "rainfall", "flood", "flooding", "flooded",
            "waterlogging", "cyclone", "storm", "heatwave",
            "drought", "pollution", "air quality", "water",
            "waste", "recycling", "recycle", "compost", "solar",
            "energy", "wildlife", "tiger", "cheetah", "elephant",
            "forest", "sustainability", "green", "carbon",
            "emission", "transport", "civic", "campus",
            "reservoir", "landslide", "evacuation", "sewage",
            "public transit", "bus service", "bus route",
            "metro rail", "electric bus", "cycling lane",
            "pedestrian safety", "campus waste", "green campus",
            "college recycling", "school recycling",
            "rainwater harvesting", "tree planting",
            "community development", "community project",
            "community cleanup", "public park",
            "drainage improvement", "civic infrastructure",
            "street lighting", "waste collection",
            "ngt", "national green tribunal", "cpcb", "tnpcb",
            "imd", "chennai corporation", "gcc", "desilting",
            "canal", "stormwater", "drain work", "c&d waste",
            "aqi", "smog", "biomining", "waterlogging",
        ]

        self.irrelevant_keywords = [
            "movie", "cinema", "trailer", "actor", "actress",
            "film", "celebrity", "cricket", "football", "match",
            "tournament", "box office",
        ]

    def check(self, title, description=""):
        text = f"{title or ''} {description or ''}".lower()

        for keyword in self.irrelevant_keywords:
            if keyword in text:
                return {
                    "is_relevant": False,
                    "reason": (
                        "Article is entertainment/sports related "
                        f"('{keyword}')."
                    ),
                    "keywords": [keyword],
                }

        matches = [
            keyword
            for keyword in self.relevant_keywords
            if re.search(
                r"\b" + re.escape(keyword) + r"\b", text
            )
        ]

        if matches:
            return {
                "is_relevant": True,
                "reason": (
                    "Article relates to environmental, transport, "
                    "campus, or civic themes: "
                    + ", ".join(matches[:5])
                    + "."
                ),
                "keywords": matches[:10],
            }

        return {
            "is_relevant": False,
            "reason": (
                "No strong environmental, climate, transport, "
                "campus, or civic topics detected."
            ),
            "keywords": [],
        }


# ---------------------------------------------------------
# 6. PROVIDER SELECTION
# ---------------------------------------------------------

def get_ai_provider(provider=None):
    """
    Return the requested provider.

    provider may be:
    - an already-created provider object
    - 'mock'
    - 'gemini'
    - 'openai'
    """

    if provider is not None and not isinstance(provider, str):
        return provider

    provider_name = (
        provider or os.getenv("AI_PROVIDER", "gemini")
    ).strip().lower()

    if provider_name == "mock":
        return MockHeuristicProvider()

    if provider_name == "openai":
        return OpenAIProvider()

    return GeminiProvider()


# ---------------------------------------------------------
# 7. PUBLIC RELEVANCE CHECK FUNCTIONS
# ---------------------------------------------------------

def check_relevance(title, description="", provider=None):
    """Check relevance using the selected AI or mock provider.
    
    Compatible with providers exposing either check(title, description)
    or classify_relevance(title, description).
    """

    selected_provider = get_ai_provider(provider)

    try:
        call_fn = None
        # Handle mocks/MagicMocks where attributes are dynamically generated
        if hasattr(selected_provider, "_mock_return_value") or hasattr(selected_provider, "_mock_side_effect"):
            if "classify_relevance" in getattr(selected_provider, "__dict__", {}):
                call_fn = selected_provider.classify_relevance
            elif "check" in getattr(selected_provider, "__dict__", {}):
                call_fn = selected_provider.check
            elif hasattr(selected_provider, "classify_relevance"):
                call_fn = selected_provider.classify_relevance
            else:
                call_fn = selected_provider.check
        elif hasattr(selected_provider, "classify_relevance") and not hasattr(selected_provider, "check"):
            call_fn = selected_provider.classify_relevance
        elif hasattr(selected_provider, "check") and not hasattr(selected_provider, "classify_relevance"):
            call_fn = selected_provider.check
        elif hasattr(selected_provider, "classify_relevance") and hasattr(selected_provider, "check"):
            subclass_classify = getattr(selected_provider.__class__, "classify_relevance", None)
            if subclass_classify is not None and subclass_classify is not BaseAIProvider.classify_relevance:
                call_fn = selected_provider.classify_relevance
            else:
                call_fn = selected_provider.check
        else:
            raise TypeError("Provider has neither check() nor classify_relevance() method.")

        result = call_fn(
            title=title,
            description=description,
        )

        if not isinstance(result, dict):
            raise TypeError("Provider must return a dictionary.")

        result.setdefault("is_relevant", False)
        result.setdefault("reason", "")
        result.setdefault("keywords", [])

        return result

    except Exception as exc:
        return {
            "is_relevant": False,
            "reason": f"Relevance check failed: {exc}",
            "keywords": [],
        }


def classify_relevance(title, description="", provider=None):
    """Alias for check_relevance to support both function naming styles."""
    return check_relevance(
        title=title,
        description=description,
        provider=provider,
    )


def is_relevant(title, description="", provider=None):
    """Return only the relevance boolean."""

    result = check_relevance(
        title=title,
        description=description,
        provider=provider,
    )

    return bool(result["is_relevant"])