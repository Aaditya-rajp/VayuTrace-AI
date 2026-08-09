from __future__ import annotations

import logging
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from prophet import Prophet

logger = logging.getLogger(__name__)


def prepare_model_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "ds" not in df.columns or "y" not in df.columns:
        return pd.DataFrame()

    # Retain core time/target columns plus exogenous weather regressors if present
    feature_cols = [c for c in ["wind_speed", "temperature", "humidity"] if c in df.columns]
    target_cols = ["ds", "y"] + feature_cols

    model_df = df[target_cols].dropna().copy()
    model_df["ds"] = pd.to_datetime(model_df["ds"], errors="coerce")
    model_df["y"] = pd.to_numeric(model_df["y"], errors="coerce")

    for col in feature_cols:
        model_df[col] = pd.to_numeric(model_df[col], errors="coerce")

    model_df = model_df.dropna().drop_duplicates("ds").sort_values("ds").reset_index(drop=True)

    # Mild outlier filtering for top 1% physical spikes
    if len(model_df) > 30:
        q99 = model_df["y"].quantile(0.99)
        model_df = model_df[model_df["y"] <= q99].reset_index(drop=True)

    return model_df


def build_forecast(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 24:
        return pd.DataFrame()

    model_df = prepare_model_data(df)
    if len(model_df) < 24:
        return pd.DataFrame()

    try:
        # Increase changepoint_prior_scale to 0.15 so the trend bends dynamically across days
        # rather than forcing a rigid straight baseline with static repeating daily waves.
        model = Prophet(
            changepoint_prior_scale=0.15,
            seasonality_prior_scale=2.0,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=False,
        )

        # Higher fourier_order (6) captures dual diurnal peaks (morning rush + night inversion)
        model.add_seasonality(name="daily", period=1, fourier_order=6, prior_scale=2.0)

        # Dynamically register weather regressors if present in dataset
        feature_cols = [c for c in ["wind_speed", "temperature", "humidity"] if c in model_df.columns]
        for col in feature_cols:
            model.add_regressor(col)

        model.fit(model_df)

        future = model.make_future_dataframe(periods=72, freq="h")

        # Forward-fill regressor variables across the 72h forecast horizon
        for col in feature_cols:
            last_val = model_df[col].iloc[-1]
            future[col] = future[col].fillna(last_val)

        forecast = model.predict(future)

        # Physical constraint: PM2.5 concentration cannot be negative
        forecast["yhat"] = forecast["yhat"].clip(lower=0)
        forecast["yhat_lower"] = forecast["yhat_lower"].clip(lower=0)
        forecast["yhat_upper"] = forecast["yhat_upper"].clip(lower=0)

        return forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    except Exception as exc:
        logger.error("Prophet fit/predict failed: %s", exc, exc_info=True)
        return pd.DataFrame()


def evaluate_forecast(df: pd.DataFrame, horizon: int = 72) -> dict[str, float | int]:
    model_df = prepare_model_data(df)
    if len(model_df) < horizon + 24:
        return {}

    train_df = model_df.iloc[:-horizon]
    actual_df = model_df.iloc[-horizon:]

    try:
        model = Prophet(
            changepoint_prior_scale=0.15,
            seasonality_prior_scale=2.0,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=False,
        )
        model.add_seasonality(name="daily", period=1, fourier_order=6, prior_scale=2.0)

        feature_cols = [c for c in ["wind_speed", "temperature", "humidity"] if c in train_df.columns]
        for col in feature_cols:
            model.add_regressor(col)

        model.fit(train_df)

        future = model.make_future_dataframe(periods=horizon, freq="h", include_history=False)
        for col in feature_cols:
            future[col] = actual_df[col].values if col in actual_df.columns else train_df[col].iloc[-1]

        predicted = model.predict(future)[["ds", "yhat"]]
        predicted["yhat"] = predicted["yhat"].clip(lower=0)

        compared = actual_df.merge(predicted, on="ds", how="inner")

        if compared.empty:
            return {}

        errors = compared["y"] - compared["yhat"]
        return {
            "mae": round(float(errors.abs().mean()), 2),
            "rmse": round(float((errors.pow(2).mean()) ** 0.5), 2),
            "samples": int(len(compared)),
        }
    except Exception as exc:
        logger.error("Forecast evaluation failed: %s", exc, exc_info=True)
        return {}


def create_forecast_figure(history_df: pd.DataFrame, station_name: str) -> go.Figure:
    forecast_df = build_forecast(history_df)

    figure = go.Figure()

    # Modeled historical scatter points
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
        # Upper confidence bound
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
        # Lower confidence bound with shaded area fill
        figure.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat_lower"],
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(255, 176, 32, 0.15)",
                line={"width": 0},
                name="Forecast uncertainty",
                hoverinfo="skip",
            )
        )
        # Main forecast trend line
        figure.add_trace(
            go.Scatter(
                x=forecast_df["ds"],
                y=forecast_df["yhat"],
                mode="lines",
                name="72h forecast",
                line={"color": "#FFB020", "width": 2.5},
            )
        )

    figure.update_layout(
        title=f"72h PM2.5 Forecast | {station_name}",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(28,24,18,0.6)",
        font={"color": "#EDE6D6", "family": "IBM Plex Sans"},
        margin={"l": 20, "r": 20, "t": 56, "b": 20},
        xaxis_title="Time",
        yaxis_title="PM2.5 µg/m³",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        hovermode="x unified",
    )
    figure.update_yaxes(rangemode="tozero")
    return figure
