"""Unit tests for the VN Stock Trading Execution System."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd
import pytest

# Ensure project root is on sys.path when running tests directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.skills.signal_diagnosis import SignalDiagnosisSkill
from agent.skills.historical_pattern_mining import HistoricalPatternMiningSkill
from agent.skills.entry_optimization import EntryOptimizationSkill
from agent.skills.risk_management import RiskManagementSkill
from agent.subagents.researcher import ResearcherAgent
from agent.subagents.analyst import AnalystAgent
from agent.subagents.executor import ExecutorAgent
from agent.workflow import TradingWorkflow

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def sample_signal() -> dict:
    return {
        "ticker": "VNM",
        "date": "2026-04-16",
        "signal": False,
        "price": 78500,
        "rsi": 42.5,
        "ma20": 79200,
        "ma50": 76800,
        "volume": 1250000,
        "avg_volume_20d": 1800000,
        "trend": "sideways",
        "signal_conditions": {
            "trend_ok": False,
            "volume_ok": False,
            "rsi_ok": True,
            "price_above_ma20": False,
        },
    }


@pytest.fixture
def winning_signal() -> dict:
    """A signal where all conditions are met for an immediate entry."""
    return {
        "ticker": "HPG",
        "date": "2026-04-16",
        "signal": True,
        "price": 37000,
        "rsi": 37.0,
        "ma20": 36500,
        "ma50": 34000,
        "volume": 4200000,
        "avg_volume_20d": 1800000,
        "trend": "uptrend",
        "signal_conditions": {
            "trend_ok": True,
            "volume_ok": True,
            "rsi_ok": True,
            "price_above_ma20": True,
        },
    }


@pytest.fixture
def sample_trades_df() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "trades.csv", parse_dates=["date"])


# ---------------------------------------------------------------------------
# SignalDiagnosisSkill
# ---------------------------------------------------------------------------


class TestSignalDiagnosisSkill:
    def test_inactive_signal_detected(self, sample_signal):
        skill = SignalDiagnosisSkill()
        result = skill.run(sample_signal)
        assert result["signal_status"] == "INACTIVE"

    def test_active_signal_detected(self, winning_signal):
        skill = SignalDiagnosisSkill()
        result = skill.run(winning_signal)
        assert result["signal_status"] == "ACTIVE"

    def test_issues_listed_when_conditions_fail(self, sample_signal):
        skill = SignalDiagnosisSkill()
        result = skill.run(sample_signal)
        # trend_ok=False → issue about trend
        assert any("trend" in issue.lower() or "Trend" in issue for issue in result["issues"])

    def test_no_issues_when_all_conditions_met(self, winning_signal):
        skill = SignalDiagnosisSkill()
        result = skill.run(winning_signal)
        assert result["issues"] == ["Tín hiệu đủ điều kiện"]

    def test_empty_data_returns_unverified(self):
        skill = SignalDiagnosisSkill()
        result = skill.run({})
        assert result["signal_status"] == "INACTIVE"
        assert any("[Unverified]" in i for i in result["issues"])

    def test_conditions_returned(self, sample_signal):
        skill = SignalDiagnosisSkill()
        result = skill.run(sample_signal)
        assert "conditions" in result
        assert isinstance(result["conditions"], dict)


# ---------------------------------------------------------------------------
# HistoricalPatternMiningSkill
# ---------------------------------------------------------------------------


class TestHistoricalPatternMiningSkill:
    def test_win_rate_calculated(self, sample_trades_df):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(sample_trades_df)
        assert 0 < result["win_rate"] < 1

    def test_win_patterns_populated(self, sample_trades_df):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(sample_trades_df)
        assert result["win_patterns"]["count"] > 0
        assert "avg_rsi" in result["win_patterns"]
        assert "avg_volume_ratio" in result["win_patterns"]

    def test_loss_patterns_populated(self, sample_trades_df):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(sample_trades_df)
        assert result["loss_patterns"]["count"] > 0

    def test_best_conditions_non_empty(self, sample_trades_df):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(sample_trades_df)
        assert len(result["best_conditions"]) > 0

    def test_empty_df_returns_unverified(self):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(pd.DataFrame())
        assert result["win_rate"] is None
        assert any("[Unverified]" in c for c in result["best_conditions"])

    def test_total_trades_count(self, sample_trades_df):
        skill = HistoricalPatternMiningSkill()
        result = skill.run(sample_trades_df)
        assert result["total_trades"] == len(sample_trades_df)


# ---------------------------------------------------------------------------
# EntryOptimizationSkill
# ---------------------------------------------------------------------------


class TestEntryOptimizationSkill:
    def test_wait_pullback_when_rsi_ok_but_trend_volume_fail(self, sample_signal):
        skill = EntryOptimizationSkill()
        diagnosis = {
            "conditions": {
                "trend_ok": False,
                "volume_ok": False,
                "rsi_ok": True,
                "price_above_ma20": False,
            }
        }
        result = skill.run(sample_signal, diagnosis, {})
        assert result["entry_timing"] == "WAIT_PULLBACK"

    def test_now_when_all_conditions_met(self, winning_signal):
        skill = EntryOptimizationSkill()
        diagnosis = {
            "conditions": {
                "trend_ok": True,
                "volume_ok": True,
                "rsi_ok": True,
                "price_above_ma20": True,
            }
        }
        result = skill.run(winning_signal, diagnosis, {})
        assert result["entry_timing"] == "NOW"

    def test_entry_zones_have_three_keys(self, sample_signal):
        skill = EntryOptimizationSkill()
        diagnosis = {"conditions": {"trend_ok": False, "volume_ok": False, "rsi_ok": True, "price_above_ma20": False}}
        result = skill.run(sample_signal, diagnosis, {})
        assert set(result["entry_zones"].keys()) == {"optimal", "aggressive", "safe"}

    def test_missing_price_returns_unverified(self):
        skill = EntryOptimizationSkill()
        result = skill.run({}, {"conditions": {}}, {})
        assert result["entry_zones"]["optimal"] == "[Unverified]"

    def test_reasoning_non_empty(self, sample_signal):
        skill = EntryOptimizationSkill()
        diagnosis = {"conditions": {"trend_ok": False, "volume_ok": False, "rsi_ok": True, "price_above_ma20": False}}
        result = skill.run(sample_signal, diagnosis, {})
        assert len(result["reasoning"]) > 0


# ---------------------------------------------------------------------------
# RiskManagementSkill
# ---------------------------------------------------------------------------


class TestRiskManagementSkill:
    def _make_win_patterns(self):
        return {"count": 20, "avg_rsi": 40.0, "avg_volume_ratio": 1.9, "avg_pnl_pct": 9.0, "avg_rr": 2.6}

    def test_rr_valid_above_minimum(self, winning_signal):
        skill = RiskManagementSkill()
        entry_zones = {"optimal": "37000", "aggressive": "36260", "safe": "35520"}
        result = skill.run(winning_signal, entry_zones, self._make_win_patterns())
        assert result["rr_valid"] is True

    def test_stoploss_below_entry(self, winning_signal):
        skill = RiskManagementSkill()
        entry_zones = {"optimal": "37000", "aggressive": "36260", "safe": "35520"}
        result = skill.run(winning_signal, entry_zones, self._make_win_patterns())
        sl = float(result["stoploss"].replace(",", ""))
        assert sl < 37000

    def test_take_profit_above_entry(self, winning_signal):
        skill = RiskManagementSkill()
        entry_zones = {"optimal": "37000", "aggressive": "36260", "safe": "35520"}
        result = skill.run(winning_signal, entry_zones, self._make_win_patterns())
        tp = float(result["take_profit"].replace(",", ""))
        assert tp > 37000

    def test_probability_string_returned(self, winning_signal):
        skill = RiskManagementSkill()
        entry_zones = {"optimal": "37000", "aggressive": "36260", "safe": "35520"}
        result = skill.run(winning_signal, entry_zones, self._make_win_patterns())
        assert isinstance(result["probability"], str)

    def test_missing_price_returns_unverified(self):
        skill = RiskManagementSkill()
        result = skill.run({}, {}, {})
        assert result["stoploss"] == "[Unverified]"
        assert result["rr_valid"] is False

    def test_max_position_respects_capital(self, winning_signal):
        skill = RiskManagementSkill()
        capital = 100_000_000
        entry_zones = {"optimal": "37000", "aggressive": "36260", "safe": "35520"}
        result = skill.run(winning_signal, entry_zones, self._make_win_patterns(), capital=capital)
        pos_value = float(result["max_position_size"].replace(",", "").replace(" VND", ""))
        assert pos_value <= capital * 0.02 / (37000 - float(result["stoploss"].replace(",", ""))) * 37000 + 37000


# ---------------------------------------------------------------------------
# ResearcherAgent
# ---------------------------------------------------------------------------


class TestResearcherAgent:
    def test_load_returns_dataframe(self):
        agent = ResearcherAgent(DATA_DIR / "trades.csv")
        df = agent.load()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_summary_has_win_rate(self):
        agent = ResearcherAgent(DATA_DIR / "trades.csv")
        summary = agent.summary()
        assert "win_rate" in summary
        assert 0 <= summary["win_rate"] <= 1

    def test_missing_file_returns_empty(self, tmp_path):
        agent = ResearcherAgent(tmp_path / "nonexistent.csv")
        df = agent.load()
        assert df.empty

    def test_summary_missing_file_returns_no_data(self, tmp_path):
        agent = ResearcherAgent(tmp_path / "nonexistent.csv")
        result = agent.summary()
        assert result == {"status": "no_data"}


# ---------------------------------------------------------------------------
# AnalystAgent
# ---------------------------------------------------------------------------


class TestAnalystAgent:
    def test_load_signal_returns_dict(self):
        agent = AnalystAgent(DATA_DIR / "latest_signal.json", DATA_DIR / "equity_curve.csv")
        signal = agent.load_signal()
        assert isinstance(signal, dict)
        assert "ticker" in signal

    def test_analyse_returns_expected_keys(self):
        agent = AnalystAgent(DATA_DIR / "latest_signal.json", DATA_DIR / "equity_curve.csv")
        result = agent.analyse()
        for key in ("ticker", "rsi", "rsi_label", "volume_label", "trend_label", "equity_health"):
            assert key in result

    def test_missing_signal_returns_status(self, tmp_path):
        agent = AnalystAgent(tmp_path / "no_signal.json", DATA_DIR / "equity_curve.csv")
        result = agent.analyse()
        assert result == {"status": "no_signal_data"}

    def test_equity_health_classification(self):
        agent = AnalystAgent(DATA_DIR / "latest_signal.json", DATA_DIR / "equity_curve.csv")
        result = agent.analyse()
        assert result["equity_health"] in (
            "at_all_time_high", "healthy", "moderate_drawdown", "severe_drawdown", "unknown"
        )


# ---------------------------------------------------------------------------
# ExecutorAgent
# ---------------------------------------------------------------------------


class TestExecutorAgent:
    def _make_inputs(self, signal_status="INACTIVE", entry_timing="WAIT_PULLBACK", rr_valid=True):
        diagnosis = {
            "signal_status": signal_status,
            "issues": ["Trend không hợp lệ: 'sideways' (cần uptrend)", "Volume yếu: 0.69x trung bình (cần ≥ 1.5x)"],
            "conditions": {"trend_ok": False, "volume_ok": False, "rsi_ok": True, "price_above_ma20": False},
        }
        analysis = {
            "ticker": "VNM",
            "rsi": 42.5,
            "rsi_label": "near_oversold",
            "volume_ratio": 0.69,
            "volume_label": "weak",
            "trend": "sideways",
            "trend_label": "neutral",
            "equity_health": "at_all_time_high",
        }
        optimization = {
            "entry_timing": entry_timing,
            "entry_zones": {"optimal": "76,930", "aggressive": "75,360", "safe": "76,080"},
            "reasoning": ["RSI hợp lệ nhưng thiếu xác nhận trend/volume"],
        }
        risk = {
            "stoploss": "74,000",
            "take_profit": "84,000",
            "rr_ratio": "2.04",
            "max_position_size": "65,520,000 VND",
            "probability": "60–70%",
            "rr_valid": rr_valid,
        }
        pattern_summary = {
            "win_rate": 0.6667,
            "win_patterns": {"count": 20, "avg_rsi": 40.0, "avg_volume_ratio": 1.9, "avg_rr": 2.6, "avg_pnl_pct": 9.0},
            "loss_patterns": {"count": 10},
            "total_trades": 30,
        }
        return diagnosis, analysis, optimization, risk, pattern_summary

    def test_output_has_required_keys(self):
        executor = ExecutorAgent()
        diagnosis, analysis, optimization, risk, pattern_summary = self._make_inputs()
        result = executor.decide(diagnosis, analysis, optimization, risk, pattern_summary)
        required = {
            "signal_status", "signal_issue", "entry_timing", "entry_zones",
            "stoploss", "take_profit", "rr_ratio", "probability", "decision", "reason",
        }
        assert required.issubset(result.keys())

    def test_decision_is_valid_value(self):
        executor = ExecutorAgent()
        diagnosis, analysis, optimization, risk, pattern_summary = self._make_inputs()
        result = executor.decide(diagnosis, analysis, optimization, risk, pattern_summary)
        assert result["decision"] in ("ENTER", "WAIT", "NO TRADE")

    def test_no_trade_when_rr_invalid(self):
        executor = ExecutorAgent()
        diagnosis, analysis, optimization, risk, pattern_summary = self._make_inputs(rr_valid=False)
        result = executor.decide(diagnosis, analysis, optimization, risk, pattern_summary)
        assert result["decision"] == "NO TRADE"

    def test_wait_when_volume_weak(self):
        executor = ExecutorAgent()
        diagnosis, analysis, optimization, risk, pattern_summary = self._make_inputs(rr_valid=True)
        # volume_label is already "weak" in the fixture
        result = executor.decide(diagnosis, analysis, optimization, risk, pattern_summary)
        assert result["decision"] == "WAIT"

    def test_entry_zones_passed_through(self):
        executor = ExecutorAgent()
        diagnosis, analysis, optimization, risk, pattern_summary = self._make_inputs()
        result = executor.decide(diagnosis, analysis, optimization, risk, pattern_summary)
        assert result["entry_zones"] == optimization["entry_zones"]


# ---------------------------------------------------------------------------
# Full workflow integration test
# ---------------------------------------------------------------------------


class TestTradingWorkflow:
    def test_workflow_runs_without_error(self):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        assert isinstance(result, dict)

    def test_workflow_output_has_required_schema(self):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        required_keys = {
            "signal_status", "signal_issue", "entry_timing", "entry_zones",
            "stoploss", "take_profit", "rr_ratio", "probability", "decision", "reason",
        }
        assert required_keys.issubset(result.keys())

    def test_workflow_decision_is_valid(self):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        assert result["decision"] in ("ENTER", "WAIT", "NO TRADE")

    def test_workflow_entry_timing_valid(self):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        assert result["entry_timing"] in ("NOW", "WAIT", "WAIT_PULLBACK")

    def test_workflow_result_is_json_serialisable(self):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        serialised = json.dumps(result, ensure_ascii=False)
        assert isinstance(serialised, str)

    def test_workflow_missing_signal_file(self, tmp_path):
        workflow = TradingWorkflow(
            signal_path=tmp_path / "missing.json",
            trades_path=DATA_DIR / "trades.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        assert result["decision"] in ("ENTER", "WAIT", "NO TRADE")

    def test_workflow_missing_trades_file(self, tmp_path):
        workflow = TradingWorkflow(
            signal_path=DATA_DIR / "latest_signal.json",
            trades_path=tmp_path / "missing.csv",
            equity_path=DATA_DIR / "equity_curve.csv",
        )
        result = workflow.run()
        assert result["decision"] in ("ENTER", "WAIT", "NO TRADE")
