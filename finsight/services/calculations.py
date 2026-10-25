"""Core financial calculations on transaction frames. Pure functions, no database access."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Summary:
    """Totals for a set of transactions. Transfers are excluded from income and expenses."""

    income: float
    expenses: float
    net: float
    savings_rate: float | None
    transaction_count: int


def _sum_type(frame: pd.DataFrame, txn_type: str) -> float:
    if frame.empty:
        return 0.0
    return float(frame.loc[frame["type"] == txn_type, "amount"].sum())


def summarize(frame: pd.DataFrame) -> Summary:
    """Compute income, expenses, net savings and savings rate. Savings rate is None without income."""
    income = round(_sum_type(frame, "income"), 2)
    expenses = round(_sum_type(frame, "expense"), 2)
    net = round(income - expenses, 2)
    rate = net / income if income > 0 else None
    return Summary(income, expenses, net, rate, len(frame))


def total_balance(all_frame: pd.DataFrame, opening_balance: float) -> float:
    """Opening balance plus all recorded income minus all recorded expenses (transfers excluded)."""
    return round(float(opening_balance) + summarize(all_frame).net, 2)


def category_breakdown(frame: pd.DataFrame, txn_type: str = "expense") -> pd.DataFrame:
    """Totals and share of total per category, sorted largest first."""
    columns = ["category", "amount", "share"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    subset = frame[frame["type"] == txn_type]
    if subset.empty:
        return pd.DataFrame(columns=columns)
    grouped = subset.groupby("category", as_index=False)["amount"].sum()
    grouped = grouped.sort_values("amount", ascending=False).reset_index(drop=True)
    total = float(grouped["amount"].sum())
    grouped["share"] = grouped["amount"] / total if total > 0 else 0.0
    return grouped[columns]
