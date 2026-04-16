"""Executor Sub-agent.

Scope: entry timing and risk — assembles all skill outputs
and produces the final trade decision in the required JSON format.
"""

from __future__ import annotations

from typing import Any


class ExecutorAgent:
    """Đưa ra quyết định vào lệnh dựa trên tổng hợp phân tích."""

    MIN_RR = 1.5

    def decide(
        self,
        diagnosis: dict[str, Any],
        analysis: dict[str, Any],
        optimization: dict[str, Any],
        risk: dict[str, Any],
        pattern_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """Assemble all inputs and return a final trade decision.

        Args:
            diagnosis: Output of SignalDiagnosisSkill.
            analysis: Output of AnalystAgent.analyse().
            optimization: Output of EntryOptimizationSkill.
            risk: Output of RiskManagementSkill.
            pattern_summary: Full output of HistoricalPatternMiningSkill.

        Returns:
            JSON-serialisable dict matching the system's output_format schema.
        """
        signal_status = diagnosis.get("signal_status", "INACTIVE")
        issues = diagnosis.get("issues", [])
        signal_issue = "; ".join(issues) if issues else "N/A"

        entry_timing = optimization.get("entry_timing", "WAIT")
        entry_zones = optimization.get("entry_zones", {
            "optimal": "[Unverified]",
            "aggressive": "[Unverified]",
            "safe": "[Unverified]",
        })

        stoploss = risk.get("stoploss", "[Unverified]")
        take_profit = risk.get("take_profit", "[Unverified]")
        rr_ratio = risk.get("rr_ratio", "[Unverified]")
        probability = risk.get("probability", "[Unverified]")
        rr_valid = risk.get("rr_valid", False)

        # Final decision logic
        decision, reason = self._make_decision(
            signal_status=signal_status,
            entry_timing=entry_timing,
            rr_valid=rr_valid,
            analysis=analysis,
            optimization=optimization,
            pattern_summary=pattern_summary,
        )

        return {
            "signal_status": signal_status,
            "signal_issue": signal_issue,
            "entry_timing": entry_timing,
            "entry_zones": entry_zones,
            "stoploss": stoploss,
            "take_profit": take_profit,
            "rr_ratio": rr_ratio,
            "probability": probability,
            "decision": decision,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_decision(
        self,
        signal_status: str,
        entry_timing: str,
        rr_valid: bool,
        analysis: dict[str, Any],
        optimization: dict[str, Any],
        pattern_summary: dict[str, Any],
    ) -> tuple[str, str]:
        """Return (decision, reason)."""
        win_rate = pattern_summary.get("win_rate", 0)
        conditions = {}
        trend_ok = conditions.get("trend_ok", False)
        volume_label = analysis.get("volume_label", "weak")
        trend_label = analysis.get("trend_label", "neutral")

        reasons: list[str] = []

        # Gate 1: Signal must be active for immediate entry
        if signal_status == "INACTIVE":
            reasons.append(f"Tín hiệu INACTIVE: {optimization.get('reasoning', [])}")
            if entry_timing == "NOW":
                return "WAIT", "Tín hiệu chưa kích hoạt — giữ WAIT dù optimization đề xuất NOW"

        # Gate 2: RR must meet minimum threshold
        if not rr_valid:
            reasons.append(f"RR < {self.MIN_RR} — không đáp ứng điều kiện tối thiểu")
            return "NO TRADE", " | ".join(reasons) if reasons else "RR không đạt"

        # Gate 3: Volume confirmation
        if volume_label == "weak":
            reasons.append("Volume yếu — thiếu xác nhận")
            return "WAIT", " | ".join(reasons)

        # Gate 4: Trend must be bullish or developing bullish
        if trend_label in ("bearish", "bearish_developing"):
            reasons.append(f"Trend không thuận: {trend_label}")
            return "NO TRADE", " | ".join(reasons)

        # Gate 5: Historical win rate check
        if win_rate and win_rate < 0.5:
            reasons.append(
                f"Win rate lịch sử thấp ({win_rate:.0%}) — thận trọng"
            )
            return "WAIT", " | ".join(reasons)

        # All gates passed
        if entry_timing == "NOW":
            reasons.append("Tất cả điều kiện đạt — entry ngay")
            return "ENTER", " | ".join(reasons)

        if entry_timing == "WAIT_PULLBACK":
            reasons.append("Chờ pullback về vùng entry tối ưu")
            return "WAIT", " | ".join(reasons)

        reasons.append("Chờ xác nhận thêm trước khi vào lệnh")
        return "WAIT", " | ".join(reasons)
