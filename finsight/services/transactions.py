"""Transaction CRUD operations, filtering and CSV export."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import select

from finsight.database import session_scope
from finsight.models import Transaction
from finsight.validation import ValidationError, validate_date_range, validate_transaction

COLUMNS = [
    "id", "title", "amount", "type", "category", "date", "payment_method",
    "description", "is_demo", "created_at",
]


@dataclass(frozen=True)
class TransactionFilter:
    """Criteria used to query stored transactions."""

    start: date | None = None
    end: date | None = None
    transaction_types: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    payment_methods: tuple[str, ...] = ()
    search: str = ""
    sort_by: str = "date"
    ascending: bool = False


def _to_frame(rows: list[Transaction]) -> pd.DataFrame:
    records = [
        {
            "id": t.id,
            "title": t.title,
            "amount": float(t.amount),
            "type": t.transaction_type,
            "category": t.category,
            "date": t.transaction_date,
            "payment_method": t.payment_method,
            "description": t.description or "",
            "is_demo": bool(t.is_demo),
            "created_at": t.created_at,
        }
        for t in rows
    ]
    frame = pd.DataFrame(records, columns=COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def list_transactions(flt: TransactionFilter | None = None) -> pd.DataFrame:
    """Return stored transactions matching the filter, as a DataFrame."""
    flt = flt or TransactionFilter()
    if flt.start and flt.end:
        validate_date_range(flt.start, flt.end)
    stmt = select(Transaction)
    if flt.start:
        stmt = stmt.where(Transaction.transaction_date >= flt.start)
    if flt.end:
        stmt = stmt.where(Transaction.transaction_date <= flt.end)
    if flt.transaction_types:
        stmt = stmt.where(Transaction.transaction_type.in_(flt.transaction_types))
    if flt.categories:
        stmt = stmt.where(Transaction.category.in_(flt.categories))
    if flt.payment_methods:
        stmt = stmt.where(Transaction.payment_method.in_(flt.payment_methods))
    term = flt.search.strip()
    if term:
        stmt = stmt.where(Transaction.title.ilike(f"%{term}%"))
    sort_column = Transaction.amount if flt.sort_by == "amount" else Transaction.transaction_date
    stmt = stmt.order_by(sort_column.asc() if flt.ascending else sort_column.desc(), Transaction.id.desc())
    with session_scope() as session:
        return _to_frame(list(session.scalars(stmt).all()))


def get_transaction(txn_id: int) -> dict[str, Any] | None:
    """Return one transaction as form-ready values, or None if it does not exist."""
    with session_scope() as session:
        txn = session.get(Transaction, txn_id)
        if txn is None:
            return None
        return {
            "title": txn.title,
            "amount": txn.amount,
            "transaction_type": txn.transaction_type,
            "category": txn.category,
            "transaction_date": txn.transaction_date,
            "payment_method": txn.payment_method,
            "description": txn.description or "",
        }


def create_transaction(data: Mapping[str, Any], is_demo: bool = False) -> int:
    """Validate and store a new transaction. Returns its ID."""
    clean = validate_transaction(data)
    with session_scope() as session:
        txn = Transaction(**clean, is_demo=is_demo)
        session.add(txn)
        session.flush()
        return int(txn.id)


def update_transaction(txn_id: int, data: Mapping[str, Any]) -> None:
    """Validate and apply changes to an existing transaction."""
    clean = validate_transaction(data)
    with session_scope() as session:
        txn = session.get(Transaction, txn_id)
        if txn is None:
            raise ValidationError("That transaction no longer exists.")
        for key, value in clean.items():
            setattr(txn, key, value)


def delete_transaction(txn_id: int) -> bool:
    """Delete a transaction. Returns False if it was already gone."""
    with session_scope() as session:
        txn = session.get(Transaction, txn_id)
        if txn is None:
            return False
        session.delete(txn)
        return True


def transactions_to_csv(frame: pd.DataFrame) -> bytes:
    """Serialise a transaction frame to UTF-8 CSV bytes (header only when empty)."""
    export = frame.copy()
    export["date"] = pd.to_datetime(export["date"]).dt.strftime("%Y-%m-%d")
    export["created_at"] = pd.to_datetime(export["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    return export.to_csv(index=False).encode("utf-8")
