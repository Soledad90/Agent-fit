"""Market Context & News Analysis Skill.

Provides a structured framework for evaluating:
1. Price & volume flow (buy/sell pressure)
2. News sentiment and credibility
3. Macro context (VN-Index, DXY, rates, oil, gold)

Works for ANY Vietnamese stock ticker — not limited to a single symbol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data-source registry
# ---------------------------------------------------------------------------

NEWS_SOURCES: dict[str, str] = {
    "cafef": "https://m.cafef.vn/",
    "vnexpress": "https://vnexpress.net/kinh-doanh",
    "dantri": "https://dantri.com.vn/kinh-doanh.htm",
    "telegram_quantin": "https://t.me/s/quantin",
}

PRICE_VOLUME_SOURCES: dict[str, str] = {
    "hsx": "https://www.hsx.vn/vi/",
    "24hmoney": "https://24hmoney.vn/stock/{ticker}/",
    "cafef_ticker": "https://m.cafef.vn/",
}

MACRO_INDICATORS = [
    "VN-Index",
    "VN30",
    "DXY",
    "USD/VND",
    "Lãi suất NHNN",
    "Giá dầu WTI/Brent",
    "Giá vàng (XAU/USD)",
    "US SPX / NDQ",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class VolumeFlowData:
    """Price & volume flow analysis for a ticker."""

    ticker: str
    last_close: float = 0.0
    change_pct: float = 0.0
    volume: int = 0
    avg_volume_20d: int = 0
    volume_ratio: float = 0.0  # volume / avg
    buy_active_pct: float = 0.0
    sell_active_pct: float = 0.0
    foreign_net: float = 0.0  # positive = net buy
    institutional_trades: str = ""  # notable block trades
    flow_bias: str = "neutral"  # buy_dominant | sell_dominant | neutral


@dataclass
class NewsItem:
    """A single news item with credibility assessment."""

    headline: str
    source: str
    date: str = ""
    sentiment: str = "neutral"  # positive | negative | neutral
    impact: str = "low"  # high | medium | low
    credibility: str = "medium"  # high | medium | low
    notes: str = ""


@dataclass
class MacroContext:
    """Macro environment snapshot."""

    vn_index: float = 0.0
    vn_index_change_pct: float = 0.0
    dxy: float = 0.0
    usd_vnd: float = 0.0
    interest_rate_direction: str = "stable"  # rising | falling | stable
    oil_price: float = 0.0
    gold_price: float = 0.0
    risk_environment: str = "neutral"  # risk_on | risk_off | neutral
    geopolitical_notes: str = ""


@dataclass
class MarketContextResult:
    """Full market-context analysis output."""

    ticker: str
    volume_flow: VolumeFlowData | None = None
    news_items: list[NewsItem] = field(default_factory=list)
    macro: MacroContext | None = None
    news_sentiment_score: float = 0.0  # -1.0 (bearish) to +1.0 (bullish)
    credibility_score: str = "medium"  # high | medium | low
    overall_assessment: str = "neutral"  # bullish | bearish | neutral | mixed


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class MarketContextAnalysisSkill:
    """Analyse price/volume flow, news, and macro context for a VN stock.

    This skill structures and evaluates externally-collected data.  It does
    not fetch data on its own — the caller supplies the raw inputs.

    Usage::

        skill = MarketContextAnalysisSkill()

        flow = VolumeFlowData(
            ticker="ACB",
            last_close=22600,
            change_pct=-2.16,
            volume=28_890_000,
            avg_volume_20d=12_490_000,
            buy_active_pct=47.85,
            sell_active_pct=52.15,
        )
        news = [
            NewsItem(headline="ACB Q1 LNTT +17%", source="cafef",
                     sentiment="positive", impact="high"),
        ]
        macro = MacroContext(vn_index=1855.66, dxy=98.47, ...)

        result = skill.run(flow, news, macro)
    """

    def run(
        self,
        volume_flow: VolumeFlowData,
        news_items: list[NewsItem],
        macro: MacroContext | None = None,
    ) -> dict[str, Any]:
        """Evaluate market context and return assessment."""
        ticker = volume_flow.ticker
        logger.info("[market_context] Analysing context for %s", ticker)

        # --- Volume-flow bias ---
        flow_bias = self._assess_flow(volume_flow)
        volume_flow.flow_bias = flow_bias

        # --- News sentiment ---
        sentiment_score = self._score_news(news_items)
        credibility = self._assess_credibility(news_items)

        # --- Overall ---
        overall = self._overall(flow_bias, sentiment_score, macro)

        result = MarketContextResult(
            ticker=ticker,
            volume_flow=volume_flow,
            news_items=news_items,
            macro=macro,
            news_sentiment_score=sentiment_score,
            credibility_score=credibility,
            overall_assessment=overall,
        )

        return _serialise(result)

    # ------------------------------------------------------------------

    @staticmethod
    def _assess_flow(flow: VolumeFlowData) -> str:
        """Determine buy/sell dominance from volume flow data."""
        flow.volume_ratio = (
            round(flow.volume / flow.avg_volume_20d, 2)
            if flow.avg_volume_20d > 0
            else 0.0
        )

        if flow.buy_active_pct >= 55:
            return "buy_dominant"
        if flow.sell_active_pct >= 55:
            return "sell_dominant"
        if flow.volume_ratio >= 2.0 and flow.change_pct < -1.5:
            return "sell_dominant"  # distribution
        if flow.volume_ratio >= 2.0 and flow.change_pct > 1.5:
            return "buy_dominant"  # accumulation / breakout
        return "neutral"

    @staticmethod
    def _score_news(items: list[NewsItem]) -> float:
        """Return a score from -1.0 (bearish) to +1.0 (bullish)."""
        if not items:
            return 0.0

        impact_weight = {"high": 3, "medium": 2, "low": 1}
        sentiment_val = {"positive": 1, "neutral": 0, "negative": -1}

        weighted_sum = 0.0
        total_weight = 0.0
        for item in items:
            w = impact_weight.get(item.impact, 1)
            s = sentiment_val.get(item.sentiment, 0)
            weighted_sum += w * s
            total_weight += w

        if total_weight == 0:
            return 0.0
        raw = weighted_sum / total_weight
        return round(max(-1.0, min(1.0, raw)), 2)

    @staticmethod
    def _assess_credibility(items: list[NewsItem]) -> str:
        """Aggregate credibility of news items."""
        if not items:
            return "low"
        scores = {"high": 3, "medium": 2, "low": 1}
        avg = sum(scores.get(i.credibility, 2) for i in items) / len(items)
        if avg >= 2.5:
            return "high"
        if avg >= 1.5:
            return "medium"
        return "low"

    @staticmethod
    def _overall(
        flow_bias: str,
        sentiment: float,
        macro: MacroContext | None,
    ) -> str:
        """Combine flow, news, and macro into overall assessment."""
        signals: list[int] = []

        # Flow
        if flow_bias == "buy_dominant":
            signals.append(1)
        elif flow_bias == "sell_dominant":
            signals.append(-1)
        else:
            signals.append(0)

        # News
        if sentiment >= 0.3:
            signals.append(1)
        elif sentiment <= -0.3:
            signals.append(-1)
        else:
            signals.append(0)

        # Macro
        if macro:
            if macro.risk_environment == "risk_on":
                signals.append(1)
            elif macro.risk_environment == "risk_off":
                signals.append(-1)
            else:
                signals.append(0)

        total = sum(signals)
        if total >= 2:
            return "bullish"
        if total <= -2:
            return "bearish"
        if any(s > 0 for s in signals) and any(s < 0 for s in signals):
            return "mixed"
        return "neutral"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialise(result: MarketContextResult) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ticker": result.ticker,
        "news_sentiment_score": result.news_sentiment_score,
        "credibility_score": result.credibility_score,
        "overall_assessment": result.overall_assessment,
    }
    if result.volume_flow:
        data["volume_flow"] = asdict(result.volume_flow)
    if result.news_items:
        data["news_items"] = [asdict(n) for n in result.news_items]
    if result.macro:
        data["macro"] = asdict(result.macro)
    return data
