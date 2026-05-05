"""Multi-Timeframe Technical Analysis Skill.

Provides a structured framework for analysing Vietnamese stocks across
four mandatory timeframes: 1H, 4H, 1D, 1W.

The skill follows a top-down approach (Weekly → Daily → 4H → 1H) and
produces a consolidated trend assessment with support/resistance zones,
momentum signals, and an overall directional bias.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Timeframe definitions
# ---------------------------------------------------------------------------

TIMEFRAMES = ("1W", "1D", "4H", "1H")

TIMEFRAME_META: dict[str, dict[str, str]] = {
    "1W": {
        "label": "Weekly",
        "purpose": "Xu hướng dài hạn, vùng tích lũy lớn",
        "tradingview_interval": "1W",
        "lookback": "1-2 năm",
    },
    "1D": {
        "label": "Daily",
        "purpose": "Xu hướng chính, hỗ trợ/kháng cự quan trọng",
        "tradingview_interval": "1D",
        "lookback": "3-6 tháng",
    },
    "4H": {
        "label": "4-Hour",
        "purpose": "Swing ngắn hạn, xác nhận breakout/breakdown",
        "tradingview_interval": "4H",
        "lookback": "1-2 tháng",
    },
    "1H": {
        "label": "1-Hour",
        "purpose": "Scalping / entry chính xác trong phiên",
        "tradingview_interval": "1H",
        "lookback": "5-10 ngày",
    },
}

# Indicators applied on every timeframe
REQUIRED_INDICATORS = [
    {"name": "EMA", "periods": [20, 50, 200], "purpose": "Xu hướng ngắn/trung/dài"},
    {"name": "RSI", "period": 14, "overbought": 70, "oversold": 30},
    {"name": "MACD", "fast": 12, "slow": 26, "signal": 9},
    {"name": "Volume", "compare_to": "avg_20d"},
    {"name": "Bollinger Bands", "period": 20, "std_dev": 2},
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TimeframeSnapshot:
    """Technical state for a single timeframe."""

    timeframe: str
    trend: str = "unknown"  # uptrend | downtrend | sideways
    price_vs_ema20: str = "unknown"  # above | below | at
    price_vs_ema50: str = "unknown"
    price_vs_ema200: str = "unknown"
    rsi: float | None = None
    macd_histogram: str = "unknown"  # rising | falling | flat
    volume_vs_avg: str = "unknown"  # above | below | at
    volume_ratio: float | None = None
    candle_pattern: str = "none"
    support_levels: list[float] = field(default_factory=list)
    resistance_levels: list[float] = field(default_factory=list)
    notes: str = ""


@dataclass
class MultiTimeframeResult:
    """Consolidated multi-timeframe analysis result."""

    ticker: str
    exchange: str  # HOSE | HNX | UPCOM
    snapshots: dict[str, TimeframeSnapshot] = field(default_factory=dict)
    overall_trend: str = "unknown"
    trend_alignment: int = 0  # 0-4: how many TFs agree
    trend_strength: str = "unknown"  # strong | moderate | weak | conflicting
    key_supports: list[float] = field(default_factory=list)
    key_resistances: list[float] = field(default_factory=list)
    bias: str = "neutral"  # bullish | bearish | neutral


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


class MultiTimeframeAnalysisSkill:
    """Analyse a VN stock across 1H, 4H, 1D, 1W timeframes.

    This skill does **not** fetch live data on its own — it structures and
    evaluates data that has been collected externally (e.g. via TradingView
    screenshots, web scraping, or API calls).

    Usage::

        skill = MultiTimeframeAnalysisSkill()

        # Build snapshots from externally collected data
        snapshots = {
            "1W": TimeframeSnapshot(timeframe="1W", trend="downtrend", ...),
            "1D": TimeframeSnapshot(timeframe="1D", trend="downtrend", ...),
            "4H": TimeframeSnapshot(timeframe="4H", trend="downtrend", ...),
            "1H": TimeframeSnapshot(timeframe="1H", trend="sideways", ...),
        }

        result = skill.run("ACB", "HOSE", snapshots)
    """

    def run(
        self,
        ticker: str,
        exchange: str,
        snapshots: dict[str, TimeframeSnapshot],
    ) -> dict[str, Any]:
        """Evaluate multi-timeframe data and return consolidated analysis."""
        logger.info(
            "[multi_timeframe] Analysing %s:%s across %d timeframes",
            exchange,
            ticker,
            len(snapshots),
        )

        missing = [tf for tf in TIMEFRAMES if tf not in snapshots]
        if missing:
            logger.warning("[multi_timeframe] Missing timeframes: %s", missing)

        # --- Trend alignment ---
        trends = [snapshots[tf].trend for tf in TIMEFRAMES if tf in snapshots]
        dominant = _dominant_trend(trends)
        alignment = sum(1 for t in trends if t == dominant)
        strength = _trend_strength(alignment, len(trends))

        # --- Aggregate supports / resistances ---
        all_supports: list[float] = []
        all_resistances: list[float] = []
        for tf in TIMEFRAMES:
            snap = snapshots.get(tf)
            if snap:
                all_supports.extend(snap.support_levels)
                all_resistances.extend(snap.resistance_levels)

        key_supports = sorted(set(all_supports), reverse=True)[:5]
        key_resistances = sorted(set(all_resistances))[:5]

        # --- Bias ---
        bias = _compute_bias(dominant, alignment, len(trends))

        result = MultiTimeframeResult(
            ticker=ticker,
            exchange=exchange,
            snapshots=snapshots,
            overall_trend=dominant,
            trend_alignment=alignment,
            trend_strength=strength,
            key_supports=key_supports,
            key_resistances=key_resistances,
            bias=bias,
        )

        return _serialise(result)

    @staticmethod
    def tradingview_url(ticker: str, exchange: str = "HOSE") -> str:
        """Return the TradingView chart URL for a VN stock."""
        return (
            f"https://www.tradingview.com/chart/"
            f"?symbol={exchange}%3A{ticker}"
        )

    @staticmethod
    def data_sources(ticker: str, exchange: str = "HOSE") -> dict[str, str]:
        """Return standard data-source URLs for a VN ticker."""
        return {
            "tradingview": f"https://www.tradingview.com/chart/?symbol={exchange}%3A{ticker}",
            "hsx": "https://www.hsx.vn/vi/",
            "cafef": "https://m.cafef.vn/",
            "24hmoney": f"https://24hmoney.vn/stock/{ticker}/",
            "vnexpress": "https://vnexpress.net/kinh-doanh",
            "telegram_quantin": "https://t.me/s/quantin",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dominant_trend(trends: list[str]) -> str:
    """Return the most common trend label."""
    if not trends:
        return "unknown"
    counts: dict[str, int] = {}
    for t in trends:
        counts[t] = counts.get(t, 0) + 1
    return max(counts, key=lambda k: counts[k])


def _trend_strength(alignment: int, total: int) -> str:
    if total == 0:
        return "unknown"
    ratio = alignment / total
    if ratio >= 1.0:
        return "strong"
    if ratio >= 0.75:
        return "moderate"
    if ratio >= 0.5:
        return "weak"
    return "conflicting"


def _compute_bias(dominant: str, alignment: int, total: int) -> str:
    if total == 0:
        return "neutral"
    ratio = alignment / total
    if dominant == "uptrend" and ratio >= 0.75:
        return "bullish"
    if dominant == "downtrend" and ratio >= 0.75:
        return "bearish"
    return "neutral"


def _serialise(result: MultiTimeframeResult) -> dict[str, Any]:
    """Convert dataclasses to plain dicts for JSON serialisation."""
    data = asdict(result)
    # Convert snapshot dataclasses
    data["snapshots"] = {
        tf: asdict(snap) for tf, snap in result.snapshots.items()
    }
    return data
