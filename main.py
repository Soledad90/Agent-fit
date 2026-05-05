#!/usr/bin/env python3
"""VN Stock Trading Execution System — entry point.

Usage:
    python main.py [--signal data/latest_signal.json]
                   [--trades data/trades.csv]
                   [--equity data/equity_curve.csv]
                   [--capital 100000000]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from agent.workflow import TradingWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Default data paths relative to this file
_HERE = Path(__file__).parent
DEFAULT_SIGNAL = _HERE / "data" / "latest_signal.json"
DEFAULT_TRADES = _HERE / "data" / "trades.csv"
DEFAULT_EQUITY = _HERE / "data" / "equity_curve.csv"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VN Stock Trading Execution System v2.0"
    )
    parser.add_argument(
        "--signal",
        default=str(DEFAULT_SIGNAL),
        help="Path to latest_signal.json",
    )
    parser.add_argument(
        "--trades",
        default=str(DEFAULT_TRADES),
        help="Path to trades.csv",
    )
    parser.add_argument(
        "--equity",
        default=str(DEFAULT_EQUITY),
        help="Path to equity_curve.csv",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100_000_000,
        help="Total trading capital in VND (default: 100,000,000)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logger.info("Starting VN Stock Trading Execution System v2.0")
    logger.info("Signal file : %s", args.signal)
    logger.info("Trades file : %s", args.trades)
    logger.info("Equity file : %s", args.equity)
    logger.info("Capital     : %s VND", f"{args.capital:,.0f}")

    workflow = TradingWorkflow(
        signal_path=args.signal,
        trades_path=args.trades,
        equity_path=args.equity,
        capital=args.capital,
    )

    result = workflow.run()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
