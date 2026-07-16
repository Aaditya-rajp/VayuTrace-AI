from __future__ import annotations

import logging
from datetime import datetime
from html import escape
import os
from dotenv import load_dotenv

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from config import settings
from data.fallback_data import get_demo_pm25_history, get_demo_waqi_data
from data.open_meteo_client import fetch_open_meteo_history
from data.waqi_client import fetch_waqi_map_data
from modules.advisory import generate_multi_agent_advisory
from modules.forecasting import create_forecast_figure, evaluate_forecast
from modules.geospatial import generate_pollution_map, get_live_delhi_weather

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# UPDATE 1: Browser Tab Title
st.set_page_config(page_title="VayuTrace AI | Urban Air Intelligence", page_icon="🌬️", layout="wide")

# UPDATE 2: Autorefresh Cache Key
st_autorefresh(interval=1800 * 1000, key="vayutrace_refresh")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

    :root {
        --vs-bg: #14120F;
        --vs-panel: #1C1812;
        --vs-panel-alt: #221D15;
        --vs-border: #38311F;
        --vs-amber: #E8A33D;
        --vs-ochre: #C9723A;
        --vs-text: #EDE6D6;
        --vs-text-dim: #A69A80;
        --vs-text-faint: #6B6252;
    }

    #MainMenu, footer, header {visibility: hidden;}

    .stApp {
        background-color: var(--vs-bg);
        color: var(--vs-text);
        font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    [data-testid="stSidebar"] {
        background-color: var(--vs-panel);
        border-right: 1px solid var(--vs-border);
    }
    [data-testid="stSidebar"] * { font-family: 'IBM Plex Mono', monospace; }

    /* ---- Signature: station bulletin strip ---- */
    .vs-strip {
        display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 12px; letter-spacing: 0.5px; color: var(--vs-text-dim);
        border: 1px solid var(--vs-border);
        background: var(--vs-panel);
        padding: 9px 16px; border-radius: 4px; margin-bottom: 28px;
    }
    .vs-strip b { color: var(--vs-text); font-weight: 600; }
    .vs-dot {
        display: inline-block; width: 7px; height: 7px; border-radius: 50%;
        background: var(--vs-amber); margin-right: 6px;
        animation: vs-pulse 2.4s ease-in-out infinite;
    }
    @keyframes vs-pulse {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(232,163,61,0.5); }
        50% { opacity: 0.55; box-shadow: 0 0 0 4px rgba(232,163,61,0); }
    }
    @media (prefers-reduced-motion: reduce) { .vs-dot { animation: none; } }

    /* ---- Hero ---- */
    .vayu-hero { padding: 4px 0px 30px 0px; border-bottom: 1px solid var(--vs-border); margin-bottom: 30px; }
    .vayu-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: 44px; font-weight: 700; letter-spacing: -0.5px;
        color: var(--vs-text); margin: 0;
    }
    .vayu-title span { color: var(--vs-amber); }
    .vayu-subtitle {
        color: var(--vs-text-dim); font-size: 15.5px; margin-top: 10px;
        font-weight: 400; max-width: 760px; line-height: 1.6;
    }

    /* ---- KPI instrument cards (targeted via container key) ---- */
    div[class*="st-key-kpi-"] {
        background: var(--vs-panel) !important;
        border: 1px solid var(--vs-border) !important;
        border-top: 3px solid var(--vs-amber) !important;
        border-radius: 4px !important;
        padding: 4px 6px 2px 6px !important;
    }
    [data-testid="stMetric"] { background: transparent; padding: 10px 6px; }
    [data-testid="stMetricLabel"] {
        font-family: 'IBM Plex Mono', monospace;
        color: var(--vs-text-dim); font-size: 11.5px; font-weight: 600;
        text-transform: uppercase; letter-spacing: 1px;
    }
    [data-testid="stMetricValue"] {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700; font-size: 30px; color: var(--vs-text); padding-top: 2px;
    }
    [data-testid="stMetricDelta"] { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; }

    /* ---- Tabs styled as tuner ticks, not pill buttons ---- */
    .stTabs [data-baseweb="tab-list"] { gap: 28px; border-bottom: 1px solid var(--vs-border); }
    .stTabs [data-baseweb="tab"] {
        background: transparent; border: none; padding: 10px 2px;
        color: var(--vs-text-dim); font-weight: 500; font-size: 14.5px;
        font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.3px;
    }
    .stTabs [aria-selected="true"] {
        color: var(--vs-amber) !important;
        border-bottom: 2px solid var(--vs-amber) !important;
        background: transparent;
    }

    [data-testid="stDataFrame"] { border: 1px solid var(--vs-border); border-radius: 4px; overflow: hidden; }

    /* ---- Sidebar status LEDs ---- */
    .vs-led-row { display: flex; align-items: center; gap: 9px; font-size: 12.5px; margin: 6px 0; color: var(--vs-text-dim); }
    .vs-led { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .vs-led.on { background: #7FB069; box-shadow: 0 0 6px rgba(127,176,105,0.6); }
    .vs-led.off { background: #D65C4F; box-shadow: 0 0 6px rgba(214,92,79,0.6); }

    .vs-eyebrow {
        font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 1.5px;
        text-transform: uppercase; color: var(--vs-text-faint); margin-bottom: 6px;
    }

    /* ---- Rain / system banners ---- */
    .vs-banner {
        border: 1px solid var(--vs-border); border-left: 3px solid var(--vs-amber);
        background: var(--vs-panel-alt); padding: 12px 16px; border-radius: 4px;
        margin-bottom: 24px; color: var(--vs-text-dim); font-size: 13.5px;
        font-family: 'IBM Plex Sans', sans-serif;
    }
    .vs-banner b { color: var(--vs-text); }

    div.stButton > button, .stDownloadButton > button {
        font-family: 'IBM Plex Mono', monospace; font-size: 12.5px;
        background: var(--vs-panel-alt); color: var(--vs-text);
        border: 1px solid var(--vs-border);
    }
    div.stButton > button:hover { border-color: var(--vs-amber); color: var(--vs-amber); }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("<div class='vs-eyebrow'>System Status</div>", unsafe_allow_html=True)

gemini_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or settings.gemini_api_key.get_secret_value()
waqi_key = os.getenv("WAQI_API_KEY", "")

st.sidebar.markdown(
    f"""
    <div class="vs-led-row"><span class="vs-led {'on' if gemini_key else 'off'}"></span>AI ENGINE — {'ONLINE' if gemini_key else 'OFFLINE'}</div>
    <div class="vs-led-row"><span class="vs-led {'on' if waqi_key else 'off'}"></span>TELEMETRY — {'CONNECTED' if waqi_key else 'DISCONNECTED'}</div>
    """,
    unsafe_allow_html=True,
)

bounds = settings.city_bounds
st.sidebar.markdown(
    f"""
    <div style='font-size:11.5px; color:#6B6252; margin-top:14px; line-height:1.7;'>
    REGION &nbsp;{bounds['lat_min']}–{bounds['lat_max']}°N<br>
    FEEDS &nbsp;WAQI / OPEN-METEO CAMS
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("<hr style='border-color:#38311F; margin:18px 0;'>", unsafe_allow_html=True)
st.sidebar.markdown("<div class='vs-eyebrow'>System Control</div>", unsafe_allow_html=True)

if st.sidebar.button("🧹 Clear System Cache", width="stretch"):
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("🔄 Force Refresh", width="stretch"):
    st.rerun()
st.sidebar.link_button("📂 View on GitHub", "https://github.com/Aaditya-rajp/VayuTrace-AI.git", width="stretch")

st.markdown(
    f"""
    <div class="vs-strip">
        <span><span class="vs-dot"></span><b>STATION NCR-01</b></span>
        <span>SYNC {datetime.now().strftime('%H:%M:%S IST')}</span>
        <span>{bounds['lat_min']:.2f}°N {bounds.get('lon_min', 77.1):.2f}°E</span>
        <span>REFRESH CYCLE 30MIN</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# UPDATE 3: Hero Title 
st.markdown(
    """
    <div class="vayu-hero">
        <div class="vayu-title">Vayu<span>Trace</span> AI</div>
        <div class="vayu-subtitle">Enterprise atmospheric intelligence. Real-time telemetry, spatial attribution, and multi-agent GRAP policy enforcement for Delhi.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Synchronizing live telemetry..."):
    waqi_df = fetch_waqi_map_data()

avg_wind_spd, avg_wind_dir, is_raining = get_live_delhi_weather()

if is_raining:
    st.markdown(
        """
        <div class="vs-banner">
            🌧️ <b>Atmospheric Cleanse Active</b> — Precipitation detected over Delhi.
            Wet deposition math is currently scaling down PM2.5 persistence factors.
        </div>
        """,
        unsafe_allow_html=True,
    )

if waqi_df.empty:
    waqi_df = get_demo_waqi_data()
    st.markdown(
        """
        <div class="vs-banner" style="border-left-color:#D65C4F;">
            ⚠️ <b>SYSTEM NOTICE</b> — Live telemetry unreachable. Displaying local fallback data stream.
        </div>
        """,
        unsafe_allow_html=True,
    )

valid_aqi = waqi_df["aqi"].dropna()
if waqi_df.empty or valid_aqi.empty:
    st.error("🔴 No valid AQI readings available from live telemetry or the local fallback dataset. Dashboard cannot render.")
    st.stop()

city_avg = round(float(valid_aqi.mean()), 1)
worst_row = waqi_df.sort_values("aqi", ascending=False).iloc[0]
active_nodes = len(waqi_df)
worst_aqi = round(float(worst_row['aqi']))
aqi_color = "#00E400" if worst_aqi <= 50 else "#FFFF00" if worst_aqi <= 100 else "#FF7E00" if worst_aqi <= 150 else "#FF0000" if worst_aqi <= 200 else "#8F3F97" if worst_aqi <= 300 else "#7E0023"

kpi_a, kpi_b, kpi_c = st.columns(3)
with kpi_a.container(border=True, key="kpi-avg"):
    st.metric("City Average AQI", city_avg, f"Category: {worst_row['category']}", delta_color="off")
with kpi_b.container(border=True, key="kpi-critical"):
    st.metric("Critical Node", worst_row["name"], f"Max AQI: {worst_aqi}", delta_color="off")
with kpi_c.container(border=True, key="kpi-nodes"):
    st.metric("Active Sensors", active_nodes, "WAQI Network", delta_color="off")

st.markdown(f"<style>div[class*='st-key-kpi-critical'] {{ border-top-color: {aqi_color} !important; }}</style>", unsafe_allow_html=True)

tab_forecast, tab_geospatial, tab_advisory = st.tabs(["📈 24-72H FORECASTING", "🗺️ SPATIAL SOURCE ATTRIBUTION", "🛡️ AI HEALTH ADVISORY"])

with tab_forecast:
    station_names = waqi_df["name"].tolist()
    default_index = station_names.index(worst_row["name"]) if worst_row["name"] in station_names else 0
    selected_name = st.selectbox("Select target monitoring station:", station_names, index=default_index)
    
    selected_station = waqi_df[waqi_df["name"] == selected_name].iloc[0]
    station_name = escape(str(selected_station["name"]))
    
    try:
        live_aqi = float(selected_station["aqi"])
    except (ValueError, TypeError):
        live_aqi = None

    with st.spinner(f"Computing predictive atmospheric model for {station_name}..."):
        history_df = fetch_open_meteo_history(float(selected_station["latitude"]), float(selected_station["longitude"]), live_anchor_pm25=live_aqi)
        
        if not history_df.empty:
            fig = create_forecast_figure(history_df, station_name)
            st.plotly_chart(fig, width='stretch', key=f"forecast_chart_{selected_name}")
            
            metrics = evaluate_forecast(history_df)
            if metrics:
                col1, col2, col3 = st.columns(3)
                col1.metric("Average Prediction Error", f"± {metrics.get('mae', 0)} µg/m³")
                col2.metric("Worst-Case Variance", f"± {metrics.get('rmse', 0)} µg/m³")
                col3.metric("Historical Data Analyzed", f"{metrics.get('samples', 0)} Hours")
        else:
            st.error("Model failure: Insufficient baseline atmospheric data.")
            
        st.markdown("<div class='vs-eyebrow' style='margin-top:18px;'>Telemetry Datastream (Live &amp; Anchored)</div>", unsafe_allow_html=True)
        st.dataframe(waqi_df[["name", "aqi", "category", "source_hint", "last_updated"]], width="stretch", hide_index=True)

with tab_geospatial:
    if waqi_df.empty:
        st.error("Spatial engine offline: No telemetry available.")
    else:
        st.markdown(
            "<div class='vs-banner' style='margin-bottom:18px;'>Attributions are generated via Gaussian wind-vector mathematics and represent geometric probability, not causal certainty.</div>",
            unsafe_allow_html=True,
        )
        map_col, signal_col = st.columns([2.2, 1])

        with map_col:
            pollution_map = generate_pollution_map(waqi_df, avg_wind_spd, avg_wind_dir, is_raining)
            st.iframe(pollution_map._repr_html_(), height=650, width="stretch")

        with signal_col:
            st.markdown("<div class='vs-eyebrow'>Detected Anomalies</div>", unsafe_allow_html=True)
            st.dataframe(waqi_df[["name", "aqi", "category"]].sort_values("aqi", ascending=False).head(12), width="stretch", hide_index=True)

with tab_advisory:
    st.markdown(
        f"<div class='vs-eyebrow'>System Alert</div>"
        f"<div style='font-family:\"Space Grotesk\",sans-serif; font-size:22px; font-weight:600; color:{aqi_color}; margin-bottom:18px;'>AQI {worst_aqi} at {escape(str(worst_row['name']))}</div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Initializing multi-agent GRAP enforcement protocol..."):
        weather_payload = f"Speed: {avg_wind_spd:.1f} m/s, Heading: {avg_wind_dir}°"
        if is_raining: weather_payload += " | STATUS: ACTIVE PRECIPITATION (Rain Washout Active)"
            
        advisory = generate_multi_agent_advisory(str(worst_row["name"]), float(worst_row["aqi"]), weather_payload)

        analyst_txt = escape(str(advisory.get('analyst', 'Data unavailable.'))).replace('\n', '<br>')
        enforcement_txt = escape(str(advisory.get('enforcement', 'Action unavailable.'))).replace('\n', '<br>')
        hindi_txt = escape(str(advisory.get('hindi_translation', 'Translation unavailable.'))).replace('\n', '<br>')

        st.markdown(f"""
        <div style='background:#1C1812; border:1px solid #38311F; border-left:3px solid #E8A33D; padding:18px; border-radius:4px; margin-bottom:16px;'>
            <div style='color:#E8A33D; font-family:"IBM Plex Mono",monospace; font-size:11.5px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:10px;'>[NODE 01] Atmospheric Analyst</div>
            <div style='color:#EDE6D6; font-family:"IBM Plex Sans",sans-serif; font-size:14.5px; line-height:1.65;'>{analyst_txt}</div>
        </div>

        <div style='background:#1C1812; border:1px solid #38311F; border-left:3px solid #C9723A; padding:18px; border-radius:4px; margin-bottom:16px;'>
            <div style='color:#C9723A; font-family:"IBM Plex Mono",monospace; font-size:11.5px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:10px;'>[NODE 02] Tactical Enforcement (GRAP Compliant)</div>
            <div style='color:#EDE6D6; font-family:"IBM Plex Sans",sans-serif; font-size:14.5px; line-height:1.65;'>{enforcement_txt}</div>
        </div>

        <div style='background:#1C1812; border:1px solid #38311F; border-left:3px solid #7FB069; padding:18px; border-radius:4px; margin-bottom:16px;'>
            <div style='color:#7FB069; font-family:"IBM Plex Mono",monospace; font-size:11.5px; font-weight:600; text-transform:uppercase; letter-spacing:1.5px; margin-bottom:10px;'>[NODE 03] Public Broadcast (Hindi)</div>
            <div style='color:#EDE6D6; font-family:"IBM Plex Sans",sans-serif; font-size:14.5px; line-height:1.65;'>{hindi_txt}</div>
        </div>
        """, unsafe_allow_html=True)
