"""
/analytics  — Route performance analytics endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend import analytics_engine
from backend.database import get_db
from backend.schemas import (
    CategoryBreakdown,
    DeteriorationAlert,
    RouteRanking,
    TimeHeatmapCell,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/rankings", response_model=list[RouteRanking])
def route_rankings(db: Session = Depends(get_db)):
    """
    Return all routes ranked by composite score.
    Includes trend indicator (improving / stable / declining).
    """
    return analytics_engine.get_route_rankings(db)


@router.get("/deterioration", response_model=list[DeteriorationAlert])
def deterioration_alerts(
    threshold: float = Query(0.25, description="Rating drop threshold to flag"),
    db: Session = Depends(get_db),
):
    """
    Return routes whose average rating has dropped by >= threshold
    comparing the last 30 days vs the previous 30 days.
    Severity: 'critical' if drop > 0.5, else 'warning'.
    """
    return analytics_engine.get_deteriorating_routes(db, threshold=threshold)


@router.get("/time-heatmap/{route_id}", response_model=list[TimeHeatmapCell])
def time_heatmap(route_id: int, db: Session = Depends(get_db)):
    """
    Return complaint counts and average ratings bucketed by hour-of-day × day-of-week.
    Useful for identifying worst time slots (e.g., 5 PM–7 PM weekdays).
    """
    return analytics_engine.get_time_heatmap(route_id, db)


@router.get("/categories/{route_id}", response_model=list[CategoryBreakdown])
def category_breakdown(route_id: int, db: Session = Depends(get_db)):
    """
    Return complaint category breakdown for a specific route.
    Includes percentage share and average severity score.
    """
    return analytics_engine.get_category_breakdown(route_id, db)


@router.get("/categories", response_model=list[CategoryBreakdown])
def global_category_breakdown(db: Session = Depends(get_db)):
    """Return category breakdown across ALL routes."""
    return analytics_engine.get_global_category_breakdown(db)


@router.get("/trend")
def rating_trend(
    route_id: int | None = Query(None, description="Leave blank for all routes"),
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """
    Return monthly average rating trend.
    If route_id is omitted, returns the global trend across all routes.
    """
    return analytics_engine.get_rating_trend(route_id, db, months=months)


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    """
    High-level platform overview stats for the admin dashboard header.
    Returns total feedback count, overall average rating, total routes,
    and number of routes with deterioration alerts.
    """
    from backend.models import Feedback, Route

    total_feedback = db.query(Feedback).count()
    total_routes = db.query(Route).filter(Route.is_active == True).count()
    user_feedback = db.query(Feedback).filter(Feedback.source == "user").count()

    all_ratings = [
        f.rating_overall
        for f in db.query(Feedback).all()
        if f.rating_overall > 0
    ]
    avg_rating = round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else 0.0

    alerts = analytics_engine.get_deteriorating_routes(db)
    critical_count = sum(1 for a in alerts if a["severity"] == "critical")

    return {
        "total_feedback": total_feedback,
        "user_submitted": user_feedback,
        "total_routes": total_routes,
        "platform_avg_rating": avg_rating,
        "routes_with_alerts": len(alerts),
        "critical_alerts": critical_count,
    }
