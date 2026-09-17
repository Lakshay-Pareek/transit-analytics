"""
SQLAlchemy ORM models for the Transport Analytics Platform.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    route_name: Mapped[str] = mapped_column(String(120))
    borough: Mapped[str] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    feedbacks: Mapped[list["Feedback"]] = relationship("Feedback", back_populates="route")
    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="route")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("routes.id"), index=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), index=True
    )
    hour_of_day: Mapped[int] = mapped_column(Integer, default=0)  # 0–23

    # Ratings (1–5 scale; 0 means not rated)
    rating_overall: Mapped[float] = mapped_column(Float, default=0.0)
    rating_punctuality: Mapped[float] = mapped_column(Float, default=0.0)
    rating_cleanliness: Mapped[float] = mapped_column(Float, default=0.0)
    rating_crowding: Mapped[float] = mapped_column(Float, default=0.0)
    rating_driver: Mapped[float] = mapped_column(Float, default=0.0)

    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="General", index=True)
    severity: Mapped[str] = mapped_column(String(10), default="low", index=True)
    source: Mapped[str] = mapped_column(String(20), default="user")  # "user" | "311_import"

    route: Mapped["Route"] = relationship("Route", back_populates="feedbacks")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("routes.id"), index=True)
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    vehicle_id: Mapped[str | None] = mapped_column(String(30), nullable=True)

    route: Mapped["Route"] = relationship("Route", back_populates="trips")
