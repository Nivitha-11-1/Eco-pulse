# EcoPulse – Automated Community News & Eco-Alert Aggregator

EcoPulse is an automated community information system that collects local environmental news, civic announcements, public alerts, and campus sustainability updates from RSS feeds and public sources.

---

## 📌 Project Overview
- **Project Name:** EcoPulse
- **Purpose:** Aggregate, clean, filter, and summarize local eco-alerts and civic announcements for students and community members.
- **Tech Stack:** Python 3, Flask, SQLite, feedparser, BeautifulSoup4, APScheduler, Google GenAI / LLM API.

---

## 📁 Project Structure

```text
EcoPulse/
│
├── app.py                      # Flask Application entry point (Upcoming Phase 9)
├── config.py                   # Central configuration & environment loader (Phase 1)
├── requirements.txt            # Project dependencies (Phase 1)
├── README.md                   # Project documentation & guide (Phase 1)
├── .env.example                # Environment variables template (Phase 1)
├── .gitignore                  # Git ignore rules for virtualenvs, db, secrets (Phase 1)
│
├── collectors/                 # RSS Feed Collectors
│   ├── __init__.py             # (Phase 1)
│   ├── rss_collector.py        # (Upcoming Phase 2)
│   └── source_config.py        # (Upcoming Phase 2)
│
├── processors/                 # Content Processing Pipeline
│   ├── __init__.py             # (Phase 1)
│   ├── cleaner.py              # HTML cleaning & normalization (Upcoming Phase 5)
│   ├── deduplicator.py         # URL & Title deduplication (Upcoming Phase 5)
│   └── relevance.py            # Keyword relevance filter (Upcoming Phase 6)
│
├── database/                   # SQLite Database Management
│   ├── __init__.py             # (Phase 1)
│   └── database.py             # Schema & CRUD operations (Upcoming Phase 3)
│
├── ai/                         # Modular AI Services
│   ├── __init__.py             # (Phase 1)
│   ├── classifier.py           # Priority & Category classifier (Upcoming Phase 7)
│   └── summarizer.py           # Concise summary & action generator (Upcoming Phase 8)
│
├── digest/                     # Digest Generation
│   ├── __init__.py             # (Phase 1)
│   └── daily_digest.py         # Grouped daily summaries (Upcoming Phase 11)
│
├── scheduler/                  # Background Automation
│   ├── __init__.py             # (Phase 1)
│   └── scheduler.py            # APScheduler automated workflow (Upcoming Phase 12)
│
├── templates/                  # Frontend HTML Templates (Upcoming Phase 9)
│   ├── base.html
│   ├── index.html
│   └── digest.html
│
├── static/                     # CSS & JavaScript Assets (Upcoming Phase 9 & 14)
│   ├── style.css
│   └── script.js
│
├── data/                       # Local SQLite storage
│   └── news.db                 # SQLite database (Upcoming Phase 3)
│
└── tests/                      # Automated Test Suite (Upcoming Phase 13)
    ├── __init__.py             # (Phase 1)
    ├── test_rss.py
    ├── test_database.py
    └── test_relevance.py
```

---

## 🛠️ Step-by-Step Setup Guide

### 1. Create and Activate Virtual Environment
Open PowerShell or your command prompt in the project root:

```powershell
# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment on Windows
.\venv\Scripts\Activate.ps1
```

*(If execution policy restricts PowerShell scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 2. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

Open `.env` and configure:
- `DEMO_MODE=true` for safe local offline development.
- `AI_API_KEY` with your API key when AI features are configured.

---

## 🚦 Implementation Roadmap
- [x] **Phase 1: Project Structure + Requirements** *(Current)*
- [ ] **Phase 2: RSS Collector**
- [ ] **Phase 3: SQLite Database**
- [ ] **Phase 4: RSS → Database Pipeline**
- [ ] **Phase 5: Cleaning + Duplicate Detection**
- [ ] **Phase 6: Relevance Filtering**
- [ ] **Phase 7: AI Classification**
- [ ] **Phase 8: AI Summaries**
- [ ] **Phase 9: Flask Dashboard**
- [ ] **Phase 10: Search and Filters**
- [ ] **Phase 11: Daily Digest**
- [ ] **Phase 12: Scheduler**
- [ ] **Phase 13: Testing**
- [ ] **Phase 14: Final UI Polish**
