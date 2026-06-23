# 🔱 NovaSentinel

<p align="center">
  <b>AI-native sentiment-driven trading signal engine on Injective</b><br>
  <sub>Three AI agents debate. One executes on-chain.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Injective-iAgent_SDK-00B5D8?style=flat-square" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-43_passed-10B981?style=flat-square" />
  <img src="https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/Injective_Nova-2026-8B5CF6?style=flat-square" />
</p>

---

## What is NovaSentinel?

Most crypto trading tools either **analyze** or **execute** — never both. NovaSentinel closes the loop:

```
Social sentiment  ┐
On-chain data     ├─→ Multi-agent Forum Debate ─→ Trading Signal ─→ Injective Execution
Macro events      ┘
```

Three specialized AI agents gather market intelligence from different dimensions, debate in a structured forum, and a Signal Engine translates their consensus into a structured trading decision — which is then executed autonomously on Injective's perpetual contract market via the iAgent SDK.

Built as a fork of [BettaFish](https://github.com/666ghj/BettaFish), an open-source multi-agent public opinion analysis system, with the analysis core preserved and the data sources + execution layer replaced for crypto trading.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        NovaSentinel                          │
│                                                              │
│  SocialSentinel   OnChainSentinel   MacroSentinel            │
│  ─────────────    ──────────────    ─────────────            │
│  Twitter/X        Injective RPC     Fed / CPI Calendar       │
│  Reddit           CoinGecko         BTC Dominance            │
│  CryptoPanic      OI / Funding      Market Environment       │
│       │                │                  │                  │
│       └────────────────┼──────────────────┘                  │
│                        ▼                                      │
│               ForumEngine (BettaFish)                        │
│          3-agent debate + LLM Host moderator                 │
│          [HIGH_CONSENSUS] / [CONFLICT] tagging               │
│                        │                                      │
│                        ▼                                      │
│                  SignalEngine                                 │
│          Forum text → TradingSignal JSON                     │
│          Confidence aggregation + SL/TP calc                 │
│                        │                                      │
│                        ▼                                      │
│                  RiskManager                                  │
│          Position sizing + daily loss guard                  │
│                        │                                      │
│                        ▼                                      │
│              InjectiveExecutor                               │
│          iAgent SDK — perpetual open/close                   │
│          MCP natural language interface                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

**Multi-Agent Forum Debate**
Three agents with different data sources debate every 5 minutes. A Forum Host LLM moderates, identifies consensus or conflict, and directs the next research round via `[INVESTIGATE:topic]` tags.

**Structured Trading Signals**
Forum debate is parsed into a strict JSON schema: direction (LONG/SHORT/NEUTRAL), confidence score, entry range, stop-loss, take-profit levels, and source attribution.

```json
{
  "asset": "INJ",
  "signal": "LONG",
  "confidence": 0.82,
  "time_horizon": "4h",
  "entry_range": [24.85, 25.15],
  "stop_loss": 23.75,
  "take_profit": [27.00, 28.75],
  "consensus_tag": "HIGH_CONSENSUS",
  "reasoning": "Strong social bullish momentum confirmed by low funding rate."
}
```

**Injective-Native Execution**
Signals are executed directly via the Injective iAgent SDK. Supports testnet (default), mainnet, and a full mock mode for safe demos.

**MCP Natural Language Interface**
Send plain-text trade instructions that are parsed and executed on-chain:
```
"Buy 5% INJ with 2x leverage"  →  executed on Injective perpetuals
"做多 INJ 3% 2倍杠杆"           →  same result
```

**Risk Management**
- Position size = `total_capital × max_pct × profile_multiplier × confidence`
- Daily loss limit — auto-suspend when exceeded, reset at UTC 00:00
- Conservative / Medium / Aggressive risk profiles
- Exponential backoff retry on execution failure (3 attempts)

**Real-time Dashboard**
Flask + SocketIO dashboard with live signal cards, forum debate chat stream, position panel, and MCP command input. No page refresh needed.

---

## Quick Start

**Requirements:** Python 3.10+, pip

```bash
git clone https://github.com/airbate/novasentine.git
cd novasentine

pip install -r requirements.txt

cp .env.example .env
# Edit .env — at minimum set SIGNAL_ENGINE_API_KEY and FORUM_HOST_API_KEY

python nova_app.py
# Open http://localhost:5000
# Click "Start System"
```

**Zero-config demo** (mock mode, no real API keys needed):
```bash
# .env already has INJECTIVE_MOCK=true
# Set placeholder keys to run without real LLM:
SIGNAL_ENGINE_API_KEY=sk-placeholder
FORUM_HOST_API_KEY=sk-placeholder
```

---

## Configuration

All configuration is via `.env` (copy from `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `SIGNAL_ENGINE_API_KEY` | LLM for signal parsing (GPT-4o-mini recommended) | — |
| `FORUM_HOST_API_KEY` | LLM for forum moderation (Qwen/GPT) | — |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 bearer token | — |
| `REDDIT_CLIENT_ID` | Reddit app client ID | — |
| `COINGECKO_API_KEY` | CoinGecko Pro API key (optional) | — |
| `INJECTIVE_NETWORK` | `testnet` or `mainnet` | `testnet` |
| `INJECTIVE_PRIVATE_KEY` | Wallet private key (hex) | — |
| `INJECTIVE_MOCK` | `true` = no real funds used | `true` |
| `TOTAL_CAPITAL_USD` | Total trading capital | `10000` |
| `MAX_POSITION_PCT` | Max position size per trade | `0.05` |
| `MAX_DAILY_LOSS_PCT` | Daily loss limit before suspend | `0.02` |
| `RISK_PROFILE` | `conservative` / `medium` / `aggressive` | `medium` |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /` | GET | Dashboard UI |
| `/api/system/start` | POST | Start all agents + signal loop |
| `/api/system/stop` | POST | Stop all agents |
| `/api/signals` | GET | Last 20 signals from DB |
| `/api/positions` | GET | Current Injective positions |
| `/api/forum/log` | GET | Recent forum debate lines |
| `/api/mcp` | POST | Execute natural language trade command |

**MCP example:**
```bash
curl -X POST http://localhost:5000/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy 5% INJ 2x", "price": 25.0}'
```

---

## Project Structure

```
novasentine/
├── nova_app.py              # Main Flask app + signal loop + Dashboard
├── config.py                # Pydantic Settings (reads .env)
├── .env.example             # Environment variable template
│
├── SocialSentinel/          # Twitter, Reddit, CryptoPanic sentiment
├── OnChainSentinel/         # Injective RPC + CoinGecko market data
├── MacroSentinel/           # Macro event calendar + BTC dominance
│
├── ForumEngine/             # Multi-agent debate engine (from BettaFish)
│   ├── monitor.py           # Log watcher + tag parser
│   └── llm_host.py          # Forum Host LLM (trading-focused prompt)
│
├── SignalEngine/
│   ├── schema.py            # TradingSignal Pydantic model
│   ├── parser.py            # Forum text → JSON signal (LLM)
│   └── db.py                # SQLite signal persistence
│
├── RiskManager/
│   └── risk_manager.py      # Position sizing + daily loss guard
│
├── InjectiveExecutor/
│   ├── executor.py          # iAgent SDK wrapper (open/close/query)
│   └── mcp_interface.py     # Natural language trade parser
│
└── tests/
    ├── test_risk_manager.py  # 4 unit tests
    └── test_integration.py   # 39 integration tests (43 total, all passing)
```

---

## How the Forum Works

Every analysis round, three agents run in parallel and write their findings to individual log files. The ForumEngine monitors all three logs simultaneously:

1. When a `FirstSummaryNode` output is detected, a new forum session begins
2. Each agent's analysis is written to `forum.log` with a source tag (`[SOCIAL]`, `[ONCHAIN]`, `[MACRO]`)
3. After every 5 agent messages, the Forum Host LLM generates a moderator speech
4. The Host identifies `[HIGH_CONSENSUS]` or `[CONFLICT]` and issues `[INVESTIGATE:topic]` directives
5. SignalEngine reads the accumulated forum log and extracts a final `TradingSignal`

---

## Built On

NovaSentinel is built on top of [BettaFish](https://github.com/666ghj/BettaFish) (GPL-2.0), an open-source multi-agent public opinion analysis system. The ForumEngine, node architecture (~80%), and LLM wrappers (~90%) are preserved. Data sources were replaced with financial APIs and the output layer was replaced with Injective chain execution.

**Reused from BettaFish:** ForumEngine, Search→Summary→Reflect node pipeline, LLM client wrappers, config system, retry utilities

**New in NovaSentinel:** SocialSentinel, OnChainSentinel, MacroSentinel, SignalEngine, RiskManager, InjectiveExecutor, MCP interface, trading-focused Forum Host prompt

---

## License

GPL-2.0 — see [LICENSE](LICENSE)

---

<p align="center">
  Submitted to <b>Injective Nova 2026</b> · Built with ❤️ on Injective
</p>
