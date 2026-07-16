from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from prophet import Prophet


def prepare_model_data(df: pd.DataFrame) -> pd.DataFrame:
    model_df = df[["ds", "y"]].dropna().copy()
    model_df["ds"] = pd.to_datetime(model_df["ds"], errors="coerce")
    model_df["y"] = pd.to_numeric(model_df["y"], errors="coerce")
    model_df = model_df.dropna().drop_duplicates("ds").sort_values("ds").reset_index(drop=True)

    if not model_df.empty:
        q99 = model_df["y"].quantile(0.99)
        model_df = model_df[model_df["y"] <= q99]

    return model_df

def build_forecast(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 24:
        return pd.DataFrame()

    model_df = prepare_model_data(df)
    if len(model_df) < 24:            # ← re-check AFTER cleaning
        return pd.DataFrame()

    try:
        model = Prophet(
            changepoint_prior_scale=0.01,
            seasonality_prior_scale=0.1,
            daily_seasonality=True,
            weekly_seasonality=False,
            yearly_seasonality=False,
        )
        model.fit(model_df)
        future = model.make_future_dataframe(periods=72, freq="h")
        forecast = model.predict(future)
        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    except Exception as exc:
        import logging
        logging.error("Prophet fit/predict failed: %s", exc, exc_info=True)
        return pd.DataFrame()

def evaluate_forecast(df: pd.DataFrame, horizon: int = 72) -> dict[str, float | int]:
    model_df = prepare_model_data(df)
    if len(model_df) < horizon + 24:
        return {}

    train_df = model_df.iloc[:-horizon]
    actual_df = model_df.iloc[-horizon:]
    model = Prophet(
        changepoint_prior_scale=0.01,
        seasonality_prior_scale=0.1,
        daily_seasonality=True,
        weekly_seasonality=False,
        yearly_seasonality=False
    )
    model.fit(train_df)
    future = model.make_future_dataframe(periods=horizon, freq="h", include_history=False)
    predicted = model.predict(future)[["ds", "yhat"]]
    compared = actual_df.merge(predicted, on="ds", how="inner")

    if compared.empty:
        return {}

    errors = compared["y"] - compared["yhat"]
    return {
        "mae": round(float(errors.abs().mean()), 2),
        "rmse": round(float((errors.pow(2).mean()) ** 0.5), 2),
        "samples": int(len(compared)),
    }


def create_forecast_figure(history_df: pd.DataFrame, station_name: str) -> go.Figure:
    forecast_df = build_forecast(history_df)

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history_df["ds"],
            y=history_df["y"],
            mode="markers",
            name="Modeled PM2.5 history",
            marker={"color": "#9AE6B4", "size": 5, "opacity": 0.82},
        )
    )

    if not forecast_df.empty:
        figure.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat_upper"],
                mode="lines",
                line={"width": 0},
                showlegend=False,
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat_lower"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(255, 152, 0, 0.18)",
                line={"width": 0},
                name="Forecast uncertainty",
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat"],
                mode="lines",
                name="72h forecast",
                line={"color": "#FFB020", "width": 3},
            )
        )

    figure.update_layout(
        title=f"72h PM2.5 Forecast | {station_name}",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(10,14,18,0.88)",
        font={"color": "#E5E7EB"},
        margin={"l": 20, "r": 20, "t": 56, "b": 20},
        xaxis_title="Time",
        yaxis_title="PM2.5 µg/m³",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    figure.update_yaxes(rangemode="tozero")
    return figure