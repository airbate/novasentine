"""
NovaSentinel — main Flask application.
Wires together: 3 Sentinels → ForumEngine → SignalEngine → RiskManager → InjectiveExecutor
"""

import os
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request
from flask_socketio import SocketIO, emit
from loguru import logger
from openai import OpenAI

from config import settings
from ForumEngine.monitor import start_forum_monitoring, stop_forum_monitoring, get_forum_log
from SignalEngine.schema import TradingSignal, SignalStatus
from SignalEngine.parser import SignalParser
from SignalEngine.db import save_signal, get_recent_signals, mark_signal_result
from RiskManager.risk_manager import RiskManager, RiskConfig
from InjectiveExecutor.executor import InjectiveExecutor
from InjectiveExecutor.mcp_interface import MCPInterface
from OnChainSentinel.tools.coingecko_client import CoinGeckoClient

app = Flask(__name__)
app.config["SECRET_KEY"] = "novasentinel-injective-nova-2026"
socketio = SocketIO(app, cors_allowed_origins="*")

# ── Global singletons (lazy-initialized on first /api/system/start) ──────────

_llm = None
_signal_parser = None
_risk_manager = RiskManager(RiskConfig(
    total_capital_usd=float(os.getenv("TOTAL_CAPITAL_USD", "10000")),
    max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.05")),
    max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", "0.02")),
    max_leverage=int(os.getenv("MAX_LEVERAGE", "3")),
    profile=os.getenv("RISK_PROFILE", "medium"),
))
_executor = InjectiveExecutor(
    private_key_hex=os.getenv("INJECTIVE_PRIVATE_KEY", ""),
    network=os.getenv("INJECTIVE_NETWORK", "testnet"),
    mock=os.getenv("INJECTIVE_MOCK", "true").lower() == "true",
)
_coingecko = CoinGeckoClient(api_key=os.getenv("COINGECKO_API_KEY"))

active_signals: list[dict] = []


_mcp = MCPInterface(_executor, _risk_manager)


# ── Signal generation loop ────────────────────────────────────────────────────

def _signal_loop():
    """Background thread: every 5 minutes, parse forum log → signal → execute."""
    while True:
        try:
            forum_lines = get_forum_log()
            if len(forum_lines) < 10:
                time.sleep(60)
                continue

            forum_text = "\n".join(forum_lines[-200:])
            market = _coingecko.get_market_data("INJ")
            current_price = market.price_usd if market else 0.0

            signal = _signal_parser.parse(forum_text, "INJ", current_price)
            approved, reason, size_usd = _risk_manager.approve(signal)

            logger.info(f"Signal: {signal.signal} conf={signal.confidence:.2f} approved={approved} ({reason})")

            if approved and size_usd > 0:
                result = _executor.open_position(signal, size_usd)
                if result.success:
                    signal.tx_hash = result.tx_hash
                else:
                    signal.status = SignalStatus.EXEC_FAILED

            save_signal(signal)   # Task 6.5: persist every signal

            sig_dict = signal.model_dump(mode="json")
            active_signals.append(sig_dict)
            if len(active_signals) > 100:
                active_signals.pop(0)

            socketio.emit("new_signal", sig_dict)

        except Exception as e:
            logger.exception(f"Signal loop error: {e}")

        time.sleep(300)  # 5 min


# ── Routes ────────────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
<title>NovaSentinel</title>
<style>
body{font-family:monospace;background:#0d1117;color:#c9d1d9;padding:20px}
h1{color:#58a6ff}.signal-card{border:1px solid #30363d;border-radius:8px;padding:12px;margin:8px 0}
.LONG{border-left:4px solid #3fb950}.SHORT{border-left:4px solid #f85149}.NEUTRAL{border-left:4px solid #8b949e}
.forum-msg{padding:6px;border-bottom:1px solid #21262d;font-size:12px}
.SOCIAL{color:#79c0ff}.ONCHAIN{color:#56d364}.MACRO{color:#e3b341}.HOST{color:#f0883e;font-weight:bold}
</style>
</head>
<body>
<h1>🔱 NovaSentinel — AI Trading Signal Engine</h1>
<p>Powered by BettaFish ForumEngine × Injective iAgent SDK</p>
<div style="display:flex;gap:20px">
  <div style="flex:1"><h3>📊 Latest Signals</h3><div id="signals"></div></div>
  <div style="flex:1"><h3>💬 Forum Debate</h3><div id="forum" style="height:400px;overflow-y:auto"></div></div>
</div>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const io = window.io();
const sigDiv = document.getElementById('signals');
const forumDiv = document.getElementById('forum');
io.on('new_signal', s => {
  const c = document.createElement('div');
  c.className = 'signal-card ' + s.signal;
  c.innerHTML = `<b>${s.signal}</b> ${s.asset} | conf: ${(s.confidence*100).toFixed(1)}% | ${s.consensus_tag}<br>
    <small>${s.reasoning}</small><br>
    <small>SL: ${s.stop_loss} | TP: ${s.take_profit.join(', ')} | tx: ${s.tx_hash||'-'}</small>`;
  sigDiv.prepend(c);
});
io.on('forum_message', m => {
  const d = document.createElement('div');
  d.className = 'forum-msg';
  d.innerHTML = `<span class="${m.sender.split(' ')[0].toUpperCase()}">[${m.sender}]</span> ${m.content}`;
  forumDiv.prepend(d);
});
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/signals")
def get_signals():
    return jsonify(get_recent_signals(20))      # Task 6.5: from DB


@app.route("/api/signals/<signal_id>/result", methods=["POST"])
def update_signal_result():                     # Task 6.6: mark TP/SL
    data = request.get_json() or {}
    mark_signal_result(data["signal_id"], data["status"])
    return jsonify({"success": True})


@app.route("/api/mcp", methods=["POST"])
def mcp_command():                              # Task 8.6: natural language trading
    data = request.get_json() or {}
    text = data.get("text", "")
    price = float(data.get("price", 0))
    result = _mcp.handle(text, price)
    return jsonify(result)


@app.route("/api/positions")
def get_positions():
    return jsonify(_executor.query_positions())


@app.route("/api/forum/log")
def forum_log():
    return jsonify({"lines": get_forum_log()[-100:]})


@app.route("/api/system/start", methods=["POST"])
def start_system():
    start_forum_monitoring()
    t = threading.Thread(target=_signal_loop, daemon=True)
    t.start()
    return jsonify({"success": True, "message": "NovaSentinel started"})


@app.route("/api/system/stop", methods=["POST"])
def stop_system():
    stop_forum_monitoring()
    return jsonify({"success": True})


@socketio.on("connect")
def on_connect():
    emit("status", "Connected to NovaSentinel")


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    logger.info(f"NovaSentinel starting on http://{host}:{port}")
    socketio.run(app, host=host, port=port, debug=False)
