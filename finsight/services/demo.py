"""Sample (demo) data. Demo rows carry is_demo=True so they can be shown and reset separately.

Loading demo data only adds rows. Existing real records are never modified or removed.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import delete, func, select

from finsight.dates import month_bounds
from finsight.database import session_scope
from finsight.models import Budget, SavingsGoal, Transaction

DEMO_BUDGETS = {
    "Groceries": 25000.0,
    "Food & Dining": 15000.0,
    "Transport": 12000.0,
    "Shopping": 15000.0,
    "Entertainment": 5000.0,
    "Utilities": 10000.0,
}


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + delta
    return total // 12, total % 12 + 1


def _random_day(rng: random.Random, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def generate_demo_transactions(today: date, seed: int = 2026) -> list[dict]:
    """Deterministic sample transactions for the four months up to ``today``."""
    rng = random.Random(seed)
    rows: list[dict] = []

    def add(day: date, title: str, amount: float, txn_type: str, category: str, method: str) -> None:
        if day <= today:
            rows.append({
                "title": title,
                "amount": round(amount, 2),
                "transaction_type": txn_type,
                "category": category,
                "transaction_date": day,
                "payment_method": method,
                "description": "Sample data",
            })

    for back in range(3, -1, -1):
        year, month = _shift_month(today.year, today.month, -back)
        start, end = month_bounds(year, month)
        add(start, "Monthly salary", 185000, "income", "Salary", "Bank Transfer")
        add(start.replace(day=2), "Apartment rent", 65000, "expense", "Rent", "Bank Transfer")
        add(start.replace(day=3), "Savings transfer", 20000, "transfer", "Transfer", "Bank Transfer")
        add(start.replace(day=5), "Internet and streaming", 4500, "expense", "Bills & Subscriptions", "Credit Card")
        add(start.replace(day=10), "Electricity bill", rng.uniform(5000, 12000), "expense", "Utilities", "Bank Transfer")
        for _ in range(rng.randint(3, 5)):
            add(_random_day(rng, start, end), "Grocery run", rng.uniform(3500, 9000), "expense", "Groceries", "Debit Card")
        for _ in range(rng.randint(4, 8)):
            add(_random_day(rng, start, end), "Restaurant dinner", rng.uniform(900, 3500), "expense", "Food & Dining", "Credit Card")
        for _ in range(rng.randint(8, 12)):
            add(_random_day(rng, start, end), "Ride-hailing", rng.uniform(250, 900), "expense", "Transport", "Mobile Wallet")
        for _ in range(rng.randint(1, 3)):
            add(_random_day(rng, start, end), "Online shopping", rng.uniform(2000, 12000), "expense", "Shopping", "Credit Card")
        add(_random_day(rng, start, end), "Entertainment outing", rng.uniform(1000, 4000), "expense", "Entertainment", "Debit Card")
        if rng.random() < 0.5:
            add(_random_day(rng, start, end), "Pharmacy", rng.uniform(800, 3000), "expense", "Health", "Cash")
        if rng.random() < 0.6:
            add(_random_day(rng, start, end), "Freelance project payment", rng.uniform(20000, 60000), "income", "Freelance", "Bank Transfer")
    return rows


def load_demo_data(today: date | None = None) -> str:
    """Add demo transactions, budgets and savings goals. Refuses to run twice without a reset."""
    today = today or date.today()
    with session_scope() as session:
        existing = session.scalar(select(func.count(Transaction.id)).where(Transaction.is_demo.is_(True)))
        if existing:
            return "Demo data is already loaded. Reset demo data first if you want to reload it."
        rows = generate_demo_transactions(today)
        session.add_all([Transaction(**row, is_demo=True) for row in rows])
        existing_categories = set(session.scalars(select(Budget.category)).all())
        added_budgets = 0
        for category, limit in DEMO_BUDGETS.items():
            if category not in existing_categories:
                session.add(Budget(category=category, monthly_limit=limit, is_demo=True))
                added_budgets += 1
        session.add_all([
            SavingsGoal(name="Emergency fund", target_amount=300000.0, current_amount=120000.0,
                        target_date=today + timedelta(days=365), is_demo=True),
            SavingsGoal(name="Laptop upgrade", target_amount=250000.0, current_amount=60000.0,
                        target_date=today + timedelta(days=120), is_demo=True),
        ])
    return (f"Loaded {len(rows)} demo transactions, {added_budgets} demo budgets and 2 demo savings goals. "
            "Your own records were not changed.")


def reset_demo_data() -> int:
    """Delete only demo-flagged rows. Returns the number of records removed."""
    removed = 0
    with session_scope() as session:
        for model in (Transaction, Budget, SavingsGoal):
            result = session.execute(delete(model).where(model.is_demo.is_(True)))
            removed += result.rowcount or 0
    return removed


def record_counts() -> dict[str, int]:
    """Counts of real and demo transactions."""
    with session_scope() as session:
        real = session.scalar(select(func.count(Transaction.id)).where(Transaction.is_demo.is_(False))) or 0
        demo_count = session.scalar(select(func.count(Transaction.id)).where(Transaction.is_demo.is_(True))) or 0
    return {"real": int(real), "demo": int(demo_count)}
