"""Monthly category budgets and utilisation."""
from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy import select

import config
from finsight.dates import filter_by_date
from finsight.database import session_scope
from finsight.models import Budget
from finsight.validation import ValidationError, parse_amount

BUDGET_COLUMNS = ["id", "category", "monthly_limit", "is_demo"]
BUDGET_STATUS_COLUMNS = ["category", "monthly_limit", "spent", "remaining", "utilization", "status"]


def list_budgets() -> pd.DataFrame:
    """All budgets, ordered by category."""
    with session_scope() as session:
        rows = session.scalars(select(Budget).order_by(Budget.category)).all()
        records = [
            {"id": b.id, "category": b.category, "monthly_limit": float(b.monthly_limit), "is_demo": bool(b.is_demo)}
            for b in rows
        ]
    return pd.DataFrame(records, columns=BUDGET_COLUMNS)


def _validate_category(category: object) -> None:
    if category not in config.EXPENSE_CATEGORIES:
        raise ValidationError("Choose an expense category for the budget.")


def create_budget(category: str, monthly_limit: object, is_demo: bool = False) -> int:
    """Create a monthly budget. Each category may have only one budget."""
    _validate_category(category)
    limit = parse_amount(monthly_limit, "Monthly limit")
    with session_scope() as session:
        exists = session.scalar(select(Budget.id).where(Budget.category == category))
        if exists is not None:
            raise ValidationError(f"A budget for {category} already exists. Edit it instead.")
        budget = Budget(category=category, monthly_limit=limit, is_demo=is_demo)
        session.add(budget)
        session.flush()
        return int(budget.id)


def update_budget_limit(budget_id: int, monthly_limit: object) -> None:
    """Change the monthly limit of an existing budget."""
    limit = parse_amount(monthly_limit, "Monthly limit")
    with session_scope() as session:
        budget = session.get(Budget, budget_id)
        if budget is None:
            raise ValidationError("That budget no longer exists.")
        budget.monthly_limit = limit


def delete_budget(budget_id: int) -> bool:
    """Delete a budget. Returns False if it was already gone."""
    with session_scope() as session:
        budget = session.get(Budget, budget_id)
        if budget is None:
            return False
        session.delete(budget)
        return True


def budget_status(budgets: pd.DataFrame, expenses: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Spending against each budget within [start, end].

    Status is 'ok' below the warning threshold, 'warning' from the threshold up to the
    full limit, and 'exceeded' above the limit. Zero limits report zero utilisation.
    """
    if budgets.empty:
        return pd.DataFrame(columns=BUDGET_STATUS_COLUMNS)
    period = filter_by_date(expenses, start, end)
    if not period.empty:
        period = period[period["type"] == "expense"]
    spent_by_category = period.groupby("category")["amount"].sum().to_dict() if not period.empty else {}
    rows = []
    for budget in budgets.itertuples(index=False):
        limit = float(budget.monthly_limit)
        spent = round(float(spent_by_category.get(budget.category, 0.0)), 2)
        utilization = spent / limit if limit > 0 else 0.0
        if utilization > 1:
            status = "exceeded"
        elif utilization >= config.BUDGET_WARNING_THRESHOLD:
            status = "warning"
        else:
            status = "ok"
        rows.append({
            "category": budget.category,
            "monthly_limit": limit,
            "spent": spent,
            "remaining": round(limit - spent, 2),
            "utilization": utilization,
            "status": status,
        })
    return pd.DataFrame(rows, columns=BUDGET_STATUS_COLUMNS)
