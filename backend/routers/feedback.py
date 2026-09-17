"""
/feedback  — Passenger feedback submission and querying.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.classifier import classify
from backend.database import get_db
from backend.models import Feedback, Route
from backend.schemas import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("/", response_model=FeedbackOut, status_code=201)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    """
    Submit passenger feedback for a route.
    The comment is automatically classified into a category and severity.
    """
    route = db.query(Route).filter(Route.id == payload.route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    # Auto-classify comment
    now = datetime.now()
    classification = classify(payload.comment or "")

    fb = Feedback(
        route_id=payload.route_id,
        submitted_at=now,
        hour_of_day=now.hour,
        rating_overall=payload.rating_overall,
        rating_punctuality=payload.rating_punctuality,
        rating_cleanliness=payload.rating_cleanliness,
        rating_crowding=payload.rating_crowding,
        rating_driver=payload.rating_driver,
        comment=payload.comment,
        category=classification["category"],
        severity=classification["severity"],
        source="user",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


@router.get("/", response_model=list[FeedbackOut])
def list_feedback(
    route_id: int | None = Query(None),
    category: str | None = Query(None),
    severity: str | None = Query(None),
    start: str | None = Query(None, description="ISO date: 2024-01-01"),
    end: str | None = Query(None, description="ISO date: 2024-12-31"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Query feedback with filters. Supports pagination."""
    query = db.query(Feedback)

    if route_id is not None:
        query = query.filter(Feedback.route_id == route_id)
    if category:
        query = query.filter(Feedback.category.ilike(f"%{category}%"))
    if severity:
        query = query.filter(Feedback.severity == severity)
    if start:
        try:
            query = query.filter(Feedback.submitted_at >= datetime.fromisoformat(start))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid start date format")
    if end:
        try:
            query = query.filter(Feedback.submitted_at <= datetime.fromisoformat(end))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid end date format")

    return (
        query.order_by(Feedback.submitted_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{feedback_id}", response_model=FeedbackOut)
def get_feedback(feedback_id: int, db: Session = Depends(get_db)):
    fb = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not fb:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return fb
