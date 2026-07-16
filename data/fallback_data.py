from __future__ import annotations

import math

import pandas as pd


DEMO_STATIONS = [
    (101, "Anand Vihar, Delhi", 171.0, 28.6508, 77.3152, "Industrial and freight corridor signal"),
    (102, "Bawana, Delhi", 164.0, 28.7932, 77.0483, "Industrial and freight corridor signal"),
    (103, "ITO, Delhi", 151.0, 28.6286, 77.2410, "Traffic exposure signal"),
    (104, "R K Puram, Delhi", 139.0, 28.5633, 77.1869, "Residential exposure signal"),
    (105, "Sector 62, Noida", 132.0, 28.6245, 77.3577, "Residential exposure signal"),
    (106, "Lodhi Road, Delhi", 118.0, 28.5918, 77.2273, "Traffic exposure signal"),
    (107, "Gurugram Sector 51", 126.0, 28.4210, 77.0669, "Residential exposure signal"),
    (108, "Dwarka Sector 8, Delhi", 121.0, 28.5710, 77.0718, "Residential exposure signal"),
]


def get_demo_waqi_data() -> pd.DataFrame:
    rows = []
    for uid, name, aqi, latitude, longitude, source_hint in DEMO_STATIONS:
        if aqi <= 50:
            category = "Good"
        elif aqi <= 100:
            category = "Moderate"
        elif aqi <= 150:
            category = "Unhealthy for Sensitive Groups"
        elif aqi <= 200:
            category = "Unhealthy"
        elif aqi <= 300:
            category = "Very Unhealthy"
        else:
            category = "Hazardous"
        rows.append(
            {
                "uid": uid,
                "name": name,
                "aqi": aqi,
                "latitude": latitude,
                "longitude": longitude,
                "category": category,
                "source_hint": source_hint,
                "last_updated": "Demo snapshot",
            }
        )
    return pd.DataFrame(rows)


def get_demo_pm25_history(latitude: float, longitude: float) -> pd.DataFrame:
    timestamps = pd.date_range(end=pd.Timestamp.now().floor("h"), periods=336, freq="h")
    offset = int(abs(latitude * 100 + longitude * 100)) % 19
    values = []
    for index in range(len(timestamps)):
        hour = index % 24
        daily = 20 * math.cos((hour - 8) * math.pi / 12)
        weekly = 8 * math.sin(index * math.pi / 84)
        values.append(round(max(8.0, 78.0 + offset + daily + weekly), 2))
    return pd.DataFrame({"ds": timestamps, "y": values})
