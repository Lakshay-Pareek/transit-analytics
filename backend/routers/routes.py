"""
/routes  — Route management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import analytics_engine
from backend.database import get_db
from backend.models import Route
from backend.schemas import RouteCreate, RouteOut, RouteSummary

router = APIRouter(prefix="/routes", tags=["Routes"])


@router.get("/", response_model=list[RouteOut])
def list_routes(borough: str | None = None, db: Session = Depends(get_db)):
    """Return all active routes, optionally filtered by borough."""
    query = db.query(Route).filter(Route.is_active == True)
    if borough:
        query = query.filter(Route.borough.ilike(f"%{borough}%"))
    return query.order_by(Route.route_number).all()


@router.get("/{route_id}", response_model=RouteOut)
def get_route(route_id: int, db: Session = Depends(get_db)):
    route = db.query(Route).filter(Route.id == route_id).first()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")
    return route


@router.get("/{route_id}/summary", response_model=RouteSummary)
def route_summary(route_id: int, db: Session = Depends(get_db)):
    """
    Return the full analytics summary for a route — the key dashboard data.
    Example output for Route M42:
      Overall Rating: 2.7/5
      Top Issue: Overcrowding
      Worst period: 5 PM–7 PM
      Complaints this month: 128
    """
    summary = analytics_engine.get_route_summary(route_id, db)
    if not summary:
        raise HTTPException(status_code=404, detail="Route not found")
    return summary


@router.post("/", response_model=RouteOut, status_code=201)
def create_route(payload: RouteCreate, db: Session = Depends(get_db)):
    existing = db.query(Route).filter(Route.route_number == payload.route_number).first()
    if existing:
        raise HTTPException(status_code=409, detail="Route number already exists")
    route = Route(**payload.model_dump())
    db.add(route)
    db.commit()
    db.refresh(route)
    return route
