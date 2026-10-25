from datetime import date

import pytest

from finsight.services import transactions
from finsight.services.transactions import TransactionFilter
from finsight.validation import ValidationError, parse_amount


def _txn(**overrides):
    base = {
        "title": "Groceries run", "amount": 2500, "transaction_type": "expense", "category": "Groceries",
        "transaction_date": date(2026, 3, 10), "payment_method": "Debit Card", "description": "",
    }
    base.update(overrides)
    return base


def test_crud_round_trip():
    txn_id = transactions.create_transaction(_txn())
    frame = transactions.list_transactions()
    assert len(frame) == 1 and frame.iloc[0]["title"] == "Groceries run"
    transactions.update_transaction(txn_id, _txn(title="Big groceries", amount=3000))
    assert transactions.get_transaction(txn_id)["amount"] == 3000
    assert transactions.delete_transaction(txn_id) is True
    assert transactions.list_transactions().empty
    assert transactions.delete_transaction(txn_id) is False


@pytest.mark.parametrize("bad_amount", [0, -10, "abc", float("nan")])
def test_invalid_amounts_are_rejected(bad_amount):
    with pytest.raises(ValidationError):
        transactions.create_transaction(_txn(amount=bad_amount))


def test_category_must_match_transaction_type():
    with pytest.raises(ValidationError):
        transactions.create_transaction(_txn(category="Salary"))


def test_required_title_and_reversed_date_range_are_rejected():
    with pytest.raises(ValidationError):
        transactions.create_transaction(_txn(title="   "))
    with pytest.raises(ValidationError):
        transactions.list_transactions(TransactionFilter(start=date(2026, 5, 1), end=date(2026, 4, 1)))


def test_date_filter_is_inclusive_and_sorting_works():
    transactions.create_transaction(_txn(transaction_date=date(2026, 1, 31), title="Jan"))
    transactions.create_transaction(_txn(transaction_date=date(2026, 2, 1), title="Feb early", amount=100))
    transactions.create_transaction(_txn(transaction_date=date(2026, 2, 28), title="Feb late", amount=900))
    feb = transactions.list_transactions(TransactionFilter(start=date(2026, 2, 1), end=date(2026, 2, 28)))
    assert set(feb["title"]) == {"Feb early", "Feb late"}
    by_amount = transactions.list_transactions(TransactionFilter(sort_by="amount", ascending=True))
    assert list(by_amount["title"])[0] == "Feb early"


def test_search_and_type_filters():
    transactions.create_transaction(_txn())
    transactions.create_transaction(_txn(title="Salary March", transaction_type="income", category="Salary",
                                         payment_method="Bank Transfer", amount=185000))
    found = transactions.list_transactions(TransactionFilter(search="salary"))
    assert list(found["title"]) == ["Salary March"]
    expenses_only = transactions.list_transactions(TransactionFilter(transaction_types=("expense",)))
    assert list(expenses_only["type"].unique()) == ["expense"]


def test_csv_export_has_header_and_rows():
    transactions.create_transaction(_txn())
    text = transactions.transactions_to_csv(transactions.list_transactions()).decode("utf-8")
    assert text.splitlines()[0].startswith("id,title,amount,type")
    assert "Groceries run" in text
    empty_text = transactions.transactions_to_csv(
        transactions.list_transactions(TransactionFilter(search="no-such-title"))).decode("utf-8")
    assert empty_text.splitlines()[0].startswith("id,title")
    assert len(empty_text.splitlines()) == 1


def test_parse_amount_rules():
    assert parse_amount("12.5") == 12.5
    assert parse_amount(0, allow_zero=True) == 0
    with pytest.raises(ValidationError):
        parse_amount(0)
