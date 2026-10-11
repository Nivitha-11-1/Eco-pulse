"""Configuration module for EcoPulse.

Loads settings from environment variables (.env file) and defines
centralized constants and configuration objects.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


class Config:
    """Application configuration parameters."""

    # Project Information
    APP_NAME = "EcoPulse"
    APP_SUBTITLE = "Automated Community News & Eco-Alert Aggregator"

    # Flask Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "ecopulse-default-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("PORT", 5000))

    # Database Configuration
    DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/news.db")
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

    # Geographical Alert Categories
    REGIONS = [
        {"id": "all", "label": "All Regions"},
        {"id": "chennai", "label": "Chennai — Local Alerts"},
        {"id": "tamil_nadu", "label": "Tamil Nadu — State Alerts"},
        {"id": "india", "label": "India — National Alerts"},
        {"id": "global", "label": "Other Relevant Global Alerts"},
    ]

    # Demo Mode Setting
    # When true, uses mock/sample articles when live external feeds are unavailable
    DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    # AI Configuration
    AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    AI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY", "")

    # Scheduler Settings
    DAILY_RUN_TIME = os.getenv("DAILY_RUN_TIME", "06:00")
    SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", 24))
    SCHEDULE_INTERVAL_MINUTES = int(os.getenv("SCHEDULE_INTERVAL_MINUTES", 30))

    # News Categories as required by the project specifications
    CATEGORIES = [
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
    ]

    # Priority Levels
    PRIORITIES = ["HIGH", "MEDIUM", "LOW"]

    # Keyword filters for candidate identification before AI classification
    INITIAL_KEYWORDS = [
        "environment",
        "pollution",
        "waste",
        "recycling",
        "water",
        "flood",
        "rain",
        "rainfall",
        "climate",
        "sustainability",
        "energy",
        "solar",
        "transport",
        "traffic",
        "civic",
        "community",
        "campus",
        "green",
        "public safety",
    ]


# Active configuration instance
config = Config()
