from __future__ import annotations

from html import escape
import math
import requests

import streamlit as st
import folium
import pandas as pd
from folium.plugins import HeatMap

from config import settings
from modules.dispersion import calculate_plume_impact

INDUSTRIAL_REGISTRY = {
    "Anand Vihar (Transit/Industrial)": (28.6465, 77.3158),
    "Bawana (Manufacturing)": (28.7944, 77.0422),
    "Okhla (Industrial Estate)": (28.5284, 77.2721),
    "Narela (Industrial Area)": (28.8427, 77.0945),
    "Mundka (Plastics/Scrap)": (28.6811, 77.0270)
}

# 1. CACHE APPLIED: 15-minute TTL prevents API spam on every widget click
@st.cache_data(ttl=900)
def get_live_delhi_weather() -> tuple[float, float, bool]:
    """Bypasses WAQI API to fetch live macro wind vectors AND rain status directly from Open-Meteo."""
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&current_weather=true"
        response = requests.get(url, timeout=3)
        data = response.json()
        cw = data["current_weather"]
        
        is_raining = cw.get("weathercode", 0) in [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]
        
        return float(cw["windspeed"]), float(cw["winddirection"]), is_raining
    except Exception:
        return 2.5, 270.0, False 

def get_compass_direction(degrees: float) -> str:
    """Translates a 0-360 azimuth into a 16-point human-readable compass string."""
    dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 
            'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    return dirs[round(degrees / 22.5) % 16]

def get_aqi_color(aqi: float) -> str:
    if pd.isna(aqi): return "#475569" 
    if aqi <= 50: return "#00E400"    
    if aqi <= 100: return "#FFFF00"   
    if aqi <= 150: return "#FF7E00"   
    if aqi <= 200: return "#FF0000"   
    if aqi <= 300: return "#8F3F97"   
    return "#7E0023"                  

def get_marker_radius(aqi: float) -> float:
    if pd.isna(aqi): return 5.0
    return min(22.0, max(6.0, 5.0 + (float(aqi) / 20.0)))

# 2. SIGNATURE UPDATED: Now requires weather variables passed from app.py
def generate_pollution_map(df: pd.DataFrame, avg_wind_spd: float, avg_wind_dir: float, is_raining: bool) -> folium.Map:
    bounds = settings.city_bounds
    center_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2.0
    center_lon = (bounds["lon_min"] + bounds["lon_max"]) / 2.0

    pollution_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles="CartoDB dark_matter",
        control_scale=True,
        width="100%",
        height=650  
    )

    if df.empty:
        return pollution_map

    rain_tag = " (🌧️ Active Rain)" if is_raining else ""
    compass_heading = get_compass_direction(avg_wind_dir)

    travel_compass = (avg_wind_dir + 180) % 360 
    math_angle = (450 - travel_compass) % 360 
    
    spread = 15 
    length = min(0.25, max(0.10, avg_wind_spd * 0.04)) 

    for name, coords in INDUSTRIAL_REGISTRY.items():
        f_lat, f_lon = coords
        
        angle1 = math.radians(math_angle - spread)
        p2_lat = f_lat + (length * math.sin(angle1)) 
        p2_lon = f_lon + (length * math.cos(angle1))

        angle2 = math.radians(math_angle + spread)
        p3_lat = f_lat + (length * math.sin(angle2))
        p3_lon = f_lon + (length * math.cos(angle2))

        folium.CircleMarker(
            location=[f_lat, f_lon],
            radius=4, color='#94A3B8', weight=1, fill=True, fill_color='#00E5FF', fill_opacity=1.0,
            tooltip=f"⚠️ Known Source: {name}"
        ).add_to(pollution_map)

        folium.Polygon(
            locations=[[f_lat, f_lon], [p2_lat, p2_lon], [p3_lat, p3_lon]],
            color='#00E5FF', fill=True, fill_opacity=0.20, weight=1.5, dash_array='4, 6',
            tooltip=f"{name} Dispersion Path (Wind: {avg_wind_spd:.1f} m/s, Heading: {compass_heading} / {avg_wind_dir:.0f}°{rain_tag})"
        ).add_to(pollution_map)

    heat_data = []

    for _, row in df.dropna(subset=["latitude", "longitude"]).iterrows():
        aqi = row.get("aqi")
        color = get_aqi_color(aqi)
        radius = get_marker_radius(aqi)
        
        lat = float(row["latitude"])
        lon = float(row["longitude"])

        if pd.notna(aqi):
            heat_data.append([lat, lon, float(aqi)])

        attributed_source = escape(str(row.get("source_hint", "Urban background signal")))
        
        if pd.notna(aqi) and float(aqi) > 100:
            best_source = None
            max_impact = 0.0
            nearest_dist = float("inf")
            
            for factory_name, coords in INDUSTRIAL_REGISTRY.items():
                # --- NEW: NEAR-FIELD AMBIENT OVERRIDE ---
                # Calculate true distance in kilometers using flat-Earth projection
                dy = lat - coords[0]
                dx = (lon - coords[1]) * math.cos(math.radians(coords[0]))
                dist_km = math.sqrt(dx**2 + dy**2) * 111.32
                
                # If the station is within a 3.0km radius, local diffusion overrides wind vectors
                if dist_km <= 3.0:
                    nearest_dist = dist_km
                    best_source = factory_name
                    max_impact = 999.0  # Mathematical lock
                    continue
                    
                # --- FAR-FIELD GAUSSIAN MATH ---
                # Execute the Pasquill-Gifford physics engine for long-range transport
                impact = calculate_plume_impact(
                    source_lat=coords[0], source_lon=coords[1],
                    target_lat=lat, target_lon=lon,
                    wind_spd=avg_wind_spd, wind_dir=avg_wind_dir
                )
                
                if impact > max_impact:
                    max_impact = impact
                    best_source = factory_name
            
            if best_source and max_impact > 0.000001: 
                rain_washout_note = " <span style='color:#64748B;'>(Rain washout active)</span>" if is_raining else ""
                if max_impact == 999.0 and nearest_dist != float("inf"):
                    method_tag = f"Ambient Proximity ({nearest_dist:.2f} km)"
                else:
                    method_tag = "Gaussian Plume"
                attributed_source = f"<span style='color:#00E5FF; font-weight:700;'>⌖ Attributed to {best_source} ({method_tag})</span>{rain_washout_note}"

        station_name = escape(str(row.get("name", "Unknown")), quote=True).replace("\n", "").replace("\r", "")
        category = escape(str(row.get("category", "Unknown")), quote=True).replace("\n", "").replace("\r", "")
        last_updated = escape(str(row.get("last_updated", "Unknown")), quote=True).replace("\n", "").replace("\r", "")
        safe_aqi = str(aqi) if pd.notna(aqi) else "Offline"

        popup_html = (
            f"<div style='background-color:#0F172A; color:#E2E8F0; padding:14px; border-radius:8px; font-family:Inter,sans-serif; width:280px; border:1px solid #1E293B; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);'>"
            f"<h4 style='margin:0 0 10px 0; color:#F8FAFC; font-size:15px; border-bottom:1px solid #1E293B; padding-bottom:6px;'>{station_name}</h4>"
            f"<div style='margin-bottom:6px;'><span style='color:#64748B; font-size:12px; text-transform:uppercase;'>Current AQI</span><br><strong style='color:{color}; font-size:22px; line-height:1;'>{safe_aqi}</strong></div>"
            f"<div style='margin-bottom:6px; font-size:13px;'><span style='color:#94A3B8;'>Risk Level:</span> {category}</div>"
            f"<div style='margin-bottom:8px; font-size:13px;'><span style='color:#94A3B8;'>Signal:</span> {attributed_source}</div>"
            f"<div style='margin-top:10px; font-size:10px; color:#475569;'>Last Sync: {last_updated}</div>"
            f"</div>"
        )

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=f"{station_name} | AQI {safe_aqi}",
            color=color, fill=True, fill_color=color, fill_opacity=0.85, weight=1.0,
        ).add_to(pollution_map)

    if heat_data:
        HeatMap(
            heat_data, radius=24, blur=16, min_opacity=0.35, max_zoom=13,
            gradient={0.2: "#00E400", 0.4: "#FFFF00", 0.6: "#FF7E00", 0.8: "#FF0000", 0.95: "#8F3F97", 1.0: "#7E0023"},
        ).add_to(pollution_map)

    return pollution_map