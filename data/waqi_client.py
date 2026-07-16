from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings

WAQI_BOUNDS_URL = "https://api.waqi.info/map/bounds/"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    return session


def get_aqi_category(aqi: float) -> str:
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def infer_source_hint(station_name: str, aqi: float) -> str:
    normalized = station_name.lower()
    if any(term in normalized for term in ["industrial", "anand vihar", "bawana", "mundka", "wazirpur", "okhla", "narela"]):
        return "Industrial and freight corridor signal"
    if any(term in normalized for term in ["road", "marg", "airport", "bus", "traffic", "ito", "ashram"]):
        return "Traffic exposure signal"
    if any(term in normalized for term in ["university", "school", "sector", "colony", "puram", "bagh", "vihar"]):
        return "Residential exposure signal"
    if aqi >= 200:
        return "Severe regional pollution signal"
    if aqi >= 150:
        return "Elevated urban background signal"
    return "Urban background signal"


def parse_station(row: dict[str, Any]) -> dict[str, Any] | None:
    station = row.get("station") or {}
    aqi = pd.to_numeric(row.get("aqi"), errors="coerce")
    latitude = pd.to_numeric(row.get("lat"), errors="coerce")
    longitude = pd.to_numeric(row.get("lon"), errors="coerce")

    if pd.isna(aqi) or pd.isna(latitude) or pd.isna(longitude):
        return None

    name = str(station.get("name") or f"WAQI Node {row.get('uid', 'Unknown')}").strip()
    numeric_aqi = float(aqi)

    return {
        "uid": row.get("uid"),
        "name": name,
        "aqi": round(numeric_aqi, 1),
        "latitude": float(latitude),
        "longitude": float(longitude),
        "category": get_aqi_category(numeric_aqi),
        "source_hint": infer_source_hint(name, numeric_aqi),
        "last_updated": station.get("time") or datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


@st.cache_data(ttl=900)
def fetch_waqi_map_data() -> pd.DataFrame:
    bounds = settings.city_bounds
    token = settings.waqi_api_key.get_secret_value()
    if not token:
        return pd.DataFrame()
    params = {
        "latlng": f"{bounds['lat_min']},{bounds['lon_min']},{bounds['lat_max']},{bounds['lon_max']}",
        "token": token,
    }

    try:
        response = get_session().get(WAQI_BOUNDS_URL, params=params, timeout=15)
        response.raise_for_status()
        payload = response.json()

        if payload.get("status") != "ok":
            logging.error("WAQI API returned non-ok status: %s", payload)
            return pd.DataFrame()

        rows = [parse_station(item) for item in payload.get("data", [])]
        df = pd.DataFrame([row for row in rows if row is not None])

        if df.empty:
            return df

        df = df.dropna(subset=["aqi", "latitude", "longitude"])
        df = df.sort_values("aqi", ascending=False).reset_index(drop=True)
        return df[["uid", "name", "aqi", "latitude", "longitude", "category", "source_hint", "last_updated"]]
    except Exception as exc:
        logging.error("WAQI telemetry fetch failed: %s", exc, exc_info=True)
        return pd.DataFrame()
