# FinSight AI

A personal finance dashboard built with Streamlit, SQLite and SQLAlchemy. Track income, expenses,
monthly budgets and savings goals, analyse spending trends, and export CSV or PDF reports.
All data is stored locally. No paid APIs or cloud services are used.

## Features

- **Dashboard**: total balance, income, expenses, net savings, savings rate, charts, budget
  utilisation, recent transactions and rule-based insights.
- **Transactions**: full CRUD with confirmation before delete, search, filters (date, type,
  category, payment method), sorting, and CSV export.
- **Budgets**: monthly category budgets with progress bars, a warning at 80%, and an alert when exceeded.
- **Savings goals**: target and saved amounts, percent complete, remaining amount, and the estimated
  monthly contribution needed.
- **Analytics**: monthly income vs expenses, savings rate over time, category distribution, daily
  trend, and month-over-month comparison.
- **Reports**: monthly or custom-period summaries, CSV export, and PDF export (ReportLab).
- **Data management**: opening balance, load sample data, and reset sample data. Sample rows are
  labelled "Demo" and are the only rows a reset removes.

Balance formula: `opening balance + all income - all expenses`. Transfers are recorded but excluded
from income and expenses, so they are not double-counted.

Insights are labelled **Historical** (derived from recorded transactions) or **Estimate**
(forecast or illustrative figure). Forecasts are linear trend estimates, not guarantees.

## Setup (Windows PowerShell)

```powershell
cd finsight_ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```powershell
streamlit run app.py
```

Open the URL shown in the terminal (usually http://localhost:8501). On first run, go to
**Data management** and choose **Load demo data** to explore with sample PKR records, or start
adding your own transactions.

## Test

```powershell
pytest -q
```

Tests use a temporary SQLite database created per test. They never read or modify `data/finsight.db`.

## Project layout

```
app.py                  Streamlit entry point (navigation, sidebar period filter)
config.py               Constants: currency, categories, thresholds
finsight/
  database.py           Engine, sessions (commit or roll back), table creation
  models.py             SQLAlchemy models: Transaction, Budget, SavingsGoal, AppSetting
  validation.py         Input validation with readable errors
  formatting.py         Currency and percentage formatting
  dates.py              Month bounds, previous period, date filtering
  services/             Business logic, no Streamlit imports
    transactions.py     CRUD, filtering, CSV export
    calculations.py     Summary, balance, category breakdown
    analytics.py        Monthly and daily trends, month-over-month
    budgets.py          Budget CRUD and utilisation status
    goals.py            Goal CRUD and progress calculations
    insights.py         Rule-based insights
    forecast.py         Optional linear-trend forecast (scikit-learn)
    reports.py          PDF generation (ReportLab)
    demo.py             Sample data load and reset
    settings.py         Opening balance
  ui/
    components.py       Theme, metric cards, empty states, period selector
    charts.py           Plotly chart builders
    pages.py            Page renderers
tests/                  Pytest suite
examples/               Sample generated report
```

## Limitations

- Single currency (PKR). Multi-currency conversion is not implemented.
- No bank connection or import. Entries are manual or via CSV export.
- Forecasts use a simple linear trend and need at least three months of history.
- Budgets are evaluated against the calendar month containing the end of the selected period.
