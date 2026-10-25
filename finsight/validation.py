"""Validation of user-entered data. Every function raises ValidationError with a readable message."""
from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import config


class ValidationError(ValueError):
    """Raised when user input fails validation."""


def parse_amount(value: Any, field: str = "Amount", allow_zero: bool = False) -> float:
    """Parse a finite money amount, rounded to two decimals."""
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be a number.") from exc
    if not math.isfinite(amount):
        raise ValidationError(f"{field} must be a finite number.")
    if (amount < 0) if allow_zero else (amount <= 0):
        requirement = "zero or positive" if allow_zero else "greater than zero"
        raise ValidationError(f"{field} must be {requirement}.")
    return round(amount, 2)


def require_text(value: Any, field: str, max_length: int) -> str:
    """Return stripped text, ensuring it is non-empty and within the length limit."""
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > max_length:
        raise ValidationError(f"{field} must be {max_length} characters or fewer.")
    return text


def parse_date(value: Any, field: str = "Date") -> date:
    """Accept date, datetime or ISO strings and return a date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError(f"{field} must be a valid date (YYYY-MM-DD).") from exc
    raise ValidationError(f"{field} is required.")


def validate_date_range(start: date, end: date) -> None:
    """Ensure a reporting range is ordered correctly."""
    if start > end:
        raise ValidationError("Start date must be on or before end date.")


def validate_transaction(data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalise a transaction payload for storage."""
    title = require_text(data.get("title"), "Title", config.TITLE_MAX_LENGTH)
    amount = parse_amount(data.get("amount"), "Amount")
    txn_type = str(data.get("transaction_type") or "").lower()
    if txn_type not in config.TRANSACTION_TYPES:
        raise ValidationError("Type must be income, expense or transfer.")
    category = str(data.get("category") or "")
    if category not in config.CATEGORIES_BY_TYPE[txn_type]:
        raise ValidationError(f"'{category}' is not a valid {txn_type} category.")
    payment_method = str(data.get("payment_method") or "")
    if payment_method not in config.PAYMENT_METHODS:
        raise ValidationError("Choose a valid payment method.")
    txn_date = parse_date(data.get("transaction_date"), "Date")
    description = str(data.get("description") or "").strip()[:500]
    return {
        "title": title,
        "amount": amount,
        "transaction_type": txn_type,
        "category": category,
        "transaction_date": txn_date,
        "payment_method": payment_method,
        "description": description,
    }
