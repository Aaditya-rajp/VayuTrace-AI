from __future__ import annotations

import unittest

import pandas as pd

from data.fallback_data import get_demo_pm25_history, get_demo_waqi_data
from data.open_meteo_client import parse_open_meteo_hourly
from data.waqi_client import get_aqi_category, parse_station
from modules.geospatial import get_aqi_color


class DataClientTests(unittest.TestCase):
    def test_parse_station_accepts_numeric_values(self) -> None:
        row = {
            "uid": 42,
            "aqi": "157",
            "lat": "28.61",
            "lon": "77.21",
            "station": {"name": "ITO Road, Delhi", "time": "2026-07-05 12:00"},
        }
        parsed = parse_station(row)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["aqi"], 157.0)
        self.assertEqual(parsed["category"], "Unhealthy")
        self.assertEqual(parsed["source_hint"], "Traffic exposure signal")

    def test_parse_station_rejects_invalid_aqi(self) -> None:
        self.assertIsNone(parse_station({"aqi": "-", "lat": 28.6, "lon": 77.2, "station": {}}))

    def test_open_meteo_parser_cleans_and_fills(self) -> None:
        hourly = {
            "time": ["2026-07-01T00:00", "2026-07-01T01:00", "invalid"],
            "pm2_5": [42.0, None, 99.0],
        }
        parsed = parse_open_meteo_hourly(hourly)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed.iloc[1]["y"], 42.0)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(parsed["ds"]))

    def test_aqi_categories_and_colors_match(self) -> None:
        self.assertEqual(get_aqi_category(50), "Good")
        self.assertEqual(get_aqi_category(151), "Unhealthy")
        self.assertEqual(get_aqi_color(50), "#4CAF50")
        self.assertEqual(get_aqi_color(201), "#8B0000")

    def test_demo_data_is_complete_and_labeled(self) -> None:
        stations = get_demo_waqi_data()
        history = get_demo_pm25_history(28.6, 77.2)
        self.assertGreaterEqual(len(stations), 8)
        self.assertEqual(len(history), 336)
        self.assertTrue(stations["last_updated"].eq("Demo snapshot").all())


if __name__ == "__main__":
    unittest.main()
