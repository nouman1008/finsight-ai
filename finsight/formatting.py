"""Consistent display formatting for currency, percentages and dates."""
from __future__ import annotations

import math
from typing import Any

import config


def format_currency(amount: Any, currency: str = config.DEFAULT_CURRENCY) -> str:
    """Format an amount such as ``PKR 1,250``. Missing values render as N/A."""
    if amount is None:
        return "N/A"
    value = float(amount)
    if math.isnan(value):
        return "N/A"
    sign = "-" if round(value) < 0 else ""
    return f"{sign}{currency} {abs(value):,.0f}"


def format_percent(fraction: Any, decimals: int = 1) -> str:
    """Format a 0-1 fraction as a percentage. Undefined values render as N/A."""
    if fraction is None:
        return "N/A"
    value = float(fraction)
    if math.isnan(value) or math.isinf(value):
        return "N/A"
    return f"{value * 100:.{decimals}f}%"
