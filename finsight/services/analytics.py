"""Trend and comparison analytics. Every function returns an empty frame for empty input."""
from __future__ import annotations

import numpy as np
import pandas as pd

from finsight.dates import filter_by_date, month_bounds, previous_month
from finsight.services.calculations import category_breakdown, summarize

MONTHLY_COLUMNS = ["month", "income", "expense", "net"]


def monthly_income_expense(frame: pd.DataFrame) -> pd.DataFrame:
    """Income, expenses and net per calendar month (YYYY-MM)."""
    if frame.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS)
    subset = frame[frame["type"].isin(["income", "expense"])]
    if subset.empty:
        return pd.DataFrame(columns=MONTHLY_COLUMNS)
    months = pd.to_datetime(subset["date"]).dt.strftime("%Y-%m")
    pivot = subset.assign(month=months, amount=subset["amount"].astype(float)).pivot_table(
        index="month", columns="type", values="amount", aggfunc="sum", fill_value=0.0
    )
    pivot = pivot.reindex(columns=["income", "expense"], fill_value=0.0).reset_index()
    pivot.columns.name = None
    pivot["net"] = pivot["income"] - pivot["expense"]
    return pivot.sort_values("month").reset_index(drop=True)


def savings_rate_over_time(monthly: pd.DataFrame) -> pd.DataFrame:
    """Monthly savings rate. Months without income are NaN rather than a division error."""
    if monthly.empty:
        return pd.DataFrame(columns=["month", "savings_rate"])
    rates = [net / inc if inc > 0 else np.nan for net, inc in zip(monthly["net"], monthly["income"])]
    return pd.DataFrame({"month": monthly["month"], "savings_rate": rates})


def daily_expense_trend(frame: pd.DataFrame) -> pd.DataFrame:
    """Total expense per calendar day."""
    columns = ["date", "amount"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    subset = frame[frame["type"] == "expense"]
    if subset.empty:
        return pd.DataFrame(columns=columns)
    days = pd.to_datetime(subset["date"]).dt.normalize()
    daily = subset.assign(day=days).groupby("day", as_index=False)["amount"].sum()
    return daily.rename(columns={"day": "date"}).sort_values("date").reset_index(drop=True)


def monthly_changes(monthly: pd.DataFrame) -> pd.DataFrame:
    """Expense per month with percentage change from the previous month (NaN when undefined)."""
    if monthly.empty:
        return pd.DataFrame(columns=["month", "expense", "change_pct"])
    out = monthly[["month", "expense"]].copy()
    out["change_pct"] = out["expense"].pct_change().replace([np.inf, -np.inf], np.nan)
    return out


def highest_categories(frame: pd.DataFrame, limit: int = 5) -> pd.DataFrame:
    """The largest expense categories."""
    return category_breakdown(frame).head(limit)


def month_over_month(frame: pd.DataFrame, year: int, month: int) -> dict[str, float | None]:
    """Compare expenses in a month with the month before it."""
    cur_start, cur_end = month_bounds(year, month)
    prev_year, prev_month = previous_month(year, month)
    prev_start, prev_end = month_bounds(prev_year, prev_month)
    current = summarize(filter_by_date(frame, cur_start, cur_end)).expenses
    previous = summarize(filter_by_date(frame, prev_start, prev_end)).expenses
    change = round(current - previous, 2)
    change_pct = change / previous if previous > 0 else None
    return {"current": current, "previous": previous, "change": change, "change_pct": change_pct}
