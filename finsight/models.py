"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now()


class Base(DeclarativeBase):
    """Declarative base for all models."""


class Transaction(Base):
    """A single income, expense or transfer record."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    transaction_type: Mapped[str] = mapped_column("type", String(20), index=True)
    category: Mapped[str] = mapped_column(String(60), index=True)
    transaction_date: Mapped[date] = mapped_column("date", Date, index=True)
    payment_method: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Budget(Base):
    """A recurring monthly spending limit for one expense category."""

    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(60), unique=True)
    monthly_limit: Mapped[float] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SavingsGoal(Base):
    """A savings target with optional target date."""

    __tablename__ = "savings_goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    target_amount: Mapped[float] = mapped_column(Float)
    current_amount: Mapped[float] = mapped_column(Float, default=0.0)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AppSetting(Base):
    """Key-value application settings such as the opening balance."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
