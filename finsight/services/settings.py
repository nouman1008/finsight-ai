"""Application settings stored in the database."""
from __future__ import annotations

from finsight.database import session_scope
from finsight.models import AppSetting
from finsight.validation import parse_amount

OPENING_BALANCE_KEY = "opening_balance"


def get_opening_balance() -> float:
    """The user's opening balance (defaults to zero)."""
    with session_scope() as session:
        row = session.get(AppSetting, OPENING_BALANCE_KEY)
        return float(row.value) if row else 0.0


def set_opening_balance(value: object) -> None:
    """Store the opening balance. Zero is allowed; negatives are not."""
    amount = parse_amount(value, "Opening balance", allow_zero=True)
    with session_scope() as session:
        row = session.get(AppSetting, OPENING_BALANCE_KEY)
        if row is None:
            session.add(AppSetting(key=OPENING_BALANCE_KEY, value=str(amount)))
        else:
            row.value = str(amount)
