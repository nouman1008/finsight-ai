from datetime import date

import numpy as np
import pandas as pd
import pytest

from finsight.dates import filter_by_date, month_bounds, previous_period
from finsight.services.analytics import (
    daily_expense_trend, month_over_month, monthly_income_expense, savings_rate_over_time,
)
from finsight.services.calculations import category_breakdown, summarize, total_balance


def make(rows):
    data = [{"amount": a, "type": t, "category": c, "date": pd.Timestamp(d)} for a, t, c, d in rows]
    return pd.DataFrame(data, columns=["amount", "type", "category", "date"])


def test_income_expense_totals_and_savings_rate():
    df = make([
        (1000, "income", "Salary", date(2026, 3, 1)),
        (500, "income", "Freelance", date(2026, 3, 9)),
        (300, "expense", "Groceries", date(2026, 3, 4)),
    ])
    s = summarize(df)
    assert s.income == 1500
    assert s.expenses == 300
    assert s.net == 1200
    assert s.savings_rate == pytest.approx(0.8)


def test_transfers_do_not_affect_income_or_expenses():
    df = make([
        (1000, "income", "Salary", date(2026, 3, 1)),
        (400, "transfer", "Transfer", date(2026, 3, 2)),
        (100, "expense", "Groceries", date(2026, 3, 3)),
    ])
    s = summarize(df)
    assert s.income == 1000 and s.expenses == 100


def test_savings_rate_is_none_without_income():
    s = summarize(make([(100, "expense", "Groceries", date(2026, 3, 3))]))
    assert s.savings_rate is None


def test_empty_dataset_is_safe_everywhere():
    empty = make([])
    s = summarize(empty)
    assert (s.income, s.expenses, s.net) == (0, 0, 0)
    assert s.savings_rate is None
    assert category_breakdown(empty).empty
    assert monthly_income_expense(empty).empty
    assert daily_expense_trend(empty).empty
    assert total_balance(empty, 5000) == 5000


def test_total_balance_is_opening_plus_net_over_all_records():
    df = make([
        (2000, "income", "Salary", date(2026, 1, 2)),
        (500, "expense", "Rent", date(2026, 1, 5)),
    ])
    assert total_balance(df, 10000) == 11500


def test_category_breakdown_aggregates_and_computes_shares():
    df = make([
        (300, "expense", "Groceries", date(2026, 3, 1)),
        (200, "expense", "Groceries", date(2026, 3, 2)),
        (1000, "expense", "Rent", date(2026, 3, 3)),
    ])
    cats = category_breakdown(df)
    assert list(cats["category"]) == ["Rent", "Groceries"]
    assert cats.iloc[1]["amount"] == 500
    assert cats.iloc[0]["share"] == pytest.approx(1000 / 1500)


def test_savings_rate_over_time_handles_months_without_income():
    df = make([
        (1000, "income", "Salary", date(2026, 1, 1)),
        (200, "expense", "Food", date(2026, 1, 5)),
        (300, "expense", "Food", date(2026, 2, 5)),
    ])
    rates = savings_rate_over_time(monthly_income_expense(df))
    assert rates.iloc[0]["savings_rate"] == pytest.approx(0.8)
    assert np.isnan(rates.iloc[1]["savings_rate"])


def test_month_over_month_change():
    df = make([
        (1000, "expense", "Food", date(2026, 2, 10)),
        (1500, "expense", "Food", date(2026, 3, 10)),
    ])
    result = month_over_month(df, 2026, 3)
    assert result["current"] == 1500
    assert result["previous"] == 1000
    assert result["change_pct"] == pytest.approx(0.5)


def test_month_over_month_without_previous_spending_has_no_percentage():
    df = make([(1500, "expense", "Food", date(2026, 3, 10))])
    assert month_over_month(df, 2026, 3)["change_pct"] is None


def test_date_filtering_and_previous_period():
    df = make([
        (100, "expense", "Food", date(2026, 1, 15)),
        (200, "expense", "Food", date(2026, 2, 15)),
        (300, "expense", "Food", date(2026, 3, 15)),
    ])
    feb = filter_by_date(df, *month_bounds(2026, 2))
    assert feb["amount"].tolist() == [200]
    # Equal-length period: 28 days ending 31 Jan 2026
    assert previous_period(date(2026, 2, 1), date(2026, 2, 28)) == (date(2026, 1, 4), date(2026, 1, 31))
