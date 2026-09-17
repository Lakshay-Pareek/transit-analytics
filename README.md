# TransitVoice — Public Transport Feedback and Service Analytics Platform

A full-stack platform that collects structured passenger feedback on public bus services, automatically classifies complaints using a custom NLP pipeline, and presents actionable operational insights to transit administrators through an analytics dashboard.

Built as a case study around the NYC MTA network, using real complaint data from the NYC 311 Open Data API.

---

## The Problem

Public transit agencies receive thousands of complaints every month through unstructured channels — hotlines, web forms, social media — with no systematic way to analyse them at scale. Administrators cannot easily answer questions like:

- Which routes are consistently underperforming, and why?
- Is Route M42 getting worse this month compared to last?
- What time of day do complaints peak on the Q58?
- Is the primary issue on the BX12 crowding, driver behaviour, or mechanical failure?

Without answers to these questions, resource allocation decisions are made on instinct rather than evidence.

---

## What This Project Does

TransitVoice is built around two workflows:

**For passengers:** A simple web form where commuters rate their journey across four dimensions — punctuality, driver conduct, cleanliness, and crowding — and optionally write a free-text comment. The comment is automatically classified into a complaint category and severity level on submission.

**For administrators:** A real-time analytics dashboard that aggregates all feedback into route-level performance metrics, trend indicators, deterioration alerts, complaint heatmaps, and category breakdowns — all rendered as interactive charts.

---

## How It Works

### Data Pipeline

On first startup, the platform runs a background ingestion job that:

1. Pulls transit-related complaint records from the NYC 311 Socrata Open Data API (~2,000 records)
2. Maps 311 complaint types to the platform's internal category taxonomy (Crowding, Delays, Cleanliness, etc.)
3. Generates synthetic feedback records with realistic rating distributions per route to simulate passenger survey data

All data is stored locally in an SQLite database that persists across restarts.

### Comment Classifier

The classifier is a rule-based NLP system built from a hand-curated keyword taxonomy. It does not require any external model, API call, or internet connection.

When a passenger submits a comment, the classifier:

1. Tokenizes and normalizes the input
2. Scans for regex pattern matches across seven complaint categories
3. Assigns a category based on a priority hierarchy (Safety outranks Driver Behaviour, which outranks Delays, etc.)
4. Determines severity (low / medium / high) based on the base severity of the matched category, escalated if multiple patterns fire simultaneously
5. Returns a confidence score scaled from match density

Example:

```
Input:   "The driver ran a red light and was screaming at passengers."
Output:  { category: "Driver Behaviour", severity: "high", confidence: 0.91 }
```

### Composite Scoring

Each route is assigned a composite performance score used for ranking:

```
composite = 0.4 × overall_rating + 0.6 × weighted_component_average

Component weights:
  Punctuality:  30%
  Driver:       30%
  Cleanliness:  20%
  Crowding:     20%
```

This deliberately weights service reliability and driver conduct more heavily than cosmetic factors, reflecting what most passengers care about most.

### Deterioration Detection

Every route is assessed on a rolling basis by comparing the average rating of the most recent 30 days against the prior 30-day window:

- **Warning** — rating has dropped by 0.25 or more
- **Critical** — rating has dropped by 0.5 or more

Routes flagged as critical appear highlighted in the admin dashboard.

---

## Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Backend API | FastAPI (Python 3.11+) | Async-capable, auto-generates OpenAPI docs, clean dependency injection |
| ORM + Database | SQLAlchemy 2.0 + SQLite | Zero-config relational storage, suitable for single-node deployment |
| Data Validation | Pydantic v2 | Runtime type checking on all API inputs and outputs |
| Data Ingestion | Python `requests` + Socrata API | Pulls real-world 311 complaints without requiring an API key |
| Frontend | HTML5, Vanilla CSS, Vanilla JavaScript | No build step required, runs anywhere |
| Charts | Chart.js | Lightweight, well-documented, no framework dependency |
| Dev Server | Uvicorn | ASGI server with hot-reload for development |

---

## Project Structure

```
Decimal/
├── backend/
│   ├── main.py                  # Application entry point, startup event, static file serving
│   ├── models.py                # SQLAlchemy ORM models (Route, Feedback)
│   ├── schemas.py               # Pydantic v2 request/response schemas
│   ├── database.py              # SQLite engine and session factory
│   ├── analytics_engine.py      # Core analytics: rankings, deterioration, heatmap, trends
│   ├── classifier.py            # Keyword-based NLP classifier
│   ├── data_ingestion.py        # 311 API pull + synthetic data generation
│   └── routers/
│       ├── routes.py            # Route management endpoints
│       ├── feedback.py          # Feedback submission and retrieval
│       ├── analytics.py         # All analytics endpoints
│       └── classify.py          # Standalone classification endpoint
├── frontend/
│   ├── index.html               # Passenger feedback portal
│   ├── admin.html               # Administrator analytics dashboard
│   ├── css/style.css            # Shared design system (dark theme)
│   └── js/
│       ├── passenger.js         # Feedback form logic
│       └── admin.js             # Chart rendering and dashboard logic
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or higher
- pip

### Setup

**1. Clone the repository**

```bash
git clone https://github.com/Lakshay-Pareek/transit-analytics.git
cd transit-analytics
```

**2. Create and activate a virtual environment**

```bash
python -m venv .venv
```

On Windows:
```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:
```bash
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Start the server**

```bash
uvicorn backend.main:app --reload --port 8000
```

The first run will take a few seconds longer as the database is seeded with routes and complaint data in the background. You will see log output confirming when ingestion completes.

**5. Open the application**

| URL | Description |
|---|---|
| http://localhost:8000 | Passenger feedback portal |
| http://localhost:8000/admin | Administrator analytics dashboard |
| http://localhost:8000/api/docs | Interactive Swagger API documentation |
| http://localhost:8000/api/redoc | ReDoc API documentation |

---

## API Reference

### Routes

```
GET  /routes/                    List all active routes (filter by borough with ?borough=)
GET  /routes/{id}                Get a specific route by ID
GET  /routes/{id}/summary        Full analytics summary for a route
POST /routes/                    Create a new route
```

### Feedback

```
POST /feedback/                  Submit passenger feedback (auto-classified on write)
GET  /feedback/?route_id=&category=  Query feedback with optional filters
```

### Analytics

```
GET /analytics/overview          Platform-wide KPIs (total feedback, avg rating, alert counts)
GET /analytics/rankings          All routes ranked by composite score, with trend indicators
GET /analytics/deterioration     Routes flagged for rating decline in the last 30 days
GET /analytics/trend?route_id=   Monthly average rating trend (omit route_id for global)
GET /analytics/time-heatmap/{id} Complaint intensity by hour-of-day and day-of-week
GET /analytics/categories/{id}   Category and severity breakdown for a specific route
GET /analytics/categories        Category breakdown across all routes
```

### Classifier

```
POST /classify/
Body: { "comment": "The bus was packed and 20 minutes late again." }
Response: { "category": "Delays", "severity": "medium", "confidence": 0.79 }
```

---

## Data Source

Real complaint data is sourced from the NYC 311 Open Data portal:

- **API endpoint**: `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Dataset**: 311 Service Requests from 2010 to Present
- **Portal**: https://catalog.data.gov/dataset/311-service-requests-from-2010-to-present
- No API key is required. The public endpoint is rate-limited to approximately 1,000 requests per day.

On first startup, the ingestion module filters this dataset for transit-related complaint types and maps them to the platform's internal taxonomy.

---

## Design Decisions

**Why SQLite?**
For a single-node deployment or local demo, SQLite is sufficient and removes the need to configure a database server. The project is structured so that switching to PostgreSQL requires only a one-line change to the connection URL in `database.py`.

**Why a rule-based classifier rather than a machine learning model?**
An ML model would require labelled training data, a model file to ship, and inference dependencies. A rule-based classifier is fully offline, has zero external dependencies, is deterministic and debuggable, and performs accurately on the narrow domain of transit complaints. The taxonomy can be extended by adding entries to the `TAXONOMY` list in `classifier.py`.

**Why Vanilla JS on the frontend?**
The frontend has no build step, no bundler, and no framework. Any developer can open the HTML files, read them, and understand them immediately. This is intentional — the complexity of the project lives in the backend analytics logic, not in the UI layer.

---

## License

MIT
