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
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NovaSentinel</title>
<style>
:root{
  --bg:#0a0e1a;--surface:#111827;--border:#1f2937;--text:#e2e8f0;--muted:#6b7280;
  --green:#10b981;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6;--purple:#8b5cf6;--orange:#f97316;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
/* header */
.header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 24px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:10}
.logo{font-size:22px;font-weight:700;background:linear-gradient(135deg,#3b82f6,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.badge{font-size:11px;padding:2px 8px;border-radius:99px;font-weight:600}
.badge-mock{background:#1f2937;color:#f59e0b;border:1px solid #f59e0b44}
.badge-live{background:#0621124d;color:#10b981;border:1px solid #10b98144}
.header-right{margin-left:auto;display:flex;align-items:center;gap:10px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);box-shadow:0 0 6px var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
/* layout */
.main{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto 1fr;gap:16px;padding:16px;max-width:1400px;margin:0 auto}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.panel-header{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.panel-title{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.panel-body{padding:12px;overflow-y:auto;max-height:480px}
/* stats row */
.stats{grid-column:1/-1;display:grid;grid-template-columns:repeat(5,1fr);gap:12px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.stat-label{font-size:11px;color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
.stat-value{font-size:22px;font-weight:700}
.stat-sub{font-size:11px;color:var(--muted);margin-top:2px}
/* signal cards */
.sig-card{border-radius:8px;padding:12px;margin-bottom:8px;border-left:3px solid;background:#0d1425}
.sig-card.LONG{border-color:var(--green)}
.sig-card.SHORT{border-color:var(--red)}
.sig-card.NEUTRAL{border-color:var(--muted)}
.sig-top{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.sig-dir{font-size:13px;font-weight:700;padding:2px 10px;border-radius:4px}
.LONG .sig-dir{background:#10b98120;color:var(--green)}
.SHORT .sig-dir{background:#ef444420;color:var(--red)}
.NEUTRAL .sig-dir{background:#6b728020;color:var(--muted)}
.sig-asset{font-size:15px;font-weight:700}
.sig-conf{margin-left:auto;font-size:12px;color:var(--muted)}
.conf-bar{height:4px;background:#1f2937;border-radius:2px;margin:6px 0}
.conf-fill{height:100%;border-radius:2px;background:var(--blue);transition:width .5s}
.sig-meta{display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px;color:var(--muted);margin-top:6px}
.sig-meta span{display:flex;gap:4px}
.sig-meta b{color:var(--text)}
.sig-reason{font-size:12px;color:#94a3b8;margin-top:6px;line-height:1.5}
.tag{font-size:10px;padding:1px 6px;border-radius:3px;font-weight:600}
.tag-consensus{background:#3b82f620;color:var(--blue)}
.tag-conflict{background:#ef444420;color:var(--red)}
.tag-tx{background:#8b5cf620;color:var(--purple)}
/* forum */
.msg{padding:10px 12px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:flex-start}
.msg:last-child{border-bottom:none}
.msg-avatar{width:28px;height:28px;border-radius:6px;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:1px}
.av-SOCIAL{background:#1e3a5f;color:var(--blue)}
.av-ONCHAIN{background:#14532d;color:var(--green)}
.av-MACRO{background:#451a03;color:var(--yellow)}
.av-HOST{background:#2e1065;color:var(--purple)}
.msg-body{}
.msg-sender{font-size:11px;font-weight:600;margin-bottom:3px}
.sn-SOCIAL{color:var(--blue)}.sn-ONCHAIN{color:var(--green)}.sn-MACRO{color:var(--yellow)}.sn-HOST{color:var(--purple)}
.msg-text{font-size:12px;color:#cbd5e1;line-height:1.6}
.msg-time{font-size:10px;color:var(--muted);margin-left:auto;flex-shrink:0}
/* mcp input */
.mcp-bar{padding:12px;border-top:1px solid var(--border);display:flex;gap:8px}
.mcp-bar input{flex:1;background:#0d1425;border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-size:13px;outline:none}
.mcp-bar input:focus{border-color:var(--blue)}
.mcp-bar button{background:var(--blue);border:none;border-radius:6px;padding:8px 16px;color:#fff;font-weight:600;cursor:pointer;font-size:13px}
.mcp-bar button:hover{background:#2563eb}
/* empty state */
.empty{text-align:center;padding:40px 20px;color:var(--muted);font-size:13px}
.empty-icon{font-size:32px;margin-bottom:8px}
/* start button */
.start-btn{background:linear-gradient(135deg,#3b82f6,#8b5cf6);border:none;border-radius:8px;padding:10px 20px;color:#fff;font-weight:600;cursor:pointer;font-size:14px}
.start-btn:hover{opacity:.9}
.start-btn:disabled{opacity:.5;cursor:default}
</style>
</head>
<body>

<div class="header">
  <span class="logo">🔱 NovaSentinel</span>
  <span class="badge badge-mock" id="network-badge">MOCK</span>
  <span style="font-size:12px;color:var(--muted)">AI Sentiment → Trading Signal → Injective</span>
  <div class="header-right">
    <span class="dot" id="status-dot" style="background:var(--muted);box-shadow:none"></span>
    <span style="font-size:12px;color:var(--muted)" id="status-text">Stopped</span>
    <button class="start-btn" id="start-btn" onclick="startSystem()">Start System</button>
  </div>
</div>

<div class="main">
  <!-- Stats Row -->
  <div class="stats">
    <div class="stat-card">
      <div class="stat-label">Total Signals</div>
      <div class="stat-value" id="s-total">0</div>
      <div class="stat-sub">all time</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">LONG</div>
      <div class="stat-value" style="color:var(--green)" id="s-long">0</div>
      <div class="stat-sub">bullish signals</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">SHORT</div>
      <div class="stat-value" style="color:var(--red)" id="s-short">0</div>
      <div class="stat-sub">bearish signals</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Avg Confidence</div>
      <div class="stat-value" style="color:var(--blue)" id="s-conf">—</div>
      <div class="stat-sub">weighted mean</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Forum Messages</div>
      <div class="stat-value" style="color:var(--purple)" id="s-forum">0</div>
      <div class="stat-sub">debate rounds</div>
    </div>
  </div>

  <!-- Signals Panel -->
  <div class="panel">
    <div class="panel-header">
      <span class="panel-title">📊 Latest Signals</span>
      <span style="font-size:11px;color:var(--muted)" id="sig-count">0 signals</span>
    </div>
    <div class="panel-body" id="signals">
      <div class="empty"><div class="empty-icon">📡</div>Waiting for signals…</div>
    </div>
  </div>

  <!-- Forum Panel -->
  <div class="panel" style="display:flex;flex-direction:column">
    <div class="panel-header">
      <span class="panel-title">💬 Forum Debate</span>
      <span style="font-size:11px;color:var(--muted)" id="forum-count">0 messages</span>
    </div>
    <div class="panel-body" id="forum" style="flex:1">
      <div class="empty"><div class="empty-icon">🤖</div>Agents will debate here…</div>
    </div>
    <div class="mcp-bar">
      <input id="mcp-input" placeholder='Natural language trade: "Buy 5% INJ 2x" …' onkeydown="if(event.key==='Enter')sendMCP()">
      <button onclick="sendMCP()">Execute</button>
    </div>
  </div>
</div>

<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<script>
const socket = io();
let sigCount=0, longCount=0, shortCount=0, totalConf=0, forumCount=0;

// ── helpers ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const tag = (cls,txt) => `<span class="tag ${cls}">${txt}</span>`;
const time = () => new Date().toLocaleTimeString('en',{hour:'2-digit',minute:'2-digit'});
const SENDER_ABBR = {SOCIAL:'SO',ONCHAIN:'ON',MACRO:'MA','Forum Host':'HO'};

function updateStats(){
  $('s-total').textContent = sigCount;
  $('s-long').textContent  = longCount;
  $('s-short').textContent = shortCount;
  $('s-conf').textContent  = sigCount ? (totalConf/sigCount*100).toFixed(0)+'%' : '—';
  $('s-forum').textContent = forumCount;
  $('sig-count').textContent = sigCount+' signal'+(sigCount!==1?'s':'');
  $('forum-count').textContent = forumCount+' message'+(forumCount!==1?'s':'');
}

// ── render signal card ────────────────────────────────────────────────────────
function renderSignal(s){
  const consensusTag = s.consensus_tag==='HIGH_CONSENSUS'
    ? tag('tag-consensus','✓ HIGH CONSENSUS')
    : s.consensus_tag==='CONFLICT'
    ? tag('tag-conflict','⚡ CONFLICT')
    : '';
  const txTag = s.tx_hash ? tag('tag-tx','⛓ '+s.tx_hash.slice(0,14)+'…') : '';
  const conf = (s.confidence*100).toFixed(1);
  const tps = (s.take_profit||[]).map(p=>'$'+p).join(' / ');
  const div = document.createElement('div');
  div.className = 'sig-card '+s.signal;
  div.innerHTML = `
    <div class="sig-top">
      <span class="sig-dir">${s.signal}</span>
      <span class="sig-asset">${s.asset}</span>
      ${consensusTag}${txTag}
      <span class="sig-conf">${conf}% conf · ${s.time_horizon||'4h'}</span>
    </div>
    <div class="conf-bar"><div class="conf-fill" style="width:${conf}%"></div></div>
    ${s.reasoning?`<div class="sig-reason">${s.reasoning}</div>`:''}
    <div class="sig-meta">
      <span><b>SL</b> $${s.stop_loss||'—'}</span>
      <span><b>TP</b> ${tps||'—'}</span>
    </div>`;
  const box = $('signals');
  if(box.querySelector('.empty')) box.innerHTML='';
  box.prepend(div);
  if(box.children.length>30) box.removeChild(box.lastChild);
}

// ── render forum message ──────────────────────────────────────────────────────
function renderForum(m){
  const src = m.sender||m.source||'?';
  const key = src.split(' ')[0].toUpperCase();
  const abbr = SENDER_ABBR[src]||SENDER_ABBR[key]||src.slice(0,2).toUpperCase();
  const div = document.createElement('div');
  div.className = 'msg';
  div.innerHTML = `
    <div class="msg-avatar av-${key}">${abbr}</div>
    <div class="msg-body">
      <div class="msg-sender sn-${key}">${src}</div>
      <div class="msg-text">${(m.content||'').replace(/\\n/g,'<br>')}</div>
    </div>
    <span class="msg-time">${m.timestamp||time()}</span>`;
  const box = $('forum');
  if(box.querySelector('.empty')) box.innerHTML='';
  box.prepend(div);
  if(box.children.length>100) box.removeChild(box.lastChild);
}

// ── socket events ─────────────────────────────────────────────────────────────
socket.on('connect', ()=>{
  $('status-dot').style.cssText='background:var(--green);box-shadow:0 0 6px var(--green)';
  $('status-text').textContent='Connected';
});
socket.on('disconnect',()=>{
  $('status-dot').style.cssText='background:var(--red);box-shadow:none';
  $('status-text').textContent='Disconnected';
});
socket.on('new_signal', s=>{
  sigCount++; totalConf+=s.confidence;
  if(s.signal==='LONG') longCount++;
  if(s.signal==='SHORT') shortCount++;
  renderSignal(s); updateStats();
});
socket.on('forum_message', m=>{ forumCount++; renderForum(m); updateStats(); });

// ── system control ────────────────────────────────────────────────────────────
async function startSystem(){
  const btn = $('start-btn');
  btn.disabled=true; btn.textContent='Starting…';
  const r = await fetch('/api/system/start',{method:'POST'}).then(r=>r.json()).catch(()=>({success:false}));
  if(r.success){
    btn.textContent='Running';
    $('status-text').textContent='Active';
    $('network-badge').textContent=document.querySelector('.badge-mock')? 'MOCK':'LIVE';
  } else {
    btn.disabled=false; btn.textContent='Retry';
  }
}

// ── MCP ───────────────────────────────────────────────────────────────────────
async function sendMCP(){
  const inp = $('mcp-input');
  const text = inp.value.trim();
  if(!text) return;
  inp.value=''; inp.placeholder='Sending…';
  const r = await fetch('/api/mcp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,price:0})}).then(r=>r.json()).catch(()=>({success:false}));
  inp.placeholder = r.success
    ? `✓ Executed: ${r.tx_hash||'mock'} — type another command`
    : `✗ ${r.error||'Failed'} — try again`;
}

// ── load history on page open ─────────────────────────────────────────────────
fetch('/api/signals').then(r=>r.json()).then(list=>{
  (list||[]).slice(0,10).reverse().forEach(s=>{
    sigCount++; totalConf+=s.confidence||0;
    if(s.signal==='LONG') longCount++;
    if(s.signal==='SHORT') shortCount++;
    renderSignal(s);
  }); updateStats();
});
fetch('/api/forum/log').then(r=>r.json()).then(d=>{
  const lines=(d.lines||[]).slice(-20);
  lines.forEach(l=>{
    const m=l.match(/\[(\d+:\d+:\d+)\]\s*\[(\w+)\]\s*(.*)/);
    if(m) renderForum({timestamp:m[1],sender:m[2],content:m[3]});
  }); forumCount+=lines.length; updateStats();
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
