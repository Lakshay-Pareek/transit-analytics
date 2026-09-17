"""
Pydantic v2 schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Route schemas
# ---------------------------------------------------------------------------
class RouteBase(BaseModel):
    route_number: str = Field(..., max_length=20)
    route_name: str = Field(..., max_length=120)
    borough: str = Field(..., max_length=50)
    is_active: bool = True


class RouteCreate(RouteBase):
    pass


class RouteOut(RouteBase):
    id: int

    model_config = {"from_attributes": True}


class RouteSummary(BaseModel):
    """Analytics summary for a single route — the key dashboard output."""
    route_id: int
    route_number: str
    route_name: str
    borough: str
    overall_rating: float
    rating_punctuality: float
    rating_cleanliness: float
    rating_crowding: float
    rating_driver: float
    top_issue: str
    second_issue: str
    worst_period: str
    complaints_this_month: int
    total_feedback: int
    composite_score: float


# ---------------------------------------------------------------------------
# Feedback schemas
# ---------------------------------------------------------------------------
class FeedbackCreate(BaseModel):
    route_id: int
    rating_overall: float = Field(..., ge=1, le=5)
    rating_punctuality: float = Field(0.0, ge=0, le=5)
    rating_cleanliness: float = Field(0.0, ge=0, le=5)
    rating_crowding: float = Field(0.0, ge=0, le=5)
    rating_driver: float = Field(0.0, ge=0, le=5)
    comment: Optional[str] = Field(None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v


class FeedbackOut(BaseModel):
    id: int
    route_id: int
    submitted_at: datetime
    hour_of_day: int
    rating_overall: float
    rating_punctuality: float
    rating_cleanliness: float
    rating_crowding: float
    rating_driver: float
    comment: Optional[str]
    category: str
    severity: str
    source: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics schemas
# ---------------------------------------------------------------------------
class RouteRanking(BaseModel):
    rank: int
    route_id: int
    route_number: str
    route_name: str
    borough: str
    composite_score: float
    overall_rating: float
    total_feedback: int
    trend: str  # "improving" | "declining" | "stable"


class DeteriorationAlert(BaseModel):
    route_id: int
    route_number: str
    route_name: str
    borough: str
    score_30d: float
    score_prev_30d: float
    delta: float
    severity: str  # "critical" | "warning"


class TimeHeatmapCell(BaseModel):
    hour: int
    day_of_week: int  # 0=Mon … 6=Sun
    complaint_count: int
    avg_rating: float


class CategoryBreakdown(BaseModel):
    category: str
    count: int
    percentage: float
    avg_severity_score: float  # low=1, medium=2, high=3


# ---------------------------------------------------------------------------
# Classifier schema
# ---------------------------------------------------------------------------
class ClassifyRequest(BaseModel):
    comment: str = Field(..., min_length=1, max_length=2000)


class ClassifyResponse(BaseModel):
    category: str
    severity: str
    confidence: float
