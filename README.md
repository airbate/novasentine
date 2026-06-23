# 🔱 NovaSentinel

<p align="center">
  <b>AI原生的情绪驱动交易信号引擎，运行在 Injective 上</b><br>
  <sub>三个 AI Agent 辩论。一个 Agent 在链上执行。</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Injective-iAgent_SDK-00B5D8?style=flat-square" />
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/测试-13通过-10B981?style=flat-square" />
  <img src="https://img.shields.io/badge/协议-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/Injective_Nova-2026-8B5CF6?style=flat-square" />
</p>

---

## 这是什么

大多数加密交易工具要么**分析**，要么**执行**——从不同时存在。NovaSentinel 把这件串联了起来：

```
社媒情绪  ┐
链上数据  ├─→ 多Agent论坛辩论 ─→ 交易信号 ─→ Injective链上执行
宏观事件  ┘
```

三个专业 AI Agent 从不同维度采集市场情报，在结构化论坛中辩论，Signal Engine 将共识转化为结构化的交易决策——然后通过iAgent SDK在Injective的永续合约市场上自主执行。

---

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                        NovaSentinel                          │
│                                                              │
│  SocialSentinel   OnChainSentinel   MacroSentinel            │
│  ─────────────    ──────────────    ─────────────            │
│  Twitter/X        Injective RPC     美联储/CPI日历            │
│  Reddit           CoinGecko         BTC主导率               │
│  CryptoPanic      OI / 资金费率     市场环境判断             │
│       │                │                  │                  │
│       └────────────────┼──────────────────┘                  │
│                        ▼                                      │
│                  ForumEngine                                  │
│          三Agent辩论 + LLM主持人对协议                      │
│          [HIGH_CONSENSUS] / [CONFLICT] 标签                 │
│                        │                                      │
│                        ▼                                      │
│                  SignalEngine                                 │
│          论坛文本 → 交易信号 JSON                            │
│          置信度聚合 + 止损止盈计算                           │
│                        │                                      │
│                        ▼                                      │
│                  RiskManager                                  │
│          仓位计算 + 日内亏损保护                             │
│                        │                                      │
│                        ▼                                      │
│              InjectiveExecutor                               │
│          iAgent SDK — 永续合约开仓/平仓                      │
│          MCP自然语言接口                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 核心功能

**多Agent论坛辩论**
三个Agent每5分钟辩论一次。由Forum Host LLM主持，识别共识或分歧，通过`[INVESTIGATE:topic]`标签引导下一轮研究方向。

**结构化交易信号**
论坛辩论被解析为严格的 JSON 结构：方向（做多/做空/观望）、置信度、入场区间、止损、止盈位。

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
  "reasoning": "社交媒体看多情绪强烈，同时链上资金费率处于低位。"
}
```

**Injective 原生执行**
信号通过 Injective iAgent SDK 直接执行。支持测试网（默认）、主网和完整的模拟模式用于安全演示。

**MCP 自然语言接口**
用人类语言下达交易指令，自动解析并在链上执行：
```
"Buy 5% INJ with 2x leverage"  →  在Injective永续合约上执行
"做多 INJ 3% 2倍杠杆"           →  同上
```

**风险管理**
- 仓位规模 = `总资金 × 最大仓位比例 × 风险档位系数 × 置信度`
- 日内亏损上限——触发后自动暂停，UTC 00:00 自动重置
- 保守 / 中等 / 激进 三种风险档位
- 执行失败指数退避重试（最多3次）

**实时仪表盘**
Flask + SocketIO 仪表盘，包含实时信号卡片、论坛辩论聊天流、持仓面板和 MCP 指令输入。无需刷新页面。

---

## 快速开始

**环境要求：** Python 3.10+, pip

```bash
git clone https://github.com/airbate/novasentine.git
cd novasentine

pip install -r requirements.txt

cp .env.example .env
# 编辑 .env — 必须填写 SIGNAL_ENGINE_API_KEY 和 FORUM_HOST_API_KEY

python nova_app.py
# 打开 http://localhost:5000
# 点击"Start System"
```

**零配置演示**（模拟模式，无需真实 API Key）：
```bash
# .env里INJECTIVE_MOCK=true已默认开启
SIGNAL_ENGINE_API_KEY=sk-placeholder
FORUM_HOST_API_KEY=sk-placeholder
```

---

## 配置说明

所有配置通过 `.env` 文件管理（从 `.env.example` 复制）：

| 变量 | 说明 | 默认值 |
|----------|-------------|---------|
| `SIGNAL_ENGINE_API_KEY` | 用于信号解析的LLM（推荐GPT-4o-mini） | — |
| `FORUM_HOST_API_KEY` | 用于论坛主持的LLM（推荐Qwen/GPT） | — |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 Bearer Token | — |
| `REDDIT_CLIENT_ID` | Reddit app client ID | — |
| `COINGECKO_API_KEY` | CoinGecko Pro API密钥（可选） | — |
| `INJECTIVE_NETWORK` | `testnet` 或 `mainnet` | `testnet` |
| `INJECTIVE_PRIVATE_KEY` | 钱包私钥（hex格式） | — |
| `INJECTIVE_MOCK` | `true`=不涉及真实资金 | `true` |
| `TOTAL_CAPITAL_USD` | 总交易资金 | `10000` |
| `MAX_POSITION_PCT` | 单笔最大仓位比例 | `0.05` |
| `MAX_DAILY_LOSS_PCT` | 触发暂停的日内亏损上限 | `0.02` |
| `RISK_PROFILE` | `conservative` / `medium` / `aggressive` | `medium` |

---

## API 参考

| 端点 | 方法 | 说明 |
|----------|--------|-------------|
| `GET /` | GET | 仪表盘界面 |
| `/api/system/start` | POST | 启动所有Agent + 信号循环 |
| `/api/system/stop` | POST | 停止所有Agent |
| `/api/signals` | GET | 最近20条信号（从数据库读取） |
| `/api/positions` | GET | 当前Injective持仓 |
| `/api/forum/log` | GET | 最近论坛辩论记录 |
| `/api/mcp` | POST | 执行自然语言交易指令 |

**MCP 示例：**
```bash
curl -X POST http://localhost:5000/api/mcp \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy 5% INJ 2x", "price": 25.0}'
```

---

## 项目结构

```
novasentine/
├── nova_app.py              # Flask主程序 + 信号循环 + 仪表盘
├── config.py                # Pydantic Settings（读取.env）
├── .env.example             # 环境变量模板
│
├── SocialSentinel/          # Twitter、Reddit、CryptoPanic 情绪分析
├── OnChainSentinel/         # Injective RPC + CoinGecko 市场数据
├── MacroSentinel/           # 宏观事件日历 + BTC主导率
│
├── ForumEngine/             # 多Agent辩论引擎
│   ├── monitor.py           # 日志监控 + 标签解析
│   └── llm_host.py          # Forum Host LLM
│
├── SignalEngine/
│   ├── schema.py            # TradingSignal 数据模型
│   ├── parser.py            # 论坛文本 → JSON信号（LLM）
│   └── db.py                # SQLite 信号持久化
│
├── RiskManager/
│   └── risk_manager.py      # 仓位计算 + 日内亏损保护
│
├── InjectiveExecutor/
│   ├── executor.py          # iAgent SDK封装（开仓/平仓/查询）
│   └── mcp_interface.py     # 自然语言交易指令解析器
│
└── tests/
    ├── test_risk_manager.py  # 4个单元测试
    └── test_integration.py   # 9个集成测试（共13个测试，全部通过）
```

---

## Forum 工作机制

每轮分析中，三个Agent并行运行，将分析结果写入各自的日志文件。ForumEngine同时监控三个日志：

1. 检测到 `FirstSummaryNode` 输出时，开始新一轮论坛会话
2. 每个Agent的分析记录写入 `forum.log`，标注来源标签（`[SOCIAL]`、`[ONCHAIN]`、`[MACRO]`）
3. 每累计5条Agent发言，Forum Host LLM生成一次主持人发言
4. 主持人识别 `[HIGH_CONSENSUS]` 或 `[CONFLICT]`，并发出 `[INVESTIGATE:topic]` 指令
5. SignalEngine 读取累积的论坛日志，提取最终的 `TradingSignal`

---

## 协议

MIT — 详见 [LICENSE](LICENSE)

---

<p align="center">
  Injective Nova 2026 参赛作品 · 在 Injective 上用心构建
</p>
