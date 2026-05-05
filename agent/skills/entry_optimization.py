"""Entry Optimization Skill.

Compares pullback vs breakout approaches to determine the
best entry zone and timing recommendation.
"""

from __future__ import annotations

from typing import Any


class EntryOptimizationSkill:
    """Tối ưu điểm vào lệnh dựa trên phân tích kỹ thuật."""

    # Pullback depth relative to current price (configurable)
    PULLBACK_SHALLOW_PCT = 0.02   # 2% below current price
    PULLBACK_DEEP_PCT = 0.04      # 4% below current price
    BREAKOUT_BUFFER_PCT = 0.005   # 0.5% above MA20 for breakout confirmation

    def run(
        self,
        signal_data: dict[str, Any],
        diagnosis: dict[str, Any],
        win_patterns: dict[str, Any],
    ) -> dict[str, Any]:
        """Determine the optimal entry zone and timing.

        Args:
            signal_data: Parsed latest_signal.json.
            diagnosis: Output of SignalDiagnosisSkill.run().
            win_patterns: win_patterns dict from HistoricalPatternMiningSkill.run().

        Returns:
            Dictionary with keys:
                - entry_timing: "NOW" | "WAIT" | "WAIT_PULLBACK"
                - entry_zones: {optimal, aggressive, safe}
                - reasoning: list of reasoning steps
        """
        price = signal_data.get("price")
        ma20 = signal_data.get("ma20")
        ma50 = signal_data.get("ma50")

        if price is None:
            return {
                "entry_timing": "WAIT",
                "entry_zones": {
                    "optimal": "[Unverified]",
                    "aggressive": "[Unverified]",
                    "safe": "[Unverified]",
                },
                "reasoning": ["[Unverified] Thiếu dữ liệu giá"],
            }

        conditions = diagnosis.get("conditions", {})
        trend_ok = conditions.get("trend_ok", False)
        volume_ok = conditions.get("volume_ok", False)
        rsi_ok = conditions.get("rsi_ok", False)
        price_above_ma20 = conditions.get("price_above_ma20", False)

        # Derive support levels for entry zones
        support_shallow = round(price * (1 - self.PULLBACK_SHALLOW_PCT))
        support_deep = round(price * (1 - self.PULLBACK_DEEP_PCT))
        ma50_support = round(ma50) if ma50 else support_deep
        breakout_level = round(ma20 * (1 + self.BREAKOUT_BUFFER_PCT)) if ma20 else None

        reasoning: list[str] = []

        # Determine timing based on signal conditions
        all_conditions_met = trend_ok and volume_ok and rsi_ok and price_above_ma20
        partial_conditions = sum([trend_ok, volume_ok, rsi_ok]) >= 2

        if all_conditions_met:
            entry_timing = "NOW"
            optimal = f"{price:,}"
            aggressive = f"{support_shallow:,}"
            safe = f"{support_deep:,}"
            reasoning.append("Tất cả điều kiện đạt — entry ngay tại giá hiện tại")
        elif rsi_ok and not (trend_ok and volume_ok):
            # RSI favourable but trend/volume weak → wait for pullback to support
            entry_timing = "WAIT_PULLBACK"
            optimal = f"{support_shallow:,}"
            aggressive = f"{support_deep:,}"
            safe = f"{ma50_support:,}"
            reasoning.append("RSI hợp lệ nhưng thiếu xác nhận trend/volume")
            reasoning.append(
                f"Chờ pullback về {support_shallow:,} "
                f"(−{self.PULLBACK_SHALLOW_PCT*100:.0f}% từ giá hiện tại)"
            )
        elif partial_conditions and not all_conditions_met:
            entry_timing = "WAIT"
            optimal = (
                f"{breakout_level:,}" if breakout_level else f"{support_shallow:,}"
            )
            aggressive = f"{support_shallow:,}"
            safe = f"{support_deep:,}"
            reasoning.append("Điều kiện một phần đạt — chờ xác nhận breakout")
            if breakout_level:
                reasoning.append(f"Breakout entry: giá vượt {breakout_level:,}")
        else:
            entry_timing = "WAIT"
            optimal = f"{support_deep:,}"
            aggressive = f"{support_shallow:,}"
            safe = f"{ma50_support:,}"
            reasoning.append("Tín hiệu yếu — không đủ điều kiện để vào lệnh")

        # Incorporate historical win-pattern guidance
        if win_patterns:
            avg_rsi_win = win_patterns.get("avg_rsi")
            avg_vol_win = win_patterns.get("avg_volume_ratio")
            if avg_rsi_win:
                reasoning.append(
                    f"Lịch sử: trade thắng avg RSI = {avg_rsi_win:.1f}"
                )
            if avg_vol_win:
                reasoning.append(
                    f"Lịch sử: trade thắng avg volume ratio = {avg_vol_win:.2f}x"
                )

        return {
            "entry_timing": entry_timing,
            "entry_zones": {
                "optimal": optimal,
                "aggressive": aggressive,
                "safe": safe,
            },
            "reasoning": reasoning,
        }
