"""Researcher Sub-agent.

Scope: trades.csv — loads and provides historical trade data
to the workflow for pattern mining.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class ResearcherAgent:
    """Phân tích dữ liệu lịch sử từ trades.csv."""

    def __init__(self, trades_path: str | Path) -> None:
        self.trades_path = Path(trades_path)

    def load(self) -> pd.DataFrame:
        """Load trades.csv and return a cleaned DataFrame.

        Returns:
            DataFrame with typed columns, or an empty DataFrame on error.
        """
        if not self.trades_path.exists():
            return pd.DataFrame()

        df = pd.read_csv(self.trades_path, parse_dates=["date"])

        numeric_cols = [
            "entry_price", "exit_price", "stoploss", "take_profit",
            "rsi_at_entry", "volume_ratio", "pnl_pct", "rr_achieved",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def summary(self) -> dict:
        """Return a quick summary of historical trade data."""
        df = self.load()
        if df.empty:
            return {"status": "no_data"}

        total = len(df)
        wins = int((df["result"] == "win").sum()) if "result" in df.columns else 0
        losses = total - wins
        win_rate = round(wins / total, 4) if total > 0 else 0.0

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
        }
