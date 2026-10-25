"""Central application configuration."""
from pathlib import Path

APP_NAME = "FinSight AI"
TAGLINE = "Personal finance, clearly measured."
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "finsight.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

DEFAULT_CURRENCY = "PKR"
BUDGET_WARNING_THRESHOLD = 0.8
OVERSPEND_CHANGE_THRESHOLD = 0.10
CATEGORY_SPIKE_RATIO = 1.5
CATEGORY_SPIKE_MIN_INCREASE = 5000.0
TITLE_MAX_LENGTH = 120

TRANSACTION_TYPES = ("income", "expense", "transfer")
PAYMENT_METHODS = ("Cash", "Bank Transfer", "Debit Card", "Credit Card", "Mobile Wallet", "Other")
INCOME_CATEGORIES = ("Salary", "Freelance", "Business", "Investments", "Gifts", "Other")
EXPENSE_CATEGORIES = (
    "Rent", "Groceries", "Food & Dining", "Transport", "Utilities", "Bills & Subscriptions",
    "Shopping", "Health", "Education", "Entertainment", "Other",
)
TRANSFER_CATEGORIES = ("Transfer",)
CATEGORIES_BY_TYPE = {
    "income": INCOME_CATEGORIES,
    "expense": EXPENSE_CATEGORIES,
    "transfer": TRANSFER_CATEGORIES,
}
ALL_CATEGORIES = tuple(dict.fromkeys(INCOME_CATEGORIES + EXPENSE_CATEGORIES + TRANSFER_CATEGORIES))
