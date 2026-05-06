"""Modelos Activity, Record y Lap."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fitapp.db import Base


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (UniqueConstraint("user_id", "file_hash", name="uq_activities_user_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    sport: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(nullable=False)

    duration_s: Mapped[int | None] = mapped_column(Integer)
    moving_time_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    ascent_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    descent_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    avg_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    max_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    max_hr: Mapped[int | None] = mapped_column(Integer)
    avg_cadence: Mapped[int | None] = mapped_column(Integer)
    avg_power: Mapped[int | None] = mapped_column(Integer)
    calories: Mapped[int | None] = mapped_column(Integer)

    start_point = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
    bbox = mapped_column(Geography(geometry_type="POLYGON", srid=4326, spatial_index=False))
    summary: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)

    records: Mapped[list[Record]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", passive_deletes=True
    )
    laps: Mapped[list[Lap]] = relationship(
        back_populates="activity", cascade="all, delete-orphan", passive_deletes=True
    )


class Record(Base):
    __tablename__ = "records"

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ts: Mapped[datetime] = mapped_column(primary_key=True)

    position = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
    altitude_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    heart_rate: Mapped[int | None] = mapped_column(SmallInteger)
    cadence: Mapped[int | None] = mapped_column(SmallInteger)
    power: Mapped[int | None] = mapped_column(SmallInteger)
    temperature: Mapped[int | None] = mapped_column(SmallInteger)

    activity: Mapped[Activity] = relationship(back_populates="records")


class Lap(Base):
    __tablename__ = "laps"
    __table_args__ = (UniqueConstraint("activity_id", "lap_index", name="uq_laps_activity_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    distance_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    avg_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    avg_hr: Mapped[int | None] = mapped_column(Integer)
    ascent_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    activity: Mapped[Activity] = relationship(back_populates="laps")
