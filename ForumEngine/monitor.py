"""
ForumEngine monitor — original implementation, no BettaFish code.
Watches sentinel log files; extracts summaries and pushes them to forum.log.
"""
from __future__ import annotations
import re, threading, time
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

LOG_DIR = Path("logs")
FORUM_LOG = LOG_DIR / "forum.log"
SENTINEL_LOGS = {"SOCIAL": LOG_DIR/"social.log", "ONCHAIN": LOG_DIR/"onchain.log", "MACRO": LOG_DIR/"macro.log"}
HOST_TRIGGER = 5
IDLE_TIMEOUT = 7200
_investigate_hints: dict[str, str] = {}
_lock = threading.Lock()

def get_investigate_hints() -> dict[str, str]:
    with _lock: return dict(_investigate_hints)

def _set_hints(text: str) -> None:
    with _lock:
        for m in re.finditer(r"\[INVESTIGATE:([^\]]+)\]", text):
            topic = m.group(1).strip()
            pre = text[:text.index(m.group(0))][-120:].upper()
            agent = next((a for a in ("SOCIAL","ONCHAIN","MACRO") if a in pre), "ALL")
            _investigate_hints[agent] = topic

def _write(content: str, source: str = "SYSTEM") -> None:
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%H:%M:%S")
    line = content.replace("\n","\\n").replace("\r","")
    with open(FORUM_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] [{source}] {line}\n"); f.flush()

def get_forum_log() -> list[str]:
    if not FORUM_LOG.exists(): return []
    return [l.rstrip() for l in FORUM_LOG.read_text(encoding="utf-8", errors="ignore").splitlines() if l.strip()]

class _SentinelReader:
    MARKER = re.compile(r"(FirstSummaryNode|ReflectionSummaryNode|paragraph_latest_state)", re.I)
    def __init__(self, name: str, path: Path):
        self.name = name; self.path = path
        self._pos = path.stat().st_size if path.exists() else 0
    def read_new(self) -> list[str]:
        if not self.path.exists(): return []
        size = self.path.stat().st_size
        if size < self._pos: self._pos = 0
        if size == self._pos: return []
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(self._pos); text = f.read(); self._pos = f.tell()
        return [l.strip() for l in text.splitlines() if l.strip() and self.MARKER.search(l)]

class ForumMonitor:
    def __init__(self):
        self._running = False; self._thread: Optional[threading.Thread] = None
        self._readers: dict[str,_SentinelReader] = {}
        self._buffer: list[str] = []; self._active = False
    def start(self) -> bool:
        if self._running: return False
        LOG_DIR.mkdir(exist_ok=True)
        FORUM_LOG.write_text("", encoding="utf-8")
        _write(f"=== Forum session start {datetime.now():%Y-%m-%d %H:%M:%S} ===")
        self._readers = {n: _SentinelReader(n,p) for n,p in SENTINEL_LOGS.items()}
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start(); logger.info("ForumEngine: started"); return True
    def stop(self) -> None:
        self._running = False
        if self._thread: self._thread.join(timeout=3)
        _write(f"=== Forum session end {datetime.now():%Y-%m-%d %H:%M:%S} ===")
        logger.info("ForumEngine: stopped")
    def _loop(self) -> None:
        idle = 0
        while self._running:
            found = False
            for name, reader in self._readers.items():
                for line in reader.read_new():
                    self._active = True; idle = 0; found = True
                    summary = self._extract(line)
                    if summary:
                        _write(summary, name); self._buffer.append(f"[{name}] {summary}")
                        if len(self._buffer) >= HOST_TRIGGER: self._trigger_host()
            if self._active and not found:
                idle += 1
                if idle >= IDLE_TIMEOUT:
                    self._active = False; _write("=== Forum idle timeout ==="); idle = 0
            time.sleep(1)
    def _extract(self, line: str) -> Optional[str]:
        for key in ("updated_paragraph_latest_state","paragraph_latest_state"):
            m = re.search(rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"', line)
            if m: return m.group(1).replace("\\n","\n").replace('\\"','"')
        clean = re.sub(r"^\d{4}-\d{2}-\d{2}\s+[\d:.]+\s*\|\s*\w+\s*\|\s*[^-]+-\s*","",line)
        clean = re.sub(r"^\[[\d:]+\]\s*","",clean).strip()
        return clean if len(clean) > 40 else None
    def _trigger_host(self) -> None:
        speeches = list(self._buffer); self._buffer.clear()
        try:
            from ForumEngine.llm_host import generate_host_speech
            speech = generate_host_speech(speeches)
            if speech:
                _write(speech, "HOST"); _set_hints(speech)
                tag = "[HIGH_CONSENSUS]" if "[HIGH_CONSENSUS]" in speech else "[CONFLICT]" if "[CONFLICT]" in speech else ""
                if tag: logger.info(f"ForumEngine: {tag} detected")
        except Exception as e:
            logger.warning(f"ForumEngine: host speech failed ({e})")

_monitor: Optional[ForumMonitor] = None

def start_forum_monitoring() -> bool:
    global _monitor; _monitor = ForumMonitor(); return _monitor.start()

def stop_forum_monitoring() -> None:
    if _monitor: _monitor.stop()
