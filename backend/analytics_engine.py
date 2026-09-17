"""
Python analytics engine for route performance analysis.

Provides:
  - Route rankings (weighted composite score)
  - Deterioration detection (30-day rolling comparison)
  - Worst time-slot identification
  - Category breakdown with severity scores
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from backend.models import Feedback, Route

if TYPE_CHECKING:
    from backend.schemas import (
        CategoryBreakdown,
        DeteriorationAlert,
        RouteRanking,
        RouteSummary,
        TimeHeatmapCell,
    )

# Weights for composite score
WEIGHTS = {
    "punctuality": 0.30,
    "driver": 0.30,
    "cleanliness": 0.20,
    "crowding": 0.20,
}

SEVERITY_SCORE = {"low": 1, "medium": 2, "high": 3}

HOUR_PERIOD_LABELS = {
    (5, 9): "5 AM–9 AM (Morning Rush)",
    (9, 12): "9 AM–12 PM (Mid-Morning)",
    (12, 14): "12 PM–2 PM (Lunch)",
    (14, 17): "2 PM–5 PM (Afternoon)",
    (17, 20): "5 PM–8 PM (Evening Rush)",
    (20, 24): "8 PM–12 AM (Night)",
    (0, 5): "12 AM–5 AM (Late Night)",
}

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _hour_to_period(hour: int) -> str:
    for (start, end), label in HOUR_PERIOD_LABELS.items():
        if start <= hour < end:
            return label
    return "Unknown"


def _avg(values: list[float]) -> float:
    return round(statistics.mean(values), 2) if values else 0.0


def compute_composite_score(
    punctuality: float,
    driver: float,
    cleanliness: float,
    crowding: float,
    overall: float,
) -> float:
    """
    Composite score = 40% overall + 60% weighted component average.
    Component weights: punctuality 30%, driver 30%, cleanliness 20%, crowding 20%.
    Ratings are inverted for crowding (higher crowding rating = less crowded = good).
    """
    if all(v == 0 for v in [punctuality, driver, cleanliness, crowding, overall]):
        return 0.0

    # Filter out unrated sub-scores (== 0)
    components = []
    if punctuality > 0:
        components.append(("punctuality", punctuality))
    if driver > 0:
        components.append(("driver", driver))
    if cleanliness > 0:
        components.append(("cleanliness", cleanliness))
    if crowding > 0:
        components.append(("crowding", crowding))

    if components:
        total_weight = sum(WEIGHTS[name] for name, _ in components)
        weighted_sum = sum(WEIGHTS[name] * val for name, val in components)
        component_score = weighted_sum / total_weight
    else:
        component_score = overall

    score = 0.4 * overall + 0.6 * component_score if overall > 0 else component_score
    return round(max(0.0, min(5.0, score)), 2)


# ---------------------------------------------------------------------------
# Route summary
# ---------------------------------------------------------------------------
def get_route_summary(route_id: int, db: Session) -> dict | None:
    route: Route | None = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        return None

    feedbacks = db.query(Feedback).filter(Feedback.route_id == route_id).all()
    if not feedbacks:
        return {
            "route_id": route.id,
            "route_number": route.route_number,
            "route_name": route.route_name,
            "borough": route.borough,
            "overall_rating": 0.0,
            "rating_punctuality": 0.0,
            "rating_cleanliness": 0.0,
            "rating_crowding": 0.0,
            "rating_driver": 0.0,
            "top_issue": "N/A",
            "second_issue": "N/A",
            "worst_period": "N/A",
            "complaints_this_month": 0,
            "total_feedback": 0,
            "composite_score": 0.0,
        }

    # Average ratings
    avg_overall = _avg([f.rating_overall for f in feedbacks if f.rating_overall > 0])
    avg_punc = _avg([f.rating_punctuality for f in feedbacks if f.rating_punctuality > 0])
    avg_clean = _avg([f.rating_cleanliness for f in feedbacks if f.rating_cleanliness > 0])
    avg_crowd = _avg([f.rating_crowding for f in feedbacks if f.rating_crowding > 0])
    avg_driver = _avg([f.rating_driver for f in feedbacks if f.rating_driver > 0])
    composite = compute_composite_score(avg_punc, avg_driver, avg_clean, avg_crowd, avg_overall)

    # Category counts for top issues
    cat_counts: dict[str, int] = defaultdict(int)
    for f in feedbacks:
        if f.category and f.category != "General":
            cat_counts[f.category] += 1
    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    top_issue = sorted_cats[0][0] if sorted_cats else "None"
    second_issue = sorted_cats[1][0] if len(sorted_cats) > 1 else "None"

    # Worst period by complaint count per hour
    hour_counts: dict[int, int] = defaultdict(int)
    for f in feedbacks:
        hour_counts[f.hour_of_day] += 1
    if hour_counts:
        worst_hour = max(hour_counts, key=lambda h: hour_counts[h])
        worst_period = _hour_to_period(worst_hour)
    else:
        worst_period = "N/A"

    # Complaints this calendar month
    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    complaints_this_month = sum(
        1 for f in feedbacks if f.submitted_at >= month_start
    )

    return {
        "route_id": route.id,
        "route_number": route.route_number,
        "route_name": route.route_name,
        "borough": route.borough,
        "overall_rating": avg_overall,
        "rating_punctuality": avg_punc,
        "rating_cleanliness": avg_clean,
        "rating_crowding": avg_crowd,
        "rating_driver": avg_driver,
        "top_issue": top_issue,
        "second_issue": second_issue,
        "worst_period": worst_period,
        "complaints_this_month": complaints_this_month,
        "total_feedback": len(feedbacks),
        "composite_score": composite,
    }


# ---------------------------------------------------------------------------
# Route rankings
# ---------------------------------------------------------------------------
def get_route_rankings(db: Session) -> list[dict]:
    routes = db.query(Route).filter(Route.is_active == True).all()
    results = []

    for route in routes:
        feedbacks = db.query(Feedback).filter(Feedback.route_id == route.id).all()
        if not feedbacks:
            continue

        avg_overall = _avg([f.rating_overall for f in feedbacks if f.rating_overall > 0])
        avg_punc = _avg([f.rating_punctuality for f in feedbacks if f.rating_punctuality > 0])
        avg_clean = _avg([f.rating_cleanliness for f in feedbacks if f.rating_cleanliness > 0])
        avg_crowd = _avg([f.rating_crowding for f in feedbacks if f.rating_crowding > 0])
        avg_driver = _avg([f.rating_driver for f in feedbacks if f.rating_driver > 0])
        composite = compute_composite_score(avg_punc, avg_driver, avg_clean, avg_crowd, avg_overall)

        # Trend: compare last 30 days vs previous 30 days
        now = datetime.now()
        cutoff_30 = now - timedelta(days=30)
        cutoff_60 = now - timedelta(days=60)

        recent = [f for f in feedbacks if f.submitted_at >= cutoff_30 and f.rating_overall > 0]
        previous = [f for f in feedbacks if cutoff_60 <= f.submitted_at < cutoff_30 and f.rating_overall > 0]

        if recent and previous:
            delta = _avg([f.rating_overall for f in recent]) - _avg([f.rating_overall for f in previous])
            trend = "improving" if delta > 0.15 else ("declining" if delta < -0.15 else "stable")
        else:
            trend = "stable"

        results.append({
            "route_id": route.id,
            "route_number": route.route_number,
            "route_name": route.route_name,
            "borough": route.borough,
            "composite_score": composite,
            "overall_rating": avg_overall,
            "total_feedback": len(feedbacks),
            "trend": trend,
        })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results


# ---------------------------------------------------------------------------
# Deterioration detection
# ---------------------------------------------------------------------------
def get_deteriorating_routes(db: Session, threshold: float = 0.25) -> list[dict]:
    routes = db.query(Route).filter(Route.is_active == True).all()
    alerts = []

    now = datetime.now()
    cutoff_30 = now - timedelta(days=30)
    cutoff_60 = now - timedelta(days=60)

    for route in routes:
        feedbacks = db.query(Feedback).filter(Feedback.route_id == route.id).all()
        recent = [f for f in feedbacks if f.submitted_at >= cutoff_30 and f.rating_overall > 0]
        previous = [f for f in feedbacks if cutoff_60 <= f.submitted_at < cutoff_30 and f.rating_overall > 0]

        if not recent or not previous:
            continue

        score_30 = _avg([f.rating_overall for f in recent])
        score_prev = _avg([f.rating_overall for f in previous])
        delta = score_30 - score_prev

        if delta < -threshold:
            alerts.append({
                "route_id": route.id,
                "route_number": route.route_number,
                "route_name": route.route_name,
                "borough": route.borough,
                "score_30d": round(score_30, 2),
                "score_prev_30d": round(score_prev, 2),
                "delta": round(delta, 2),
                "severity": "critical" if delta < -0.5 else "warning",
            })

    alerts.sort(key=lambda x: x["delta"])
    return alerts


# ---------------------------------------------------------------------------
# Time heatmap
# ---------------------------------------------------------------------------
def get_time_heatmap(route_id: int, db: Session) -> list[dict]:
    feedbacks = db.query(Feedback).filter(Feedback.route_id == route_id).all()

    # hour × day_of_week grid
    grid: dict[tuple[int, int], list[float]] = defaultdict(list)
    for f in feedbacks:
        dow = f.submitted_at.weekday()  # 0=Mon
        key = (f.hour_of_day, dow)
        grid[key].append(f.rating_overall if f.rating_overall > 0 else 3.0)

    cells = []
    for (hour, dow), ratings in grid.items():
        cells.append({
            "hour": hour,
            "day_of_week": dow,
            "complaint_count": len(ratings),
            "avg_rating": _avg(ratings),
        })

    return sorted(cells, key=lambda c: (c["hour"], c["day_of_week"]))


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------
def get_category_breakdown(route_id: int, db: Session) -> list[dict]:
    feedbacks = db.query(Feedback).filter(Feedback.route_id == route_id).all()
    if not feedbacks:
        return []

    cat_data: dict[str, list[int]] = defaultdict(list)
    for f in feedbacks:
        cat_data[f.category].append(SEVERITY_SCORE.get(f.severity, 1))

    total = len(feedbacks)
    breakdown = []
    for cat, scores in cat_data.items():
        breakdown.append({
            "category": cat,
            "count": len(scores),
            "percentage": round(len(scores) / total * 100, 1),
            "avg_severity_score": round(statistics.mean(scores), 2),
        })

    return sorted(breakdown, key=lambda x: x["count"], reverse=True)


# ---------------------------------------------------------------------------
# All-routes category breakdown (for admin overview)
# ---------------------------------------------------------------------------
def get_global_category_breakdown(db: Session) -> list[dict]:
    feedbacks = db.query(Feedback).all()
    if not feedbacks:
        return []

    cat_data: dict[str, list[int]] = defaultdict(list)
    for f in feedbacks:
        cat_data[f.category].append(SEVERITY_SCORE.get(f.severity, 1))

    total = len(feedbacks)
    breakdown = []
    for cat, scores in cat_data.items():
        breakdown.append({
            "category": cat,
            "count": len(scores),
            "percentage": round(len(scores) / total * 100, 1),
            "avg_severity_score": round(statistics.mean(scores), 2),
        })

    return sorted(breakdown, key=lambda x: x["count"], reverse=True)


# ---------------------------------------------------------------------------
# Rating trend over time (monthly averages)
# ---------------------------------------------------------------------------
def get_rating_trend(route_id: int | None, db: Session, months: int = 6) -> list[dict]:
    query = db.query(Feedback)
    if route_id:
        query = query.filter(Feedback.route_id == route_id)

    feedbacks = query.order_by(Feedback.submitted_at).all()
    if not feedbacks:
        return []

    monthly: dict[str, list[float]] = defaultdict(list)
    for f in feedbacks:
        key = f.submitted_at.strftime("%Y-%m")
        if f.rating_overall > 0:
            monthly[key].append(f.rating_overall)

    trend = []
    for month, ratings in sorted(monthly.items())[-months:]:
        trend.append({
            "month": month,
            "avg_rating": _avg(ratings),
            "count": len(ratings),
        })

    return trend
