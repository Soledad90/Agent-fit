"""Risk Management Skill.

Validates Risk/Reward ratio, calculates position sizing,
and enforces capital risk constraints.
"""

from __future__ import annotations

from typing import Any


class RiskManagementSkill:
    """Quản lý rủi ro: RR ≥ 1.5, risk ≤ 2% vốn, stoploss rõ ràng."""

    MIN_RR = 1.5
    MAX_CAPITAL_RISK_PCT = 0.02  # 2 %

    def run(
        self,
        signal_data: dict[str, Any],
        entry_zones: dict[str, str],
        win_patterns: dict[str, Any],
        capital: float = 100_000_000,
    ) -> dict[str, Any]:
        """Calculate stoploss, take-profit, RR, and position sizing.

        Args:
            signal_data: Parsed latest_signal.json.
            entry_zones: Output entry_zones dict from EntryOptimizationSkill.
            win_patterns: win_patterns dict from HistoricalPatternMiningSkill.
            capital: Total trading capital in VND (default 100 million VND).

        Returns:
            Dictionary with keys:
                - stoploss: str
                - take_profit: str
                - rr_ratio: str
                - max_position_size: str  (VND value)
                - probability: str
                - rr_valid: bool
        """
        price = signal_data.get("price")
        ma50 = signal_data.get("ma50")

        if price is None:
            return {
                "stoploss": "[Unverified]",
                "take_profit": "[Unverified]",
                "rr_ratio": "[Unverified]",
                "max_position_size": "[Unverified]",
                "probability": "[Unverified]",
                "rr_valid": False,
            }

        # Derive entry price from optimal zone (strip commas)
        optimal_str = entry_zones.get("optimal", "").replace(",", "")
        try:
            entry_price = float(optimal_str)
        except ValueError:
            entry_price = float(price)

        # Stoploss: below MA50 or 3% below entry
        if ma50 and ma50 < entry_price:
            stoploss = round(ma50 * 0.99)
        else:
            stoploss = round(entry_price * 0.97)

        risk_per_share = entry_price - stoploss
        if risk_per_share <= 0:
            return {
                "stoploss": f"{stoploss:,}",
                "take_profit": "[Unverified]",
                "rr_ratio": "[Unverified]",
                "max_position_size": "[Unverified]",
                "probability": "[Unverified]",
                "rr_valid": False,
            }

        # Take-profit: RR = 2.0 by default (historically achieved avg)
        avg_rr_historical = (
            win_patterns.get("avg_rr", 2.0) if win_patterns else 2.0
        )
        target_rr = max(avg_rr_historical, self.MIN_RR)
        take_profit = round(entry_price + risk_per_share * target_rr)

        # Actual RR achieved with this stoploss / take_profit
        achieved_rr = (take_profit - entry_price) / risk_per_share

        # Position sizing: risk ≤ 2% of capital
        max_risk_amount = capital * self.MAX_CAPITAL_RISK_PCT
        max_shares = int(max_risk_amount / risk_per_share)
        max_position_value = max_shares * entry_price

        # Win probability estimate based on historical win rate
        win_rate = win_patterns.get("avg_pnl_pct") if win_patterns else None
        probability = self._estimate_probability(win_patterns)

        rr_valid = achieved_rr >= self.MIN_RR

        return {
            "stoploss": f"{stoploss:,}",
            "take_profit": f"{take_profit:,}",
            "rr_ratio": f"{achieved_rr:.2f}",
            "max_position_size": f"{max_position_value:,} VND",
            "probability": probability,
            "rr_valid": rr_valid,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _estimate_probability(self, win_patterns: dict[str, Any] | None) -> str:
        """Estimate trade success probability from historical data."""
        if not win_patterns:
            return "[Unverified]"

        win_count = win_patterns.get("count", 0)
        avg_rr = win_patterns.get("avg_rr", 0)

        if win_count == 0:
            return "[Unverified]"

        # Simple Kelly-inspired estimate: higher avg_rr → higher probability weight
        if avg_rr >= 3.0:
            return "70–80%"
        if avg_rr >= 2.0:
            return "60–70%"
        if avg_rr >= self.MIN_RR:
            return "50–60%"
        return "< 50%"
