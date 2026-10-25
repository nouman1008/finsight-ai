"""Plotly chart builders. Each returns None when there is no data, so pages can show an empty state."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

GREEN = "#10B981"
ROSE = "#F87171"
PALETTE = ["#10B981", "#34D399", "#2DD4BF", "#38BDF8", "#818CF8", "#F59E0B",
           "#F472B6", "#A3E635", "#94A3B8", "#FB7185", "#C084FC"]


def _style(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=28, b=8),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(color="#CBD5E1"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.12)")
    return fig


def income_vs_expense(monthly: pd.DataFrame) -> go.Figure | None:
    if monthly.empty:
        return None
    fig = go.Figure()
    fig.add_bar(x=monthly["month"], y=monthly["income"], name="Income", marker_color=GREEN,
                hovertemplate="%{y:,.0f}<extra>Income</extra>")
    fig.add_bar(x=monthly["month"], y=monthly["expense"], name="Expenses", marker_color=ROSE,
                hovertemplate="%{y:,.0f}<extra>Expenses</extra>")
    fig.update_layout(barmode="group")
    return _style(fig)


def category_donut(categories: pd.DataFrame) -> go.Figure | None:
    if categories.empty:
        return None
    fig = go.Figure(go.Pie(
        labels=categories["category"], values=categories["amount"], hole=0.62,
        marker=dict(colors=PALETTE), sort=False, textinfo="percent",
        hovertemplate="%{label}: %{value:,.0f}<extra></extra>",
    ))
    return _style(fig)


def category_bars(categories: pd.DataFrame) -> go.Figure | None:
    if categories.empty:
        return None
    fig = go.Figure(go.Bar(x=categories["amount"], y=categories["category"], orientation="h",
                           marker_color=GREEN, hovertemplate="%{x:,.0f}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _style(fig, height=max(260, 34 * len(categories) + 80))


def spending_trend(daily: pd.DataFrame) -> go.Figure | None:
    if daily.empty:
        return None
    fig = go.Figure()
    fig.add_scatter(x=daily["date"], y=daily["amount"], mode="markers", name="Daily",
                    marker=dict(color="#64748B", size=6), hovertemplate="%{y:,.0f}<extra>Daily</extra>")
    rolling = daily["amount"].rolling(7, min_periods=1).mean()
    fig.add_scatter(x=daily["date"], y=rolling, mode="lines", name="7-day average",
                    line=dict(color=GREEN, width=2.5), hovertemplate="%{y:,.0f}<extra>7-day avg</extra>")
    return _style(fig)


def savings_rate(rates: pd.DataFrame) -> go.Figure | None:
    if rates.empty or rates["savings_rate"].isna().all():
        return None
    fig = go.Figure(go.Scatter(x=rates["month"], y=rates["savings_rate"], mode="lines+markers",
                               line=dict(color=GREEN, width=2.5), connectgaps=False,
                               hovertemplate="%{y:.1%}<extra>Savings rate</extra>"))
    fig.update_yaxes(tickformat=".0%")
    return _style(fig)
