from datetime import date

import pandas as pd
import pytest

from finsight.services import budgets, demo, goals, transactions
from finsight.services.budgets import BUDGET_STATUS_COLUMNS, budget_status
from finsight.services.calculations import Summary
from finsight.services.forecast import forecast_next_month_expenses
from finsight.services.goals import GOAL_COLUMNS, goal_progress
from finsight.services.insights import generate_insights
from finsight.validation import ValidationError


def make_budgets(rows):
    return pd.DataFrame([{"id": i + 1, "category": c, "monthly_limit": float(l), "is_demo": False}
                         for i, (c, l) in enumerate(rows)], columns=budgets.BUDGET_COLUMNS)


def make_expenses(rows):
    return pd.DataFrame([{"amount": a, "type": "expense", "category": c, "date": pd.Timestamp(d),
                          "title": "x", "is_demo": False} for c, a, d in rows])


def test_budget_thresholds_warning_and_exceeded():
    b = make_budgets([("Groceries", 1000), ("Food & Dining", 1000), ("Transport", 1000), ("Shopping", 1000)])
    e = make_expenses([("Groceries", 500, date(2026, 3, 5)),
                       ("Food & Dining", 850, date(2026, 3, 6)),
                       ("Transport", 1200, date(2026, 3, 7))])
    status = budget_status(b, e, date(2026, 3, 1), date(2026, 3, 31)).set_index("category")
    assert status.loc["Groceries", "status"] == "ok"
    assert status.loc["Food & Dining", "status"] == "warning"
    assert status.loc["Transport", "status"] == "exceeded"
    assert status.loc["Transport", "remaining"] == -200
    assert status.loc["Shopping", "spent"] == 0


def test_budget_period_boundaries_are_respected():
    b = make_budgets([("Groceries", 1000)])
    e = make_expenses([("Groceries", 400, date(2026, 2, 28)), ("Groceries", 100, date(2026, 3, 1))])
    march = budget_status(b, e, date(2026, 3, 1), date(2026, 3, 31))
    assert march.iloc[0]["spent"] == 100


def test_empty_budget_and_expense_sets_are_safe():
    assert budget_status(make_budgets([]), make_expenses([]), date(2026, 3, 1), date(2026, 3, 31)).empty
    status = budget_status(make_budgets([("Rent", 500)]), make_expenses([]), date(2026, 3, 1), date(2026, 3, 31))
    assert list(status.columns) == BUDGET_STATUS_COLUMNS
    assert status.iloc[0]["utilization"] == 0


def test_duplicate_and_invalid_budgets_are_rejected():
    budgets.create_budget("Groceries", 1000)
    with pytest.raises(ValidationError):
        budgets.create_budget("Groceries", 2000)
    with pytest.raises(ValidationError):
        budgets.create_budget("Salary", 2000)
    with pytest.raises(ValidationError):
        budgets.create_budget("Rent", 0)


def test_goal_progress_and_monthly_contribution():
    prog = goal_progress(100000, 25000, date(2026, 11, 1), today=date(2026, 1, 1))
    assert prog.percent == pytest.approx(0.25)
    assert prog.remaining == 75000
    assert prog.months_left == 10
    assert prog.monthly_required == pytest.approx(7500)
    assert prog.status == "on_track"


def test_past_missing_and_completed_goal_dates():
    past = goal_progress(1000, 100, date(2025, 1, 1), today=date(2026, 1, 1))
    assert past.status == "overdue" and past.monthly_required is None
    undated = goal_progress(1000, 100, None, today=date(2026, 1, 1))
    assert undated.status == "no_date" and undated.monthly_required is None
    done = goal_progress(1000, 1000, None, today=date(2026, 1, 1))
    assert done.status == "completed" and done.monthly_required == 0


def test_goal_validation_and_lifecycle():
    with pytest.raises(ValidationError):
        goals.create_goal("Trip", 0)
    with pytest.raises(ValidationError):
        goals.create_goal("", 5000)
    with pytest.raises(ValidationError):
        goal_progress(0, 0, None)
    gid = goals.create_goal("Trip", 50000, 5000, date(2027, 1, 1))
    goals.update_goal_progress(gid, 15000)
    assert goals.list_goals().iloc[0]["current_amount"] == 15000
    assert goals.delete_goal(gid) is True
    assert list(goals.list_goals().columns) == GOAL_COLUMNS


def test_demo_data_never_touches_real_records():
    transactions.create_transaction({
        "title": "My real salary", "amount": 150000, "transaction_type": "income", "category": "Salary",
        "transaction_date": date(2026, 10, 1), "payment_method": "Bank Transfer", "description": "",
    })
    demo.load_demo_data(today=date(2026, 10, 25))
    counts = demo.record_counts()
    assert counts["real"] == 1 and counts["demo"] > 0
    assert "already loaded" in demo.load_demo_data(today=date(2026, 10, 25))
    removed = demo.reset_demo_data()
    assert removed > 0
    assert demo.record_counts() == {"real": 1, "demo": 0}
    assert budgets.list_budgets().empty


def test_insights_flag_overspending_and_are_labelled():
    cur = Summary(income=10000, expenses=9000, net=1000, savings_rate=0.1, transaction_count=5)
    prev = Summary(income=10000, expenses=6000, net=4000, savings_rate=0.4, transaction_count=5)
    cur_cats = pd.DataFrame([{"category": "Shopping", "amount": 9000.0, "share": 1.0}])
    prev_cats = pd.DataFrame([{"category": "Shopping", "amount": 6000.0, "share": 1.0}])
    items = generate_insights(cur, prev, cur_cats, prev_cats,
                              pd.DataFrame(columns=BUDGET_STATUS_COLUMNS),
                              pd.DataFrame(columns=GOAL_COLUMNS), date(2026, 10, 25))
    messages = " ".join(i.message for i in items)
    assert "higher than the previous period" in messages
    assert any(i.level == "warning" for i in items)
    assert all(i.basis in {"Historical", "Estimate"} for i in items)


def test_forecast_is_an_estimate_and_needs_history():
    result = forecast_next_month_expenses(pd.Series([10000, 12000, 14000, 16000]))
    assert result["estimate"] == pytest.approx(18000, rel=0.01)
    assert forecast_next_month_expenses(pd.Series([100, 200])) is None
