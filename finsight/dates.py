"""Date helpers shared by services and the UI."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return the first and last day of a calendar month."""
    start = date(year, month, 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return start, date(next_year, next_month, 1) - timedelta(days=1)


def previous_month(year: int, month: int) -> tuple[int, int]:
    """Return the (year, month) pair immediately before the given month."""
    return (year - 1, 12) if month == 1 else (year, month - 1)


def previous_period(start: date, end: date) -> tuple[date, date]:
    """Return the period of identical length that ends the day before ``start``."""
    length = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=length - 1), prev_end


def filter_by_date(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    """Keep rows whose ``date`` column falls within [start, end] inclusive."""
    if frame.empty:
        return frame
    days = pd.to_datetime(frame["date"]).dt.date
    return frame[(days >= start) & (days <= end)]
