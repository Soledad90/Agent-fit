"""Tests for v3.0 multi-timeframe analysis skills."""

from __future__ import annotations

import pytest

from agent.skills.multi_timeframe_analysis import (
    MultiTimeframeAnalysisSkill,
    TimeframeSnapshot,
    TIMEFRAMES,
    TIMEFRAME_META,
    REQUIRED_INDICATORS,
)
from agent.skills.market_context_analysis import (
    MarketContextAnalysisSkill,
    VolumeFlowData,
    NewsItem,
    MacroContext,
)
from agent.skills.strategy_builder import StrategyBuilderSkill


# ====================================================================
# MultiTimeframeAnalysisSkill
# ====================================================================


class TestMultiTimeframeAnalysisSkill:
    def setup_method(self) -> None:
        self.skill = MultiTimeframeAnalysisSkill()

    def _make_snapshots(
        self, trends: dict[str, str] | None = None
    ) -> dict[str, TimeframeSnapshot]:
        default = {
            "1W": "downtrend",
            "1D": "downtrend",
            "4H": "downtrend",
            "1H": "sideways",
        }
        t = trends or default
        return {
            tf: TimeframeSnapshot(timeframe=tf, trend=t.get(tf, "unknown"))
            for tf in TIMEFRAMES
        }

    def test_all_timeframes_defined(self) -> None:
        assert TIMEFRAMES == ("1W", "1D", "4H", "1H")

    def test_timeframe_meta_keys(self) -> None:
        for tf in TIMEFRAMES:
            meta = TIMEFRAME_META[tf]
            assert "label" in meta
            assert "purpose" in meta
            assert "tradingview_interval" in meta

    def test_required_indicators_non_empty(self) -> None:
        assert len(REQUIRED_INDICATORS) >= 4

    def test_run_returns_expected_keys(self) -> None:
        result = self.skill.run("ACB", "HOSE", self._make_snapshots())
        assert "ticker" in result
        assert "exchange" in result
        assert "overall_trend" in result
        assert "trend_alignment" in result
        assert "trend_strength" in result
        assert "key_supports" in result
        assert "key_resistances" in result
        assert "bias" in result

    def test_dominant_trend_downtrend(self) -> None:
        result = self.skill.run("ACB", "HOSE", self._make_snapshots())
        assert result["overall_trend"] == "downtrend"

    def test_strong_alignment_all_same(self) -> None:
        snaps = self._make_snapshots(
            {"1W": "uptrend", "1D": "uptrend", "4H": "uptrend", "1H": "uptrend"}
        )
        result = self.skill.run("FPT", "HOSE", snaps)
        assert result["trend_alignment"] == 4
        assert result["trend_strength"] == "strong"
        assert result["bias"] == "bullish"

    def test_conflicting_trends(self) -> None:
        snaps = self._make_snapshots(
            {"1W": "uptrend", "1D": "downtrend", "4H": "sideways", "1H": "uptrend"}
        )
        result = self.skill.run("VNM", "HOSE", snaps)
        assert result["trend_strength"] in ("weak", "conflicting")

    def test_tradingview_url(self) -> None:
        url = MultiTimeframeAnalysisSkill.tradingview_url("ACB", "HOSE")
        assert "HOSE" in url
        assert "ACB" in url

    def test_data_sources(self) -> None:
        sources = MultiTimeframeAnalysisSkill.data_sources("HPG")
        assert "tradingview" in sources
        assert "hsx" in sources
        assert "cafef" in sources
        assert "HPG" in sources["tradingview"]
        assert "HOSE" in sources["tradingview"]

    def test_data_sources_hnx_exchange(self) -> None:
        sources = MultiTimeframeAnalysisSkill.data_sources("SHS", exchange="HNX")
        assert "HNX" in sources["tradingview"]
        assert "SHS" in sources["tradingview"]
        assert "HOSE" not in sources["tradingview"]

    def test_data_sources_upcom_exchange(self) -> None:
        sources = MultiTimeframeAnalysisSkill.data_sources("BSR", exchange="UPCOM")
        assert "UPCOM" in sources["tradingview"]

    def test_missing_timeframes_handled(self) -> None:
        partial = {"1D": TimeframeSnapshot(timeframe="1D", trend="uptrend")}
        result = self.skill.run("VCB", "HOSE", partial)
        assert result["overall_trend"] == "uptrend"
        assert result["trend_alignment"] == 1

    def test_bearish_bias_strong_downtrend(self) -> None:
        snaps = self._make_snapshots(
            {"1W": "downtrend", "1D": "downtrend", "4H": "downtrend", "1H": "downtrend"}
        )
        result = self.skill.run("ACB", "HOSE", snaps)
        assert result["bias"] == "bearish"

    def test_supports_resistances_aggregated(self) -> None:
        snaps = {
            "1D": TimeframeSnapshot(
                timeframe="1D",
                trend="downtrend",
                support_levels=[22000, 21500],
                resistance_levels=[23000, 24000],
            ),
            "1W": TimeframeSnapshot(
                timeframe="1W",
                trend="downtrend",
                support_levels=[20000],
                resistance_levels=[25000],
            ),
        }
        result = self.skill.run("ACB", "HOSE", snaps)
        assert len(result["key_supports"]) >= 2
        assert len(result["key_resistances"]) >= 2


# ====================================================================
# MarketContextAnalysisSkill
# ====================================================================


class TestMarketContextAnalysisSkill:
    def setup_method(self) -> None:
        self.skill = MarketContextAnalysisSkill()

    def _make_flow(self, **kwargs: object) -> VolumeFlowData:
        defaults = dict(
            ticker="ACB",
            last_close=22600,
            change_pct=-2.16,
            volume=28_890_000,
            avg_volume_20d=12_490_000,
            buy_active_pct=47.85,
            sell_active_pct=52.15,
        )
        defaults.update(kwargs)
        return VolumeFlowData(**defaults)  # type: ignore[arg-type]

    def test_sell_dominant_flow(self) -> None:
        flow = self._make_flow(sell_active_pct=60, buy_active_pct=40)
        result = self.skill.run(flow, [])
        assert result["volume_flow"]["flow_bias"] == "sell_dominant"

    def test_buy_dominant_flow(self) -> None:
        flow = self._make_flow(
            buy_active_pct=60, sell_active_pct=40, change_pct=2.0
        )
        result = self.skill.run(flow, [])
        assert result["volume_flow"]["flow_bias"] == "buy_dominant"

    def test_neutral_flow(self) -> None:
        flow = self._make_flow(
            buy_active_pct=50,
            sell_active_pct=50,
            volume=10_000_000,
            avg_volume_20d=12_000_000,
            change_pct=0.1,
        )
        result = self.skill.run(flow, [])
        assert result["volume_flow"]["flow_bias"] == "neutral"

    def test_news_sentiment_positive(self) -> None:
        news = [
            NewsItem(
                headline="ACB Q1 +17%",
                source="cafef",
                sentiment="positive",
                impact="high",
                credibility="high",
            ),
        ]
        flow = self._make_flow()
        result = self.skill.run(flow, news)
        assert result["news_sentiment_score"] > 0

    def test_news_sentiment_negative(self) -> None:
        news = [
            NewsItem(
                headline="Nợ xấu tăng",
                source="cafef",
                sentiment="negative",
                impact="high",
            ),
        ]
        flow = self._make_flow()
        result = self.skill.run(flow, news)
        assert result["news_sentiment_score"] < 0

    def test_credibility_high(self) -> None:
        news = [
            NewsItem(headline="A", source="cafef", credibility="high"),
            NewsItem(headline="B", source="vnexpress", credibility="high"),
        ]
        flow = self._make_flow()
        result = self.skill.run(flow, news)
        assert result["credibility_score"] == "high"

    def test_empty_news_returns_low_credibility(self) -> None:
        flow = self._make_flow()
        result = self.skill.run(flow, [])
        assert result["credibility_score"] == "low"

    def test_macro_context_included(self) -> None:
        flow = self._make_flow()
        macro = MacroContext(
            vn_index=1855.66,
            dxy=98.47,
            risk_environment="risk_off",
        )
        result = self.skill.run(flow, [], macro)
        assert result["macro"]["risk_environment"] == "risk_off"

    def test_overall_bearish(self) -> None:
        flow = self._make_flow(sell_active_pct=60, buy_active_pct=40)
        news = [
            NewsItem(
                headline="Bad",
                source="x",
                sentiment="negative",
                impact="high",
            ),
        ]
        macro = MacroContext(risk_environment="risk_off")
        result = self.skill.run(flow, news, macro)
        assert result["overall_assessment"] == "bearish"

    def test_volume_ratio_computed(self) -> None:
        flow = self._make_flow()
        result = self.skill.run(flow, [])
        assert result["volume_flow"]["volume_ratio"] > 0


# ====================================================================
# StrategyBuilderSkill
# ====================================================================


class TestStrategyBuilderSkill:
    def setup_method(self) -> None:
        self.skill = StrategyBuilderSkill()

    def _make_tf_result(self, trend: str = "downtrend") -> dict:
        return {
            "overall_trend": trend,
            "trend_strength": "strong",
            "key_supports": [22000, 21500],
            "key_resistances": [23000, 24000],
            "snapshots": {
                "1W": {"trend": trend},
                "1D": {"trend": trend},
                "4H": {"trend": trend},
                "1H": {"trend": "sideways"},
            },
        }

    def _make_ctx_result(self, flow_bias: str = "sell_dominant") -> dict:
        return {
            "volume_flow": {
                "flow_bias": flow_bias,
                "volume_ratio": 2.3,
                "change_pct": -2.16,
            },
            "news_sentiment_score": -0.2,
            "credibility_score": "medium",
        }

    def test_strategy_has_expected_keys(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result(), self._make_ctx_result(),
        )
        for key in [
            "ticker", "exchange", "target_date", "current_price",
            "overall_trend", "scenarios", "buy_entries", "sell_zones",
            "recommendation", "confidence", "reason",
        ]:
            assert key in result, f"Missing key: {key}"

    def test_three_scenarios_generated(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result(), self._make_ctx_result(),
        )
        assert len(result["scenarios"]) == 3
        total_prob = sum(s["probability_pct"] for s in result["scenarios"])
        assert total_prob == 100

    def test_recommendation_observe_on_downtrend(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result("downtrend"),
            self._make_ctx_result("sell_dominant"),
        )
        assert result["recommendation"] == "OBSERVE"

    def test_recommendation_buy_on_uptrend(self) -> None:
        result = self.skill.run(
            "FPT", "HOSE", "2026-05-06", 120000,
            self._make_tf_result("uptrend"),
            self._make_ctx_result("buy_dominant"),
        )
        assert result["recommendation"] == "BUY"

    def test_sell_zones_populated_with_resistances(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result(), self._make_ctx_result(),
        )
        assert len(result["sell_zones"]) >= 1

    def test_risk_management_defaults(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result(), self._make_ctx_result(),
        )
        assert result["max_position_pct"] == 30.0
        assert result["risk_per_trade_pct"] == 2.0
        assert result["split_orders"] == 3

    def test_sideways_scenarios(self) -> None:
        tf = self._make_tf_result("sideways")
        tf["trend_strength"] = "weak"
        result = self.skill.run(
            "VNM", "HOSE", "2026-05-06", 78500,
            tf, self._make_ctx_result("neutral"),
        )
        assert any("sideway" in s["name"].lower() for s in result["scenarios"])

    def test_news_negative_downgrades_buy_confidence(self) -> None:
        ctx = self._make_ctx_result("buy_dominant")
        ctx["news_sentiment_score"] = -0.8  # very negative news
        result = self.skill.run(
            "FPT", "HOSE", "2026-05-06", 120000,
            self._make_tf_result("uptrend"), ctx,
        )
        assert result["recommendation"] == "BUY"
        assert result["confidence"] == "medium"  # downgraded from high

    def test_news_positive_downgrades_observe_confidence(self) -> None:
        ctx = self._make_ctx_result("sell_dominant")
        ctx["news_sentiment_score"] = 0.8  # very positive news
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result("downtrend"), ctx,
        )
        assert result["recommendation"] == "OBSERVE"
        assert result["confidence"] == "medium"  # downgraded from high

    def test_trend_fields_populated(self) -> None:
        result = self.skill.run(
            "ACB", "HOSE", "2026-05-06", 22600,
            self._make_tf_result(), self._make_ctx_result(),
        )
        assert result["trend_1d"] == "downtrend"
        assert result["trend_1w"] == "downtrend"
        assert result["trend_1h"] == "sideways"
