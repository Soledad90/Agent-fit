"""Signal Diagnosis Skill.

Reads latest_signal.json, identifies why signal is False,
and evaluates missing conditions (trend, volume, RSI).
"""

from __future__ import annotations

from typing import Any


class SignalDiagnosisSkill:
    """Phân tích trạng thái tín hiệu hiện tại."""

    # Thresholds for each condition check
    RSI_OVERSOLD_MAX = 45.0
    VOLUME_RATIO_MIN = 1.5  # current volume / avg_volume_20d
    VALID_TRENDS = {"uptrend"}

    def run(self, signal_data: dict[str, Any]) -> dict[str, Any]:
        """Analyse the signal snapshot and return a diagnosis report.

        Args:
            signal_data: Parsed content of latest_signal.json.

        Returns:
            Dictionary with keys:
                - signal_status: "ACTIVE" | "INACTIVE"
                - issues: list of human-readable problem descriptions
                - conditions: dict of individual condition evaluations
        """
        if not signal_data:
            return {
                "signal_status": "INACTIVE",
                "issues": ["[Unverified] Không có dữ liệu tín hiệu"],
                "conditions": {},
            }

        signal_active: bool = bool(signal_data.get("signal", False))

        # Evaluate individual conditions
        trend = signal_data.get("trend", "")
        rsi = signal_data.get("rsi")
        volume = signal_data.get("volume")
        avg_volume = signal_data.get("avg_volume_20d")
        price = signal_data.get("price")
        ma20 = signal_data.get("ma20")

        volume_ratio = (volume / avg_volume) if (volume and avg_volume) else None

        conditions: dict[str, bool | None] = {
            "trend_ok": trend in self.VALID_TRENDS,
            "rsi_ok": (rsi is not None and rsi <= self.RSI_OVERSOLD_MAX),
            "volume_ok": (volume_ratio is not None and volume_ratio >= self.VOLUME_RATIO_MIN),
            "price_above_ma20": (
                (price is not None and ma20 is not None and price > ma20)
                if (price is not None and ma20 is not None)
                else None
            ),
        }

        # Override with explicit conditions provided in the snapshot when present
        snapshot_conditions = signal_data.get("signal_conditions", {})
        for key, value in snapshot_conditions.items():
            if key in conditions:
                conditions[key] = value

        issues = self._build_issue_list(conditions, trend, rsi, volume_ratio)

        return {
            "signal_status": "ACTIVE" if signal_active else "INACTIVE",
            "issues": issues if issues else ["Tín hiệu đủ điều kiện"],
            "conditions": conditions,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_issue_list(
        self,
        conditions: dict[str, bool | None],
        trend: str,
        rsi: float | None,
        volume_ratio: float | None,
    ) -> list[str]:
        issues: list[str] = []

        if not conditions.get("trend_ok"):
            issues.append(
                f"Trend không hợp lệ: '{trend}' (cần uptrend)"
            )
        if not conditions.get("rsi_ok"):
            rsi_str = f"{rsi:.1f}" if rsi is not None else "[Unverified]"
            issues.append(
                f"RSI quá cao: {rsi_str} (cần ≤ {self.RSI_OVERSOLD_MAX})"
            )
        if not conditions.get("volume_ok"):
            vr_str = f"{volume_ratio:.2f}x" if volume_ratio is not None else "[Unverified]"
            issues.append(
                f"Volume yếu: {vr_str} trung bình (cần ≥ {self.VOLUME_RATIO_MIN}x)"
            )
        if not conditions.get("price_above_ma20"):
            issues.append("Giá dưới MA20 — chưa breakout")

        return issues
