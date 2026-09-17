# 🚌 TransitVoice — Public Transport Feedback & Service Analytics Platform

A full-stack commuter feedback and operations analytics system built for the NYC MTA case study.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11+, FastAPI, SQLAlchemy, SQLite |
| Frontend | HTML5, Vanilla CSS (dark theme), Vanilla JS, Chart.js |
| Data | NYC 311 Socrata Open Data API + synthetic generator |
| Analytics | Pure Python (statistics module) |
| AI Classifier | Keyword-based rule classifier (offline, zero setup) |
| Dev Server | Uvicorn |

## Project Structure

```
Decimal/
├── backend/
│   ├── main.py                  # FastAPI app + startup
│   ├── models.py                # SQLAlchemy ORM models
│   ├── schemas.py               # Pydantic v2 schemas
│   ├── database.py              # SQLite connection
│   ├── analytics_engine.py      # Route rankings, deterioration, heatmap
│   ├── classifier.py            # AI keyword classifier
│   ├── data_ingestion.py        # 311 API + synthetic data pipeline
│   └── routers/
│       ├── routes.py            # GET/POST /routes
│       ├── feedback.py          # GET/POST /feedback
│       ├── analytics.py         # /analytics/* endpoints
│       └── classify.py          # POST /classify
├── frontend/
│   ├── index.html               # Passenger feedback portal
│   ├── admin.html               # Admin analytics dashboard
│   ├── css/style.css            # Shared design system
│   └── js/
│       ├── passenger.js         # Feedback form logic
│       └── admin.js             # Charts & dashboard logic
├── transport.db                 # SQLite DB (auto-created on first run)
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Create virtual environment

```powershell
cd "c:\Users\hopes\OneDrive\Desktop\Decimal"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
pip install -r requirements.txt
```

### 3. Start the server

```powershell
uvicorn backend.main:app --reload --port 8000
```

On first startup the server will:
1. Create `transport.db` with all tables
2. Seed 22 NYC bus routes
3. Attempt to pull ~2000 records from the NYC 311 Socrata API
4. Generate ~120+ synthetic feedback records per route with realistic patterns

### 4. Open the app

| URL | Description |
|---|---|
| http://localhost:8000 | Passenger feedback portal |
| http://localhost:8000/admin | Admin analytics dashboard |
| http://localhost:8000/api/docs | Interactive Swagger API docs |
| http://localhost:8000/api/redoc | ReDoc API documentation |

---

## API Reference

### Routes
```
GET  /routes/                        → List all routes
GET  /routes/{id}                    → Route detail
GET  /routes/{id}/summary            → Full analytics summary
POST /routes/                        → Create new route
```

### Feedback
```
POST /feedback/                      → Submit passenger feedback (auto-classified)
GET  /feedback/?route_id=&category=  → Query feedback with filters
```

### Analytics
```
GET /analytics/overview              → Platform-wide KPIs
GET /analytics/rankings              → Route rankings by composite score
GET /analytics/deterioration         → Routes with declining ratings
GET /analytics/trend?route_id=       → Monthly rating trend
GET /analytics/time-heatmap/{id}     → Complaints by hour × day
GET /analytics/categories/{id}       → Category breakdown per route
GET /analytics/categories            → Global category breakdown
```

### AI Classifier
```
POST /classify/   {"comment": "Bus was always packed after 6 PM"}
→ {"category": "Crowding", "severity": "low", "confidence": 0.79}
```

---

## Example Output

```
Route M42 — 42nd Street Crosstown
Overall Rating:    2.7 / 5
Composite Score:   2.85
Top Issue:         Crowding
Second Issue:      Delays
Worst Period:      5 PM–8 PM (Evening Rush)
Complaints / month: 128
```

---

## Analytics Logic

### Composite Score
```
composite = 0.4 × overall + 0.6 × weighted_components
weights: punctuality=30%, driver=30%, cleanliness=20%, crowding=20%
```

### Deterioration Detection
Compares 30-day rolling average vs. previous 30 days:
- `critical` if rating drop > 0.5
- `warning`  if rating drop > 0.25

### AI Classifier Categories
| Category | Example |
|---|---|
| Crowding | "Bus is always packed after 6 PM" |
| Delays | "Waited 40 minutes, no bus showed up" |
| Cleanliness | "Dirty seats and trash on the floor" |
| Driver Behaviour | "Driver skipped the university stop" |
| Mechanical Issues | "AC broken in 90°F heat" |
| Safety | "Witnessed harassment, driver did nothing" |
| Service Issues | "Route cancelled without notice" |

---

## Data Source

NYC 311 Open Data (transit-related complaints):
- **API**: `https://data.cityofnewyork.us/resource/erm2-nwe9.json`
- **Portal**: https://catalog.data.gov/dataset/311-service-requests-from-2010-to-present
- No API key required for public access (rate-limited to ~1000 req/day)
