"""Optional expense forecast using a linear trend. Always reported as an estimate."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

MIN_MONTHS = 3


def forecast_next_month_expenses(monthly_expenses: pd.Series) -> dict[str, float] | None:
    """Estimate next month's spending from past monthly totals. Returns None with too little history."""
    values = pd.to_numeric(pd.Series(monthly_expenses), errors="coerce").dropna().astype(float).to_numpy()
    if len(values) < MIN_MONTHS:
        return None
    x = np.arange(len(values)).reshape(-1, 1)
    model = LinearRegression().fit(x, values)
    estimate = max(float(model.predict(np.array([[len(values)]]))[0]), 0.0)
    residual_std = float(np.std(values - model.predict(x)))
    return {
        "estimate": estimate,
        "low": max(estimate - residual_std, 0.0),
        "high": estimate + residual_std,
        "months_used": float(len(values)),
    }
