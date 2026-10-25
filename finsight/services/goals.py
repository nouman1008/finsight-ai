"""Savings goal management and progress calculations."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select

from finsight.database import session_scope
from finsight.models import SavingsGoal
from finsight.validation import ValidationError, parse_amount, parse_date, require_text

GOAL_COLUMNS = ["id", "name", "target_amount", "current_amount", "target_date", "is_demo"]
DAYS_PER_MONTH = 30.44


@dataclass(frozen=True)
class GoalProgress:
    """Progress figures for one goal. Monthly figures are estimates."""

    percent: float
    remaining: float
    monthly_required: float | None
    months_left: int | None
    status: str  # completed, on_track, overdue or no_date


def goal_progress(target: float, current: float, target_date: date | None, today: date | None = None) -> GoalProgress:
    """Compute completion, remaining amount and the estimated monthly contribution needed."""
    today = today or date.today()
    target = float(target)
    current = float(current)
    if target <= 0:
        raise ValidationError("Target amount must be greater than zero.")
    percent = current / target
    remaining = max(target - current, 0.0)
    if remaining == 0:
        return GoalProgress(percent, 0.0, 0.0, None, "completed")
    if target_date is None:
        return GoalProgress(percent, remaining, None, None, "no_date")
    if target_date <= today:
        return GoalProgress(percent, remaining, None, None, "overdue")
    months_left = max(1, math.ceil((target_date - today).days / DAYS_PER_MONTH))
    return GoalProgress(percent, remaining, remaining / months_left, months_left, "on_track")


def list_goals() -> pd.DataFrame:
    """All savings goals in creation order."""
    with session_scope() as session:
        rows = session.scalars(select(SavingsGoal).order_by(SavingsGoal.id)).all()
        records = [
            {
                "id": g.id,
                "name": g.name,
                "target_amount": float(g.target_amount),
                "current_amount": float(g.current_amount or 0.0),
                "target_date": g.target_date,
                "is_demo": bool(g.is_demo),
            }
            for g in rows
        ]
    return pd.DataFrame(records, columns=GOAL_COLUMNS)


def _clean_goal(name: Any, target_amount: Any, current_amount: Any, target_date: Any) -> dict[str, Any]:
    return {
        "name": require_text(name, "Goal name", 120),
        "target_amount": parse_amount(target_amount, "Target amount"),
        "current_amount": parse_amount(current_amount or 0, "Current savings", allow_zero=True),
        "target_date": parse_date(target_date, "Target date") if target_date else None,
    }


def create_goal(name: Any, target_amount: Any, current_amount: Any = 0.0,
                target_date: Any = None, is_demo: bool = False) -> int:
    """Create a savings goal. Target must be positive; the target date is optional."""
    clean = _clean_goal(name, target_amount, current_amount, target_date)
    with session_scope() as session:
        goal = SavingsGoal(**clean, is_demo=is_demo)
        session.add(goal)
        session.flush()
        return int(goal.id)


def update_goal_progress(goal_id: int, current_amount: Any) -> None:
    """Record the amount saved so far toward a goal."""
    amount = parse_amount(current_amount, "Current savings", allow_zero=True)
    with session_scope() as session:
        goal = session.get(SavingsGoal, goal_id)
        if goal is None:
            raise ValidationError("That goal no longer exists.")
        goal.current_amount = amount


def delete_goal(goal_id: int) -> bool:
    """Delete a savings goal. Returns False if it was already gone."""
    with session_scope() as session:
        goal = session.get(SavingsGoal, goal_id)
        if goal is None:
            return False
        session.delete(goal)
        return True
