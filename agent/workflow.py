"""Trading Workflow.

Orchestrates the full perceive → reason → act → observe → repeat
cycle as defined in agent_config.json.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from agent.skills.signal_diagnosis import SignalDiagnosisSkill
from agent.skills.historical_pattern_mining import HistoricalPatternMiningSkill
from agent.skills.entry_optimization import EntryOptimizationSkill
from agent.skills.risk_management import RiskManagementSkill
from agent.subagents.researcher import ResearcherAgent
from agent.subagents.analyst import AnalystAgent
from agent.subagents.executor import ExecutorAgent

logger = logging.getLogger(__name__)

# Maximum iterations for the repeat step
MAX_REPEAT_ITERATIONS = 3


class TradingWorkflow:
    """Runs the full VN Stock Trading agent workflow.

    Workflow steps (from agent_config.json):
        1. perceive  – Load data files
        2. reason    – Select and apply relevant skills
        3. act       – Entry optimisation
        4. observe   – Compare with historical trades
        5. repeat    – Adjust entry until RR target is met
    """

    def __init__(
        self,
        signal_path: str | Path,
        trades_path: str | Path,
        equity_path: str | Path,
        capital: float = 100_000_000,
    ) -> None:
        self.capital = capital

        # Sub-agents
        self._researcher = ResearcherAgent(trades_path)
        self._analyst = AnalystAgent(signal_path, equity_path)
        self._executor = ExecutorAgent()

        # Skills
        self._diagnosis_skill = SignalDiagnosisSkill()
        self._pattern_skill = HistoricalPatternMiningSkill()
        self._optimization_skill = EntryOptimizationSkill()
        self._risk_skill = RiskManagementSkill()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Execute the complete workflow and return the final decision.

        Returns:
            JSON-serialisable dict matching the system output_format schema.
        """
        # ── Step 1: perceive ──────────────────────────────────────────
        signal_data, trades_df = self._perceive()

        # ── Step 2: reason ────────────────────────────────────────────
        diagnosis, pattern_summary, analysis = self._reason(signal_data, trades_df)

        # ── Steps 3–5: act → observe → repeat ─────────────────────────
        result = self._act_observe_repeat(
            signal_data, diagnosis, pattern_summary, analysis
        )

        return result

    # ------------------------------------------------------------------
    # Workflow steps
    # ------------------------------------------------------------------

    def _perceive(self) -> tuple[dict[str, Any], pd.DataFrame]:
        """Step 1 – Load all required data sources."""
        logger.debug("[perceive] Loading signal data and historical trades")
        signal_data = self._analyst.load_signal()
        trades_df = self._researcher.load()
        return signal_data, trades_df

    def _reason(
        self,
        signal_data: dict[str, Any],
        trades_df: pd.DataFrame,
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        """Step 2 – Apply signal-diagnosis and pattern-mining skills."""
        logger.debug("[reason] Running signal diagnosis and pattern mining")
        diagnosis = self._diagnosis_skill.run(signal_data)
        pattern_summary = self._pattern_skill.run(trades_df)
        analysis = self._analyst.analyse()
        return diagnosis, pattern_summary, analysis

    def _act_observe_repeat(
        self,
        signal_data: dict[str, Any],
        diagnosis: dict[str, Any],
        pattern_summary: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """Steps 3–5 – Optimise entry, compute risk, iterate until RR met."""
        win_patterns = pattern_summary.get("win_patterns", {})

        for iteration in range(1, MAX_REPEAT_ITERATIONS + 1):
            logger.debug("[act] Iteration %d — optimising entry", iteration)

            # Step 3: act – entry optimisation
            optimization = self._optimization_skill.run(
                signal_data, diagnosis, win_patterns
            )

            # Step 4: observe – risk management
            risk = self._risk_skill.run(
                signal_data,
                optimization["entry_zones"],
                win_patterns,
                self.capital,
            )

            rr_valid = risk.get("rr_valid", False)

            if rr_valid:
                logger.debug("[observe] RR valid on iteration %d", iteration)
                break

            # Step 5: repeat – relax entry to improve RR
            logger.debug(
                "[repeat] RR not met on iteration %d — adjusting entry", iteration
            )
            if iteration < MAX_REPEAT_ITERATIONS:
                # Push entry toward the safer (deeper pullback) zone to widen RR
                safe_zone = optimization["entry_zones"].get("safe", "")
                if safe_zone and safe_zone != "[Unverified]":
                    try:
                        adjusted_price = float(safe_zone.replace(",", ""))
                        signal_data = dict(signal_data, price=adjusted_price)
                    except ValueError:
                        pass

        # Final decision from executor
        return self._executor.decide(
            diagnosis=diagnosis,
            analysis=analysis,
            optimization=optimization,
            risk=risk,
            pattern_summary=pattern_summary,
        )
