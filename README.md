# Agent-fit — VN Stock Trading Execution System v2.0

An institutional-grade Vietnamese stock trading agent that analyses market signals, mines historical trade patterns, optimises entry zones, and enforces risk management rules — all in a structured **Skills + Workflow + Execution** architecture.

## Architecture

```
Agent-fit/
├── agent_config.json          # Full system configuration
├── main.py                    # CLI entry point
├── requirements.txt
├── data/
│   ├── latest_signal.json     # Current market signal snapshot
│   ├── trades.csv             # Historical trade log
│   └── equity_curve.csv       # Equity curve / drawdown history
├── agent/
│   ├── workflow.py            # Orchestrates perceive→reason→act→observe→repeat
│   ├── skills/
│   │   ├── signal_diagnosis.py         # Why is signal False?
│   │   ├── historical_pattern_mining.py # Extract winning-trade conditions
│   │   ├── entry_optimization.py       # Best entry zone & timing
│   │   └── risk_management.py          # SL / TP / RR / position sizing
│   └── subagents/
│       ├── researcher.py   # Loads & summarises trades.csv
│       ├── analyst.py      # RSI / MA / volume technical analysis
│       └── executor.py     # Final ENTER / WAIT / NO TRADE decision
└── tests/
    └── test_agent.py       # 43 unit + integration tests
```

## Workflow

| Step | Action |
|------|--------|
| **perceive** | Load `latest_signal.json`, `trades.csv`, `equity_curve.csv` |
| **reason** | Run `signal-diagnosis` + `historical-pattern-mining` skills |
| **act** | Run `entry-optimization` skill |
| **observe** | Run `risk-management` skill; verify RR ≥ 1.5 |
| **repeat** | Adjust entry toward safer zone if RR not met (max 3 iterations) |

## Output Format

```json
{
  "signal_status": "INACTIVE",
  "signal_issue": "Trend không hợp lệ: 'sideways' (cần uptrend); Volume yếu: ...",
  "entry_timing": "WAIT_PULLBACK",
  "entry_zones": {
    "optimal": "76,930",
    "aggressive": "75,360",
    "safe": "76,800"
  },
  "stoploss": "76,032",
  "take_profit": "79,310",
  "rr_ratio": "2.65",
  "probability": "60–70%",
  "decision": "WAIT",
  "reason": "..."
}
```

## Quick Start

```bash
pip install -r requirements.txt
python main.py
# or with custom paths:
python main.py --signal data/latest_signal.json \
               --trades data/trades.csv \
               --equity data/equity_curve.csv \
               --capital 100000000
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/test_agent.py -v
```

## Constraints

- Never fabricates data — missing fields return `[Unverified]`
- No trade if signal is weak
- No FOMO, no all-in
- Risk ≤ 2% of capital per trade
- RR ≥ 1.5 required before any ENTER decision
