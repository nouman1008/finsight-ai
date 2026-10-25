"""Rule-based financial insights built from stored data.

Each insight is labelled 'Historical' (derived from recorded transactions) or
'Estimate' (illustrative or forecast-based). Nothing here guarantees future outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

import config
from finsight.dates import filter_by_date, month_bounds, previous_period
from finsight.formatting import format_currency as fc
from finsight.formatting import format_percent
from finsight.services import transactions
from finsight.services.analytics import monthly_income_expense
from finsight.services.budgets import budget_status, list_budgets
from finsight.services.calculations import Summary, category_breakdown, summarize
from finsight.services.forecast import forecast_next_month_expenses
from finsight.services.goals import goal_progress, list_goals

HISTORICAL = "Historical"
ESTIMATE = "Estimate"


@dataclass(frozen=True)
class Insight:
    """A single explanation. level is info, success, warning or danger."""

    level: str
    basis: str
    message: str


def generate_insights(
    current: Summary,
    previous: Summary,
    current_categories: pd.DataFrame,
    previous_categories: pd.DataFrame,
    budget_df: pd.DataFrame,
    goals_df: pd.DataFrame,
    today: date,
    forecast: dict[str, float] | None = None,
) -> list[Insight]:
    """Build insights from already-computed figures. Pure function, easy to test."""
    items: list[Insight] = []

    if previous.expenses > 0:
        change = (current.expenses - previous.expenses) / previous.expenses
        detail = f"({fc(previous.expenses)} to {fc(current.expenses)})"
        if change >= config.OVERSPEND_CHANGE_THRESHOLD:
            items.append(Insight("warning", HISTORICAL,
                                 f"Expenses are {format_percent(change)} higher than the previous period {detail}."))
        elif change <= -config.OVERSPEND_CHANGE_THRESHOLD:
            items.append(Insight("success", HISTORICAL,
                                 f"Expenses fell {format_percent(-change)} compared with the previous period {detail}."))

    rate = current.savings_rate
    if rate is None:
        items.append(Insight("info", HISTORICAL,
                             "No income is recorded for this period, so the savings rate cannot be calculated."))
    elif rate < 0:
        items.append(Insight("danger", HISTORICAL,
                             f"Spending exceeded income this period (savings rate {format_percent(rate)})."))
    elif rate < 0.2:
        items.append(Insight("warning", HISTORICAL,
                             f"The savings rate is {format_percent(rate)}. A common rule of thumb is to save at least 20% of income."))
    else:
        items.append(Insight("success", HISTORICAL,
                             f"The savings rate is {format_percent(rate)}, above the 20% rule of thumb."))

    previous_map = {} if previous_categories.empty else dict(zip(previous_categories["category"], previous_categories["amount"]))
    for row in current_categories.itertuples(index=False):
        before = float(previous_map.get(row.category, 0.0))
        after = float(row.amount)
        if (before > 0 and after >= before * config.CATEGORY_SPIKE_RATIO
                and after - before >= config.CATEGORY_SPIKE_MIN_INCREASE):
            items.append(Insight("warning", HISTORICAL,
                                 f"{row.category} spending rose from {fc(before)} to {fc(after)} compared with the previous period."))

    if not current_categories.empty and float(current_categories.iloc[0]["share"]) >= 0.3:
        top = current_categories.iloc[0]
        potential = float(top["amount"]) * 0.10
        items.append(Insight("info", ESTIMATE,
                             f"{top['category']} makes up {format_percent(top['share'])} of expenses. "
                             f"Trimming it by 10% would free about {fc(potential)} (an illustrative figure, not a forecast)."))

    for row in budget_df.itertuples(index=False):
        if row.status == "exceeded":
            items.append(Insight("danger", HISTORICAL,
                                 f"{row.category} is over budget: spent {fc(row.spent)} against a limit of {fc(row.monthly_limit)}."))
        elif row.status == "warning":
            items.append(Insight("warning", HISTORICAL,
                                 f"{row.category} has used {format_percent(row.utilization)} of its budget; {fc(row.remaining)} remains."))

    for goal in goals_df.itertuples(index=False):
        target_date = goal.target_date if isinstance(goal.target_date, date) else None
        progress = goal_progress(float(goal.target_amount), float(goal.current_amount), target_date, today)
        if progress.status == "completed":
            items.append(Insight("success", HISTORICAL, f"Goal '{goal.name}' is complete."))
        elif progress.status == "overdue":
            items.append(Insight("warning", HISTORICAL,
                                 f"Goal '{goal.name}' is past its target date with {format_percent(progress.percent)} saved."))
        elif progress.status == "on_track":
            items.append(Insight("info", ESTIMATE,
                                 f"Goal '{goal.name}' needs about {fc(progress.monthly_required)} per month to reach its target by "
                                 f"{target_date:%d %b %Y}. {format_percent(progress.percent)} is saved so far."))
        else:
            items.append(Insight("info", HISTORICAL,
                                 f"Goal '{goal.name}' has no target date, so no monthly contribution is estimated."))

    if forecast:
        items.append(Insight("info", ESTIMATE,
                             f"Estimated spending next month is about {fc(forecast['estimate'])} "
                             f"(range {fc(forecast['low'])} to {fc(forecast['high'])}), based on a linear trend across "
                             f"{int(forecast['months_used'])} months. This is an estimate, not a guarantee."))

    if not items:
        items.append(Insight("info", HISTORICAL, "Add more transactions to unlock insights."))
    return items


def period_insights(start: date, end: date, today: date | None = None) -> list[Insight]:
    """Load stored data for a period and generate its insights."""
    today = today or date.today()
    all_df = transactions.list_transactions()
    period_df = filter_by_date(all_df, start, end)
    prev_start, prev_end = previous_period(start, end)
    prev_df = filter_by_date(all_df, prev_start, prev_end)
    budget_start, budget_end = month_bounds(end.year, end.month)
    status_df = budget_status(list_budgets(), filter_by_date(all_df, budget_start, budget_end),
                              budget_start, budget_end)
    monthly = monthly_income_expense(all_df)
    forecast = forecast_next_month_expenses(monthly.set_index("month")["expense"]) if not monthly.empty else None
    return generate_insights(
        summarize(period_df),
        summarize(prev_df),
        category_breakdown(period_df),
        category_breakdown(prev_df),
        status_df,
        list_goals(),
        today,
        forecast,
    )
