"""Streamlit page renderers. Calculations live in finsight.services; this module presents results."""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import TypeVar

import pandas as pd
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError

import config
from finsight.dates import filter_by_date, month_bounds, previous_month
from finsight.formatting import format_currency, format_percent
from finsight.services import analytics, budgets, calculations, demo, goals, insights, reports, settings, transactions
from finsight.services.transactions import TransactionFilter
from finsight.ui import charts
from finsight.ui.components import empty_state, metric_card
from finsight.validation import ValidationError

T = TypeVar("T")
PAGE_NAMES = ["Dashboard", "Transactions", "Budgets", "Savings goals", "Analytics", "Reports", "Data management"]
GOAL_STATUS_LABELS = {"completed": "Completed", "on_track": "On track",
                      "overdue": "Past target date", "no_date": "No target date"}


def _attempt(action: Callable[[], T]) -> tuple[bool, T | None]:
    """Run a data action, showing a readable message instead of a stack trace on failure."""
    try:
        return True, action()
    except ValidationError as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        st.error("A database error occurred. No changes were saved.")
    return False, None


def _show(fig, key: str) -> None:
    if fig is None:
        empty_state("No data for this chart in the selected range.")
    else:
        st.plotly_chart(fig, key=key)


def _signed(amount: float, txn_type: str) -> str:
    prefix = {"income": "+", "expense": "-"}.get(txn_type, "")
    return f"{prefix}{format_currency(abs(amount))}"


def display_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Presentation table: formatted dates and signed amounts, with a demo/real source column."""
    return pd.DataFrame({
        "Date": frame["date"].dt.strftime("%d %b %Y"),
        "Title": frame["title"],
        "Category": frame["category"],
        "Type": frame["type"].str.capitalize(),
        "Payment": frame["payment_method"],
        "Amount": [_signed(a, t) for a, t in zip(frame["amount"], frame["type"])],
        "Source": frame["is_demo"].map({True: "Demo", False: "Your data"}),
    })


def _render_budget_bars(status: pd.DataFrame, detailed: bool = False) -> None:
    if status.empty:
        empty_state("No budgets yet. Create a monthly category budget on the Budgets page.")
        return
    for row in status.itertuples(index=False):
        st.markdown(f"**{row.category}** · {format_currency(row.spent)} of {format_currency(row.monthly_limit)} "
                    f"· {format_percent(row.utilization)}")
        st.progress(min(float(row.utilization), 1.0))
        if row.status == "exceeded":
            st.error(f"Over budget by {format_currency(-row.remaining)}.")
        elif row.status == "warning":
            st.warning(f"At {config.BUDGET_WARNING_THRESHOLD:.0%} or more of budget. {format_currency(row.remaining)} remaining.")
        elif detailed:
            st.caption(f"{format_currency(row.remaining)} remaining")


def _insight_row(item: insights.Insight) -> None:
    show = {"info": st.info, "success": st.success, "warning": st.warning, "danger": st.error}[item.level]
    show(f"{item.message}\n\n*{item.basis}*")


# ---------------------------------------------------------------- Dashboard
def render_dashboard(start: date, end: date, label: str) -> None:
    st.title("Dashboard")
    st.caption(f"{date.today():%A, %d %B %Y}  ·  {label}: {start:%d %b %Y} to {end:%d %b %Y}")
    all_df = transactions.list_transactions()
    if all_df.empty:
        empty_state("Welcome to FinSight AI. Add your first transaction on the Transactions page, "
                    "or load sample data from Data management.")
        return

    period_df = filter_by_date(all_df, start, end)
    summary = calculations.summarize(period_df)
    balance = calculations.total_balance(all_df, settings.get_opening_balance())
    cards = st.columns(5)
    with cards[0]:
        metric_card("Total balance", format_currency(balance), "Opening balance plus all activity")
    with cards[1]:
        metric_card("Income", format_currency(summary.income), "Selected period")
    with cards[2]:
        metric_card("Expenses", format_currency(summary.expenses), "Selected period")
    with cards[3]:
        metric_card("Net savings", format_currency(summary.net), "Income minus expenses",
                    "pos" if summary.net >= 0 else "neg")
    with cards[4]:
        metric_card("Savings rate", format_percent(summary.savings_rate), "Net savings divided by income")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Income vs expenses")
        _show(charts.income_vs_expense(analytics.monthly_income_expense(period_df)), "dash_income")
    with right:
        st.subheader("Expense breakdown")
        _show(charts.category_donut(calculations.category_breakdown(period_df)), "dash_donut")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Spending trend")
        _show(charts.spending_trend(analytics.daily_expense_trend(period_df)), "dash_trend")
    with right:
        st.subheader("Budget utilisation")
        b_start, b_end = month_bounds(end.year, end.month)
        status = budgets.budget_status(budgets.list_budgets(), filter_by_date(all_df, b_start, b_end), b_start, b_end)
        _render_budget_bars(status)

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Recent transactions")
        recent = period_df.sort_values(["date", "id"], ascending=False).head(8)
        if recent.empty:
            empty_state("No transactions in this period.")
        else:
            st.dataframe(display_transactions(recent), hide_index=True)
    with right:
        st.subheader("Financial insights")
        for item in insights.period_insights(start, end):
            _insight_row(item)


# ---------------------------------------------------------------- Transactions
def _transaction_history(start: date, end: date) -> None:
    c1, c2, c3, c4 = st.columns(4)
    search = c1.text_input("Search by title", key="tx_search")
    types = c2.multiselect("Type", list(config.TRANSACTION_TYPES), key="tx_types",
                           format_func=str.capitalize)
    categories = c3.multiselect("Category", list(config.ALL_CATEGORIES), key="tx_categories")
    methods = c4.multiselect("Payment method", list(config.PAYMENT_METHODS), key="tx_methods")
    s1, s2 = st.columns(2)
    sort_by = s1.selectbox("Sort by", ["date", "amount"], key="tx_sort",
                           format_func=lambda v: "Date" if v == "date" else "Amount")
    order = s2.selectbox("Order", ["Newest or highest first", "Oldest or lowest first"], key="tx_order")

    flt = TransactionFilter(
        start=start, end=end, transaction_types=tuple(types), categories=tuple(categories),
        payment_methods=tuple(methods), search=search, sort_by=sort_by,
        ascending=order == "Oldest or lowest first",
    )
    frame = transactions.list_transactions(flt)
    if frame.empty:
        empty_state("No transactions match these filters. Widen the date range, clear filters, or add a transaction.")
    else:
        income = frame.loc[frame["type"] == "income", "amount"].sum()
        expenses = frame.loc[frame["type"] == "expense", "amount"].sum()
        st.caption(f"{len(frame)} transactions  ·  Income {format_currency(income)}  ·  Expenses {format_currency(expenses)}")
        st.dataframe(display_transactions(frame), hide_index=True)
    st.download_button("Export filtered CSV", data=transactions.transactions_to_csv(frame),
                       file_name=f"finsight_transactions_{start}_{end}.csv", mime="text/csv",
                       disabled=frame.empty, key="tx_export")


def _add_transaction_form() -> None:
    kind = st.radio("Type", list(config.TRANSACTION_TYPES), horizontal=True, key="add_type",
                    format_func=str.capitalize)
    with st.form("add_transaction_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        title = c1.text_input("Title", max_chars=config.TITLE_MAX_LENGTH)
        amount = c2.number_input("Amount (PKR)", min_value=0.0, step=100.0, format="%.2f")
        c3, c4, c5 = st.columns(3)
        category = c3.selectbox("Category", list(config.CATEGORIES_BY_TYPE[kind]))
        method = c4.selectbox("Payment method", list(config.PAYMENT_METHODS))
        when = c5.date_input("Date", value=date.today())
        description = st.text_area("Description (optional)", max_chars=500)
        submitted = st.form_submit_button("Save transaction", type="primary")
    if submitted:
        ok, _ = _attempt(lambda: transactions.create_transaction({
            "title": title, "amount": amount, "transaction_type": kind, "category": category,
            "payment_method": method, "transaction_date": when, "description": description,
        }))
        if ok:
            st.success("Transaction saved.")


def _edit_transaction_panel() -> None:
    all_df = transactions.list_transactions()
    if all_df.empty:
        empty_state("No transactions to edit yet.")
        return
    labels = {
        int(r.id): f"#{int(r.id)} · {r.date:%d %b %Y} · {r.title} · {format_currency(r.amount)}"
        for r in all_df.itertuples(index=False)
    }
    txn_id = st.selectbox("Select a transaction", list(labels), format_func=labels.get, key="edit_id")
    record = transactions.get_transaction(int(txn_id))
    if record is None:
        empty_state("That transaction no longer exists.")
        return
    kind = st.radio("Type", list(config.TRANSACTION_TYPES), horizontal=True, key=f"edit_type_{txn_id}",
                    index=list(config.TRANSACTION_TYPES).index(record["transaction_type"]),
                    format_func=str.capitalize)
    options = list(config.CATEGORIES_BY_TYPE[kind])
    with st.form(f"edit_form_{txn_id}"):
        c1, c2 = st.columns(2)
        title = c1.text_input("Title", value=record["title"], max_chars=config.TITLE_MAX_LENGTH)
        amount = c2.number_input("Amount (PKR)", min_value=0.0, value=float(record["amount"]), step=100.0, format="%.2f")
        c3, c4, c5 = st.columns(3)
        category = c3.selectbox("Category", options,
                                index=options.index(record["category"]) if record["category"] in options else 0)
        method = c4.selectbox("Payment method", list(config.PAYMENT_METHODS),
                              index=list(config.PAYMENT_METHODS).index(record["payment_method"])
                              if record["payment_method"] in config.PAYMENT_METHODS else 0)
        when = c5.date_input("Date", value=record["transaction_date"])
        description = st.text_area("Description (optional)", value=record["description"], max_chars=500)
        save = st.form_submit_button("Update transaction", type="primary")
    if save:
        ok, _ = _attempt(lambda: transactions.update_transaction(int(txn_id), {
            "title": title, "amount": amount, "transaction_type": kind, "category": category,
            "payment_method": method, "transaction_date": when, "description": description,
        }))
        if ok:
            st.success("Transaction updated.")

    st.markdown("#### Delete transaction")
    confirm = st.checkbox("I understand this transaction will be permanently deleted", key=f"confirm_txn_{txn_id}")
    if st.button("Delete transaction", disabled=not confirm, key=f"delete_txn_{txn_id}"):
        ok, _ = _attempt(lambda: transactions.delete_transaction(int(txn_id)))
        if ok:
            st.success("Transaction deleted. Refresh the History tab to see the change.")


def render_transactions(start: date, end: date, label: str) -> None:
    st.title("Transactions")
    st.caption(f"Filters start from the sidebar period: {label}, {start:%d %b %Y} to {end:%d %b %Y}.")
    history_tab, add_tab, edit_tab = st.tabs(["History", "Add transaction", "Edit or delete"])
    with history_tab:
        _transaction_history(start, end)
    with add_tab:
        _add_transaction_form()
    with edit_tab:
        _edit_transaction_panel()


# ---------------------------------------------------------------- Budgets
def _budget_create_form(budget_df: pd.DataFrame) -> None:
    st.subheader("Create a budget")
    taken = set(budget_df["category"]) if not budget_df.empty else set()
    available = [c for c in config.EXPENSE_CATEGORIES if c not in taken]
    if not available:
        st.info("Every expense category already has a budget.")
        return
    with st.form("create_budget_form", clear_on_submit=True):
        category = st.selectbox("Category", available)
        limit = st.number_input("Monthly limit (PKR)", min_value=0.0, step=500.0, format="%.0f")
        submitted = st.form_submit_button("Create budget", type="primary")
    if submitted:
        ok, _ = _attempt(lambda: budgets.create_budget(category, limit))
        if ok:
            st.success(f"Budget created for {category}.")


def _budget_edit_panel(budget_df: pd.DataFrame) -> None:
    st.subheader("Edit or delete a budget")
    if budget_df.empty:
        empty_state("No budgets to edit yet.")
        return
    names = dict(zip(budget_df["id"], budget_df["category"]))
    budget_id = int(st.selectbox("Budget", list(names), format_func=names.get, key="budget_pick"))
    current = float(budget_df.loc[budget_df["id"] == budget_id, "monthly_limit"].iloc[0])
    new_limit = st.number_input("Monthly limit (PKR)", min_value=0.0, value=current, step=500.0,
                                key=f"budget_limit_{budget_id}")
    if st.button("Save limit", key=f"save_budget_{budget_id}"):
        ok, _ = _attempt(lambda: budgets.update_budget_limit(budget_id, new_limit))
        if ok:
            st.success("Budget limit updated.")
    confirm = st.checkbox("I understand this budget will be deleted", key=f"confirm_budget_{budget_id}")
    if st.button("Delete budget", disabled=not confirm, key=f"delete_budget_{budget_id}"):
        ok, _ = _attempt(lambda: budgets.delete_budget(budget_id))
        if ok:
            st.success("Budget deleted.")


def render_budgets(start: date, end: date, label: str) -> None:
    st.title("Budgets")
    b_start, b_end = month_bounds(end.year, end.month)
    st.caption(f"Utilisation for {b_start:%B %Y}, the month containing {end:%d %b %Y}. "
               "Monthly limits apply to each calendar month.")
    budget_df = budgets.list_budgets()
    month_df = transactions.list_transactions(TransactionFilter(start=b_start, end=b_end))
    status = budgets.budget_status(budget_df, month_df, b_start, b_end)
    overview_tab, manage_tab = st.tabs(["Overview", "Manage budgets"])
    with overview_tab:
        if status.empty:
            empty_state("No budgets yet. Create one in the Manage budgets tab.")
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                metric_card("Total budgeted", format_currency(status["monthly_limit"].sum()), "Sum of monthly limits")
            with c2:
                metric_card("Total spent", format_currency(status["spent"].sum()), "Expenses this month")
            with c3:
                remaining = status["remaining"].sum()
                metric_card("Remaining", format_currency(remaining), "Across all budgets",
                            "neg" if remaining < 0 else "pos")
            _render_budget_bars(status, detailed=True)
    with manage_tab:
        _budget_create_form(budget_df)
        _budget_edit_panel(budget_df)


# ---------------------------------------------------------------- Savings goals
def _goal_create_form() -> None:
    with st.form("create_goal_form", clear_on_submit=True):
        name = st.text_input("Goal name", max_chars=120)
        c1, c2 = st.columns(2)
        target = c1.number_input("Target amount (PKR)", min_value=0.0, step=5000.0, format="%.0f")
        saved = c2.number_input("Already saved (PKR)", min_value=0.0, step=1000.0, format="%.0f")
        has_date = st.checkbox("Set a target date")
        target_date = st.date_input("Target date", value=date.today() + timedelta(days=180))
        submitted = st.form_submit_button("Create goal", type="primary")
    if submitted:
        ok, _ = _attempt(lambda: goals.create_goal(name, target, saved, target_date if has_date else None))
        if ok:
            st.success("Savings goal created.")


def _goal_card(row: pd.Series) -> None:
    target_date = row["target_date"] if isinstance(row["target_date"], date) else None
    progress = goals.goal_progress(float(row["target_amount"]), float(row["current_amount"]), target_date, date.today())
    goal_id = int(row["id"])
    with st.container(border=True):
        left, right = st.columns([3, 1])
        left.markdown(f"**{row['name']}**" + (" · Demo" if row["is_demo"] else ""))
        right.markdown(f"<div style='text-align:right;color:#8A9BB4'>{GOAL_STATUS_LABELS[progress.status]}</div>",
                       unsafe_allow_html=True)
        st.progress(min(max(progress.percent, 0.0), 1.0))
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Saved", format_currency(row["current_amount"]))
        m2.metric("Target", format_currency(row["target_amount"]))
        m3.metric("Remaining", format_currency(progress.remaining))
        m4.metric("Needed per month (estimate)",
                  "N/A" if progress.monthly_required is None else format_currency(progress.monthly_required))
        with st.expander("Update progress or delete"):
            new_saved = st.number_input("Current savings (PKR)", min_value=0.0, value=float(row["current_amount"]),
                                        step=1000.0, format="%.0f", key=f"goal_saved_{goal_id}")
            if st.button("Save progress", key=f"goal_save_{goal_id}"):
                ok, _ = _attempt(lambda: goals.update_goal_progress(goal_id, new_saved))
                if ok:
                    st.success("Progress updated.")
            confirm = st.checkbox("I understand this goal will be deleted", key=f"goal_confirm_{goal_id}")
            if st.button("Delete goal", disabled=not confirm, key=f"goal_delete_{goal_id}"):
                ok, _ = _attempt(lambda: goals.delete_goal(goal_id))
                if ok:
                    st.success("Goal deleted.")


def render_goals(start: date, end: date, label: str) -> None:
    st.title("Savings goals")
    st.caption("Progress uses the amount you have recorded as saved. Monthly figures are estimates, not guarantees.")
    goal_df = goals.list_goals()
    overview_tab, new_tab = st.tabs(["Your goals", "New goal"])
    with new_tab:
        _goal_create_form()
    with overview_tab:
        if goal_df.empty:
            empty_state("No savings goals yet. Create one in the New goal tab.")
        for _, row in goal_df.iterrows():
            _goal_card(row)


# ---------------------------------------------------------------- Analytics
def render_analytics(start: date, end: date, label: str) -> None:
    st.title("Analytics")
    st.caption(f"{label}: {start:%d %b %Y} to {end:%d %b %Y}. Charts follow the sidebar period.")
    all_df = transactions.list_transactions()
    period_df = filter_by_date(all_df, start, end)
    if period_df.empty:
        empty_state("No transactions in this date range.")
        return
    monthly = analytics.monthly_income_expense(period_df)
    left, right = st.columns(2)
    with left:
        st.subheader("Monthly income vs expenses")
        _show(charts.income_vs_expense(monthly), "an_monthly")
    with right:
        st.subheader("Savings rate over time")
        _show(charts.savings_rate(analytics.savings_rate_over_time(monthly)), "an_rate")
    left, right = st.columns(2)
    with left:
        st.subheader("Expense distribution by category")
        _show(charts.category_bars(calculations.category_breakdown(period_df)), "an_cats")
    with right:
        st.subheader("Daily spending trend")
        _show(charts.spending_trend(analytics.daily_expense_trend(period_df)), "an_daily")

    st.subheader("Month-over-month expenses")
    full_monthly = analytics.monthly_income_expense(all_df)
    changes = analytics.monthly_changes(full_monthly)
    if changes.empty:
        empty_state("Not enough history for month-over-month comparisons yet.")
    else:
        table = pd.DataFrame({
            "Month": changes["month"],
            "Expenses": changes["expense"].map(format_currency),
            "Change vs previous month": changes["change_pct"].map(lambda v: format_percent(v) if pd.notna(v) else "N/A"),
        })
        st.dataframe(table, hide_index=True)
    mom = analytics.month_over_month(all_df, end.year, end.month)
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card(f"Expenses {end:%B %Y}", format_currency(mom["current"]), "Month containing the period end")
    with c2:
        metric_card("Previous month", format_currency(mom["previous"]), "Same measure, prior month")
    with c3:
        metric_card("Change", format_percent(mom["change_pct"]),
                    f"{format_currency(mom['change'])} difference",
                    "neg" if (mom["change"] or 0) > 0 else "pos")


# ---------------------------------------------------------------- Reports
def render_reports(start: date, end: date, label: str) -> None:
    st.title("Reports")
    st.caption("Build a monthly summary or use the sidebar period, then export CSV or PDF.")
    today = date.today()
    months: list[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = previous_month(y, m)
    mode = st.radio("Report period", ["Monthly summary", "Sidebar period"], horizontal=True, key="report_mode")
    if mode == "Monthly summary":
        year_month = st.selectbox("Month", months, format_func=lambda v: f"{date(v[0], v[1], 1):%B %Y}",
                                  key="report_month")
        r_start, r_end = month_bounds(*year_month)
        r_label = f"{date(year_month[0], year_month[1], 1):%B %Y}"
    else:
        r_start, r_end, r_label = start, end, label

    frame = transactions.list_transactions(TransactionFilter(start=r_start, end=r_end))
    summary = calculations.summarize(frame)
    categories = calculations.category_breakdown(frame)
    cards = st.columns(4)
    with cards[0]:
        metric_card("Income", format_currency(summary.income), r_label)
    with cards[1]:
        metric_card("Expenses", format_currency(summary.expenses), r_label)
    with cards[2]:
        metric_card("Net savings", format_currency(summary.net), r_label, "pos" if summary.net >= 0 else "neg")
    with cards[3]:
        metric_card("Savings rate", format_percent(summary.savings_rate), r_label)
    if frame.empty:
        empty_state("No transactions in this period, so there is nothing to export yet.")
        return

    st.subheader("Category totals")
    if categories.empty:
        empty_state("No expenses in this period.")
    else:
        st.dataframe(pd.DataFrame({
            "Category": categories["category"],
            "Amount": categories["amount"].map(format_currency),
            "Share": categories["share"].map(format_percent),
        }), hide_index=True)

    st.subheader("Insights")
    items = insights.period_insights(r_start, r_end)
    for item in items:
        _insight_row(item)

    st.subheader("Export")
    stub = f"finsight_{r_start:%Y%m%d}_{r_end:%Y%m%d}"
    c1, c2 = st.columns(2)
    c1.download_button("Download transactions (CSV)", transactions.transactions_to_csv(frame),
                       file_name=f"{stub}.csv", mime="text/csv", key="dl_csv")
    with st.spinner("Preparing PDF report..."):
        pdf_bytes = reports.build_pdf_report(
            f"FinSight AI report: {r_label}", r_label, summary, categories, frame,
            [f"[{item.basis}] {item.message}" for item in items],
        )
    c2.download_button("Download PDF report", pdf_bytes, file_name=f"{stub}.pdf",
                       mime="application/pdf", key="dl_pdf")


# ---------------------------------------------------------------- Data management
def render_data(start: date, end: date, label: str) -> None:
    st.title("Data management")
    counts = demo.record_counts()
    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Your transactions", str(counts["real"]), "Entered by you")
    with c2:
        metric_card("Demo transactions", str(counts["demo"]), "Sample data, labelled Demo")
    with c3:
        metric_card("Database file", config.DATABASE_PATH.name, "Stored locally on this computer")

    st.subheader("Opening balance")
    st.caption("Total balance = opening balance + all recorded income - all recorded expenses. Transfers do not change it.")
    opening = st.number_input("Opening balance (PKR)", min_value=0.0, value=settings.get_opening_balance(),
                              step=1000.0, format="%.0f")
    if st.button("Save opening balance"):
        ok, _ = _attempt(lambda: settings.set_opening_balance(opening))
        if ok:
            st.success("Opening balance saved.")

    st.subheader("Sample data")
    st.write("Adds about four months of PKR transactions, six budgets and two savings goals, all marked Demo. "
             "Your existing records are never overwritten.")
    if st.button("Load demo data", type="primary"):
        ok, message = _attempt(demo.load_demo_data)
        if ok:
            st.success(message)

    st.subheader("Reset demo data")
    confirm = st.checkbox("Delete all demo transactions, budgets and goals. Your own records will not be touched.")
    if st.button("Reset demo data", disabled=not confirm):
        ok, removed = _attempt(demo.reset_demo_data)
        if ok:
            st.success(f"Removed {removed} demo records.")

    st.subheader("Currency")
    st.write(f"Display currency: **{config.DEFAULT_CURRENCY}**. This version stores and reports a single currency.")


RENDERERS: dict[str, Callable[[date, date, str], None]] = {
    "Dashboard": render_dashboard,
    "Transactions": render_transactions,
    "Budgets": render_budgets,
    "Savings goals": render_goals,
    "Analytics": render_analytics,
    "Reports": render_reports,
    "Data management": render_data,
}


def render(page: str, start: date, end: date, label: str) -> None:
    """Render the selected page."""
    RENDERERS[page](start, end, label)
