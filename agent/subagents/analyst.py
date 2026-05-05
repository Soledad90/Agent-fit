"""Analyst Sub-agent.

Scope: chart logic — reads latest_signal.json and equity_curve.csv
to provide technical indicator analysis (RSI, MA, volume).
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pandas as pd


class AnalystAgent:
    """Phân tích kỹ thuật: RSI, MA, volume."""

    def __init__(
        self,
        signal_path: str | Path,
        equity_path: str | Path,
    ) -> None:
        self.signal_path = Path(signal_path)
        self.equity_path = Path(equity_path)

    # ------------------------------------------------------------------
    # Signal data
    # ------------------------------------------------------------------

    def load_signal(self) -> dict[str, Any]:
        """Load and return parsed latest_signal.json."""
        if not self.signal_path.exists():
            return {}
        with open(self.signal_path, encoding="utf-8") as fh:
            return json.load(fh)

    # ------------------------------------------------------------------
    # Equity curve
    # ------------------------------------------------------------------

    def load_equity_curve(self) -> pd.DataFrame:
        """Load equity_curve.csv and return a typed DataFrame."""
        if not self.equity_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.equity_path, parse_dates=["date"])
        numeric_cols = ["equity", "daily_pnl", "drawdown_pct"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    # ------------------------------------------------------------------
    # Technical analysis helpers
    # ------------------------------------------------------------------

    def analyse(self) -> dict[str, Any]:
        """Return a technical analysis summary of the current signal.

        Returns:
            Dictionary with RSI interpretation, trend assessment,
            volume strength, and equity health.
        """
        signal = self.load_signal()
        equity_df = self.load_equity_curve()

        if not signal:
            return {"status": "no_signal_data"}

        rsi = signal.get("rsi")
        trend = signal.get("trend", "unknown")
        volume = signal.get("volume")
        avg_volume = signal.get("avg_volume_20d")
        price = signal.get("price")
        ma20 = signal.get("ma20")
        ma50 = signal.get("ma50")

        volume_ratio = (volume / avg_volume) if (volume and avg_volume) else None

        rsi_label = self._classify_rsi(rsi)
        volume_label = self._classify_volume(volume_ratio)
        trend_label = self._classify_trend(trend, price, ma20, ma50)

        # Equity health: latest drawdown
        equity_health = "unknown"
        if not equity_df.empty and "drawdown_pct" in equity_df.columns:
            latest_dd = float(equity_df["drawdown_pct"].iloc[-1])
            if latest_dd == 0:
                equity_health = "at_all_time_high"
            elif latest_dd < 5:
                equity_health = "healthy"
            elif latest_dd < 10:
                equity_health = "moderate_drawdown"
            else:
                equity_health = "severe_drawdown"

        return {
            "ticker": signal.get("ticker", "N/A"),
            "price": price,
            "rsi": rsi,
            "rsi_label": rsi_label,
            "volume_ratio": round(volume_ratio, 2) if volume_ratio else None,
            "volume_label": volume_label,
            "trend": trend,
            "trend_label": trend_label,
            "ma20": ma20,
            "ma50": ma50,
            "equity_health": equity_health,
        }

    # ------------------------------------------------------------------
    # Private classifiers
    # ------------------------------------------------------------------

    def _classify_rsi(self, rsi: float | None) -> str:
        if rsi is None:
            return "unknown"
        if rsi <= 30:
            return "oversold"
        if rsi <= 45:
            return "near_oversold"
        if rsi <= 55:
            return "neutral"
        if rsi <= 70:
            return "near_overbought"
        return "overbought"

    def _classify_volume(self, volume_ratio: float | None) -> str:
        if volume_ratio is None:
            return "unknown"
        if volume_ratio >= 2.0:
            return "strong"
        if volume_ratio >= 1.5:
            return "above_average"
        if volume_ratio >= 1.0:
            return "average"
        return "weak"

    def _classify_trend(
        self,
        trend: str,
        price: float | None,
        ma20: float | None,
        ma50: float | None,
    ) -> str:
        if trend == "uptrend":
            return "bullish"
        if trend == "downtrend":
            return "bearish"
        # Sideways: check price relative to MAs
        if price and ma20 and ma50:
            if price > ma20 > ma50:
                return "bullish_developing"
            if price < ma20 < ma50:
                return "bearish_developing"
        return "neutral"
