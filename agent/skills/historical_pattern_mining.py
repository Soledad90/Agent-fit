"""Historical Pattern Mining Skill.

Extracts winning trade patterns from trades.csv and compares
them with losing trades to derive entry conditions.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class HistoricalPatternMiningSkill:
    """Trích xuất pattern từ lịch sử giao dịch (trades.csv)."""

    # Columns expected in trades.csv
    REQUIRED_COLUMNS = {
        "date", "ticker", "entry_price", "rsi_at_entry",
        "volume_ratio", "trend", "result", "pnl_pct", "rr_achieved",
    }

    def run(self, trades_df: pd.DataFrame) -> dict[str, Any]:
        """Mine winning vs losing patterns.

        Args:
            trades_df: DataFrame loaded from trades.csv.

        Returns:
            Dictionary with keys:
                - win_rate: float (0–1)
                - win_patterns: dict with avg RSI, volume, trend distribution
                - loss_patterns: dict with avg RSI, volume, trend distribution
                - best_conditions: list of recommended entry conditions
                - total_trades: int
        """
        if trades_df is None or trades_df.empty:
            return {
                "win_rate": None,
                "win_patterns": {},
                "loss_patterns": {},
                "best_conditions": ["[Unverified] Không có dữ liệu lịch sử"],
                "total_trades": 0,
            }

        missing = self.REQUIRED_COLUMNS - set(trades_df.columns)
        if missing:
            return {
                "win_rate": None,
                "win_patterns": {},
                "loss_patterns": {},
                "best_conditions": [f"[Unverified] Thiếu cột: {missing}"],
                "total_trades": len(trades_df),
            }

        wins = trades_df[trades_df["result"] == "win"]
        losses = trades_df[trades_df["result"] == "loss"]

        total = len(trades_df)
        win_rate = len(wins) / total if total > 0 else 0.0

        win_patterns = self._summarise(wins)
        loss_patterns = self._summarise(losses)
        best_conditions = self._derive_conditions(win_patterns, loss_patterns)

        return {
            "win_rate": round(win_rate, 4),
            "win_patterns": win_patterns,
            "loss_patterns": loss_patterns,
            "best_conditions": best_conditions,
            "total_trades": total,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _summarise(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {}

        trend_dist: dict[str, int] = df["trend"].value_counts().to_dict()

        return {
            "count": len(df),
            "avg_rsi": round(float(df["rsi_at_entry"].mean()), 2),
            "avg_volume_ratio": round(float(df["volume_ratio"].mean()), 2),
            "avg_pnl_pct": round(float(df["pnl_pct"].mean()), 2),
            "avg_rr": round(float(df["rr_achieved"].mean()), 2),
            "trend_distribution": trend_dist,
        }

    def _derive_conditions(
        self,
        win_patterns: dict[str, Any],
        loss_patterns: dict[str, Any],
    ) -> list[str]:
        conditions: list[str] = []

        if not win_patterns:
            return ["[Unverified] Không đủ dữ liệu trade thắng"]

        avg_rsi_win = win_patterns.get("avg_rsi", 0)
        avg_vol_win = win_patterns.get("avg_volume_ratio", 0)
        trend_dist = win_patterns.get("trend_distribution", {})
        top_trend = max(trend_dist, key=lambda k: trend_dist[k]) if trend_dist else "unknown"

        conditions.append(f"RSI tại entry ≤ {avg_rsi_win:.1f} (avg thắng)")
        conditions.append(f"Volume ratio ≥ {avg_vol_win:.2f}x trung bình (avg thắng)")
        conditions.append(f"Trend: {top_trend} (phổ biến nhất trong trade thắng)")

        if loss_patterns:
            avg_rsi_loss = loss_patterns.get("avg_rsi", 100)
            if avg_rsi_loss > avg_rsi_win + 10:
                conditions.append(
                    f"Tránh entry khi RSI > {avg_rsi_loss - 5:.0f} "
                    f"(avg RSI trade thua: {avg_rsi_loss:.1f})"
                )

        return conditions
