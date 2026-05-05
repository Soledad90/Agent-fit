# Agent-fit — VN Stock Trading Execution System v3.0

An institutional-grade Vietnamese stock trading agent that analyses market signals across **multiple timeframes (1H / 4H / 1D / 1W)**, mines historical trade patterns, optimises entry zones, and enforces risk management rules — all in a structured **Skills + Workflow + Execution** architecture.

**Works with ANY Vietnamese stock ticker** on HOSE, HNX, or UPCOM.

## Architecture

```
Agent-fit/
├── agent_config.json          # Full system configuration (v3.0)
├── main.py                    # CLI entry point
├── requirements.txt
├── data/
│   ├── latest_signal.json     # Current market signal snapshot
│   ├── trades.csv             # Historical trade log
│   └── equity_curve.csv       # Equity curve / drawdown history
├── agent/
│   ├── workflow.py            # Orchestrates perceive→reason→act→observe→repeat
│   ├── skills/
│   │   ├── signal_diagnosis.py             # Why is signal False?
│   │   ├── historical_pattern_mining.py    # Extract winning-trade conditions
│   │   ├── entry_optimization.py           # Best entry zone & timing
│   │   ├── risk_management.py              # SL / TP / RR / position sizing
│   │   ├── multi_timeframe_analysis.py     # 1H/4H/1D/1W technical analysis
│   │   ├── market_context_analysis.py      # Price/volume flow + news + macro
│   │   └── strategy_builder.py             # Combine all → buy/sell strategy
│   └── subagents/
│       ├── researcher.py   # Loads & summarises trades.csv
│       ├── analyst.py      # RSI / MA / volume technical analysis
│       └── executor.py     # Final ENTER / WAIT / NO TRADE decision
└── tests/
    └── test_agent.py       # Unit + integration tests
```

## Workflow

### Original Trade Execution Workflow

| Step | Action |
|------|--------|
| **perceive** | Load `latest_signal.json`, `trades.csv`, `equity_curve.csv` |
| **reason** | Run `signal-diagnosis` + `historical-pattern-mining` skills |
| **act** | Run `entry-optimization` skill |
| **observe** | Run `risk-management` skill; verify RR ≥ 1.5 |
| **repeat** | Adjust entry toward safer zone if RR not met (max 3 iterations) |

### Multi-Timeframe Analysis Workflow (v3.0)

| Step | Skill | Action |
|------|-------|--------|
| **1. Technical** | `multi-timeframe-analysis` | Top-down: 1W → 1D → 4H → 1H. Collect OHLC, EMA, RSI, MACD per timeframe |
| **2. Volume/Flow** | `market-context-analysis` | Price/volume data, buy/sell active ratio, foreign flow |
| **3. News** | `market-context-analysis` | Sector news, earnings, policy, macro context |
| **4. Strategy** | `strategy-builder` | Combine all → 3 scenarios, entry zones, SL/TP, recommendation |

#### Timeframes

| Timeframe | Purpose | Lookback |
|-----------|---------|----------|
| **1H** | Scalping / precise entry within session | 5-10 days |
| **4H** | Short-term swing, breakout confirmation | 1-2 months |
| **1D** | Primary trend, key support/resistance | 3-6 months |
| **1W** | Long-term trend, major accumulation zones | 1-2 years |

#### Data Sources

| Source | URL | Data |
|--------|-----|------|
| TradingView | `https://www.tradingview.com/chart/?symbol=HOSE%3A{TICKER}` | Charts, indicators, technical rating |
| HSX | `https://www.hsx.vn/vi/` | Official price/volume data |
| 24hMoney | `https://24hmoney.vn/stock/{TICKER}/` | Buy/sell active ratio, flow |
| CafeF | `https://m.cafef.vn/` | News, earnings, sector analysis |
| VnExpress | `https://vnexpress.net/kinh-doanh` | Business news |
| Quán Tin | `https://t.me/s/quantin` | Geopolitical risk context |

#### Macro Checklist

Every analysis must check:
- VN-Index / VN30 — market trend
- DXY — USD strength
- USD/VND — exchange rate
- Interest rates — NHNN policy
- Oil / Gold prices — sector correlations
- US Markets (SPX, NDQ) — Asia sentiment

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
- Multi-timeframe: ≥3/4 timeframes must align for "strong" signal
