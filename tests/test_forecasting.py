from __future__ import annotations

import math
import unittest

import pandas as pd

from modules.forecasting import build_forecast, evaluate_forecast


class ForecastingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        timestamps = pd.date_range("2026-06-01", periods=168, freq="h")
        values = [55 + 12 * math.sin(index * math.pi / 12) for index in range(168)]
        cls.history = pd.DataFrame({"ds": timestamps, "y": values})

    def test_forecast_has_expected_horizon_and_columns(self) -> None:
        forecast = build_forecast(self.history)
        self.assertEqual(len(forecast), len(self.history) + 72)
        self.assertEqual(list(forecast.columns), ["ds", "yhat", "yhat_lower", "yhat_upper"])

    def test_backtest_returns_metrics(self) -> None:
        metrics = evaluate_forecast(self.history)
        self.assertEqual(metrics["samples"], 72)
        self.assertGreaterEqual(metrics["mae"], 0)
        self.assertGreaterEqual(metrics["rmse"], metrics["mae"])


if __name__ == "__main__":
    unittest.main()
