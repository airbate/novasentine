"""Tasks 4.1-4.2: Macro event calendar and BTC dominance tracker."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from loguru import logger


@dataclass
class MacroEvent:
    title: str
    impact: str          # "HIGH" | "MEDIUM" | "LOW"
    scheduled_at: datetime
    description: str = ""


# Static high-impact calendar — refreshed manually or via external API
STATIC_EVENTS: list[MacroEvent] = [
    MacroEvent("FOMC Rate Decision", "HIGH", datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc)),
    MacroEvent("US CPI Release", "HIGH", datetime(2026, 7, 14, 12, 30, tzinfo=timezone.utc)),
    MacroEvent("US Non-Farm Payrolls", "HIGH", datetime(2026, 8, 7, 12, 30, tzinfo=timezone.utc)),
]


class MacroCalendar:
    """Task 4.1: Upcoming high-impact event detection with confidence penalty."""

    WARNING_HOURS = 24

    def upcoming_events(self, within_hours: int = 48) -> list[MacroEvent]:
        now = datetime.now(tz=timezone.utc)
        return [
            e for e in STATIC_EVENTS
            if 0 <= (e.scheduled_at - now).total_seconds() <= within_hours * 3600
        ]

    def confidence_multiplier(self) -> float:
        """Return confidence adjustment based on proximity to high-impact events."""
        events = self.upcoming_events(within_hours=2)   # within 2h → active window
        if events:
            return 0.8
        warning = self.upcoming_events(within_hours=self.WARNING_HOURS)
        if warning:
            return 0.9
        return 1.0

    def context_text(self) -> str:
        events = self.upcoming_events()
        if not events:
            return "No high-impact macro events in the next 48 hours."
        lines = [f"- {e.title} ({e.impact}) at {e.scheduled_at.strftime('%Y-%m-%d %H:%M UTC')}" for e in events]
        return "UPCOMING MACRO EVENTS:\n" + "\n".join(lines)
