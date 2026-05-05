"""Strategy Builder Skill.

Combines multi-timeframe technical analysis with market-context analysis
to produce a concrete buy/sell strategy for any Vietnamese stock.

Output includes:
- 3 scenarios with probability estimates
- Entry zones with confirmation conditions
- Stop-loss and take-profit levels
- Risk/reward ratio
- Overall recommendation (BUY / OBSERVE / SELL)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Scenario:
    """A market scenario with probability estimate."""

    name: str  # e.g. "Tiếp tục giảm", "Hồi kỹ thuật", "Đảo chiều"
    probability_pct: int
    description: str
    action: str  # BUY | SELL | OBSERVE | NO_TRADE


@dataclass
class EntryZone:
    """A price zone for entering a position."""

    label: str  # "Entry 1", "Entry 2", etc.
    price_low: float
    price_high: float
    condition: str  # confirmation condition required
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    rr_ratio: float = 0.0


@dataclass
class Strategy:
    """Complete trading strategy output."""

    ticker: str
    exchange: str
    target_date: str
    current_price: float

    # Technical summary
    trend_1h: str = "unknown"
    trend_4h: str = "unknown"
    trend_1d: str = "unknown"
    trend_1w: str = "unknown"
    overall_trend: str = "unknown"
    trend_strength: str = "unknown"

    # Volume & flow
    flow_bias: str = "neutral"
    volume_signal: str = ""

    # News
    news_sentiment: str = "neutral"
    news_credibility: str = "medium"

    # Key levels
    supports: list[float] = field(default_factory=list)
    resistances: list[float] = field(default_factory=list)

    # Scenarios
    scenarios: list[Scenario] = field(default_factory=list)

    # Entry zones (for buyers)
    buy_entries: list[EntryZone] = field(default_factory=list)

    # Sell zones (for holders)
    sell_zones: list[dict[str, Any]] = field(default_factory=list)

    # Risk management
    max_position_pct: float = 30.0  # % of capital
    split_orders: int = 3
    risk_per_trade_pct: float = 2.0

    # Overall
    recommendation: str = "OBSERVE"  # BUY | OBSERVE | SELL
    confidence: str = "low"  # high | medium | low
    reason: str = ""


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class StrategyBuilderSkill:
    """Build a trading strategy from technical + context analysis.

    Usage::

        builder = StrategyBuilderSkill()
        strategy = builder.run(
            ticker="ACB",
            exchange="HOSE",
            target_date="2026-05-06",
            current_price=22600,
            multi_tf_result=multi_tf_dict,
            context_result=context_dict,
        )
    """

    def run(
        self,
        ticker: str,
        exchange: str,
        target_date: str,
        current_price: float,
        multi_tf_result: dict[str, Any],
        context_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine analysis results into actionable strategy."""
        logger.info(
            "[strategy_builder] Building strategy for %s:%s on %s",
            exchange,
            ticker,
            target_date,
        )

        strategy = Strategy(
            ticker=ticker,
            exchange=exchange,
            target_date=target_date,
            current_price=current_price,
        )

        # --- Extract technical data ---
        self._fill_technical(strategy, multi_tf_result)

        # --- Extract context data ---
        self._fill_context(strategy, context_result)

        # --- Generate scenarios ---
        strategy.scenarios = self._generate_scenarios(strategy)

        # --- Generate entry/sell zones ---
        strategy.buy_entries = self._generate_buy_entries(strategy)
        strategy.sell_zones = self._generate_sell_zones(strategy)

        # --- Overall recommendation ---
        strategy.recommendation, strategy.confidence, strategy.reason = (
            self._recommend(strategy)
        )

        return _serialise(strategy)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fill_technical(
        strategy: Strategy, tf: dict[str, Any]
    ) -> None:
        snapshots = tf.get("snapshots", {})
        for key, attr in [
            ("1H", "trend_1h"),
            ("4H", "trend_4h"),
            ("1D", "trend_1d"),
            ("1W", "trend_1w"),
        ]:
            snap = snapshots.get(key, {})
            setattr(strategy, attr, snap.get("trend", "unknown"))

        strategy.overall_trend = tf.get("overall_trend", "unknown")
        strategy.trend_strength = tf.get("trend_strength", "unknown")

        strategy.supports = tf.get("key_supports", [])
        strategy.resistances = tf.get("key_resistances", [])

    @staticmethod
    def _fill_context(
        strategy: Strategy, ctx: dict[str, Any]
    ) -> None:
        vf = ctx.get("volume_flow", {})
        strategy.flow_bias = vf.get("flow_bias", "neutral")

        vol_ratio = vf.get("volume_ratio", 0)
        change = vf.get("change_pct", 0)
        if vol_ratio >= 2.0 and change < -1.5:
            strategy.volume_signal = "distribution"
        elif vol_ratio >= 2.0 and change > 1.5:
            strategy.volume_signal = "accumulation"
        elif vol_ratio >= 1.5:
            strategy.volume_signal = "elevated"
        else:
            strategy.volume_signal = "normal"

        score = ctx.get("news_sentiment_score", 0)
        if score >= 0.3:
            strategy.news_sentiment = "positive"
        elif score <= -0.3:
            strategy.news_sentiment = "negative"
        else:
            strategy.news_sentiment = "neutral"

        strategy.news_credibility = ctx.get("credibility_score", "medium")

    @staticmethod
    def _generate_scenarios(strategy: Strategy) -> list[Scenario]:
        """Create 3 probability-weighted scenarios."""
        trend = strategy.overall_trend
        strength = strategy.trend_strength
        flow = strategy.flow_bias

        if trend == "downtrend" and strength in ("strong", "moderate"):
            return [
                Scenario(
                    name="Tiếp tục giảm",
                    probability_pct=55,
                    description="Xu hướng giảm tiếp, test hỗ trợ thấp hơn",
                    action="OBSERVE",
                ),
                Scenario(
                    name="Hồi kỹ thuật ngắn hạn",
                    probability_pct=30,
                    description="Bounce ngắn về vùng kháng cự rồi quay đầu",
                    action="SELL",
                ),
                Scenario(
                    name="Đảo chiều",
                    probability_pct=15,
                    description="Nến đảo chiều mạnh + volume xác nhận",
                    action="BUY",
                ),
            ]
        if trend == "uptrend" and strength in ("strong", "moderate"):
            return [
                Scenario(
                    name="Tiếp tục tăng",
                    probability_pct=55,
                    description="Xu hướng tăng tiếp, test kháng cự cao hơn",
                    action="BUY",
                ),
                Scenario(
                    name="Điều chỉnh ngắn hạn",
                    probability_pct=30,
                    description="Pullback về vùng hỗ trợ rồi tăng tiếp",
                    action="BUY",
                ),
                Scenario(
                    name="Đảo chiều giảm",
                    probability_pct=15,
                    description="Phá hỗ trợ quan trọng + volume lớn",
                    action="SELL",
                ),
            ]
        # Sideways / conflicting
        return [
            Scenario(
                name="Tiếp tục sideway",
                probability_pct=50,
                description="Giá dao động trong range, chưa có hướng rõ",
                action="OBSERVE",
            ),
            Scenario(
                name="Breakout tăng",
                probability_pct=25,
                description="Phá kháng cự + volume tăng",
                action="BUY",
            ),
            Scenario(
                name="Breakdown giảm",
                probability_pct=25,
                description="Phá hỗ trợ + volume tăng",
                action="SELL",
            ),
        ]

    @staticmethod
    def _generate_buy_entries(strategy: Strategy) -> list[EntryZone]:
        """Generate potential buy zones based on supports."""
        entries: list[EntryZone] = []
        price = strategy.current_price

        for i, sup in enumerate(strategy.supports[:2], start=1):
            if sup >= price:
                continue
            sl = round(sup * 0.97, -2)  # 3% below support
            tp1 = round(price * 1.03, -2)  # 3% above current price
            tp2 = (
                round(strategy.resistances[0], -2)
                if strategy.resistances
                else round(price * 1.05, -2)
            )

            risk = sup - sl
            reward = tp1 - sup
            rr = round(reward / risk, 2) if risk > 0 else 0.0

            entries.append(
                EntryZone(
                    label=f"Entry {i}",
                    price_low=round(sup * 0.99, -2),
                    price_high=round(sup * 1.01, -2),
                    condition="Nến rejection/hammer + volume giảm dần",
                    stop_loss=sl,
                    take_profit_1=tp1,
                    take_profit_2=tp2,
                    rr_ratio=rr,
                )
            )

        return entries

    @staticmethod
    def _generate_sell_zones(strategy: Strategy) -> list[dict[str, Any]]:
        """Generate sell zones for existing holders."""
        zones: list[dict[str, Any]] = []
        if strategy.resistances:
            zones.append(
                {
                    "zone": f"{strategy.resistances[0]:,.0f}",
                    "action": "Cân nhắc bán 30-50% vị thế",
                    "condition": "Giá hồi đến vùng kháng cự gần nhất",
                }
            )
        if strategy.supports:
            zones.append(
                {
                    "zone": f"{strategy.supports[0]:,.0f}",
                    "action": "Cắt lỗ nếu phá support",
                    "condition": "Nến đóng cửa dưới hỗ trợ + volume lớn",
                }
            )
        return zones

    @staticmethod
    def _recommend(
        strategy: Strategy,
    ) -> tuple[str, str, str]:
        """Produce the final recommendation."""
        trend = strategy.overall_trend
        strength = strategy.trend_strength
        flow = strategy.flow_bias
        news = strategy.news_sentiment

        # Strong downtrend + sell flow → OBSERVE
        if trend == "downtrend" and strength in ("strong", "moderate"):
            if flow == "sell_dominant":
                confidence = "high" if news != "positive" else "medium"
                return (
                    "OBSERVE",
                    confidence,
                    "Xu hướng giảm mạnh + dòng tiền bán > mua. "
                    "Chờ tín hiệu đảo chiều tại vùng hỗ trợ.",
                )
            confidence = "medium" if news != "positive" else "low"
            return (
                "OBSERVE",
                confidence,
                "Xu hướng giảm nhưng dòng tiền chưa quá tiêu cực. "
                "Theo dõi phản ứng tại hỗ trợ.",
            )

        # Strong uptrend + buy flow → BUY
        if trend == "uptrend" and strength in ("strong", "moderate"):
            if flow == "buy_dominant":
                confidence = "high" if news != "negative" else "medium"
                return (
                    "BUY",
                    confidence,
                    "Xu hướng tăng mạnh + dòng tiền mua chiếm ưu thế. "
                    "Tích lũy tại vùng pullback.",
                )
            confidence = "medium" if news != "negative" else "low"
            return (
                "BUY",
                confidence,
                "Xu hướng tăng nhưng dòng tiền chưa hoàn toàn xác nhận. "
                "Mua thận trọng, chia lệnh.",
            )

        # Otherwise → OBSERVE (news can nudge confidence)
        if news == "positive":
            return (
                "OBSERVE",
                "medium",
                "Tín hiệu kỹ thuật chưa rõ nhưng tin tức tích cực. "
                "Theo dõi breakout.",
            )
        if news == "negative":
            return (
                "OBSERVE",
                "low",
                "Tín hiệu kỹ thuật chưa rõ + tin tức tiêu cực. "
                "Chờ thêm dữ liệu xác nhận.",
            )
        return (
            "OBSERVE",
            "low",
            "Tín hiệu chưa rõ ràng. Chờ thêm dữ liệu xác nhận.",
        )


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------


def _serialise(strategy: Strategy) -> dict[str, Any]:
    data = asdict(strategy)
    data["scenarios"] = [asdict(s) for s in strategy.scenarios]
    data["buy_entries"] = [asdict(e) for e in strategy.buy_entries]
    return data
