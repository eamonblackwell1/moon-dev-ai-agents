"""
Background scheduler that triggers analytics reports on a cadence.
"""

from __future__ import annotations

import threading
from datetime import datetime, time, timedelta
from typing import Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback not expected
    ZoneInfo = None  # type: ignore

from termcolor import cprint

from src import config as app_config
from src.analytics.reporter import AnalyticsReporter


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(hour=int(hour), minute=int(minute))


class AnalyticsReportScheduler:
    """Simple background scheduler to run daily and weekly reports."""

    def __init__(
        self,
        reporter: AnalyticsReporter,
        timezone_name: str = app_config.ANALYTICS_REPORT_TIMEZONE,
        daily_time: str = app_config.ANALYTICS_DAILY_REPORT_TIME,
        weekly_day: int = app_config.ANALYTICS_WEEKLY_REPORT_DAY,
        weekly_time: str = app_config.ANALYTICS_WEEKLY_REPORT_TIME,
        enabled: bool = app_config.ANALYTICS_REPORTING_ENABLED,
    ) -> None:
        self.reporter = reporter
        self.enabled = enabled
        self.daily_time = _parse_time(daily_time)
        self.weekly_time = _parse_time(weekly_time)
        self.weekly_day = weekly_day % 7

        if ZoneInfo:
            self.timezone = ZoneInfo(timezone_name)
        else:  # pragma: no cover - fallback
            self.timezone = None

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._next_daily_run: Optional[datetime] = None
        self._next_weekly_run: Optional[datetime] = None

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        if not self.enabled:
            cprint("[analytics] Reporting scheduler disabled via config.", "yellow")
            return

        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._next_daily_run = self._compute_next_daily()
            self._next_weekly_run = self._compute_next_weekly()

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            cprint("[analytics] Reporting scheduler started.", "green")

    def stop(self) -> None:
        with self._lock:
            if not self._thread:
                return
            self._stop_event.set()
            self._thread.join(timeout=5)
            self._thread = None
            cprint("[analytics] Reporting scheduler stopped.", "yellow")

    def trigger_report(self, report_type: str):
        cprint(f"[analytics] Manual trigger for {report_type} report.", "cyan")
        return self.reporter.generate_report(report_type)

    # ------------------------------------------------------------------ #
    def _run_loop(self):
        while not self._stop_event.is_set():
            now = self._now()

            if self._next_daily_run and now >= self._next_daily_run:
                self._safe_generate("daily")
                self._next_daily_run = self._compute_next_daily(now + timedelta(seconds=30))

            if self._next_weekly_run and now >= self._next_weekly_run:
                self._safe_generate("weekly")
                self._next_weekly_run = self._compute_next_weekly(now + timedelta(seconds=30))

            self._stop_event.wait(timeout=30)

    def _safe_generate(self, report_type: str):
        try:
            self.reporter.generate_report(report_type)
        except Exception as exc:  # pragma: no cover - defensive
            cprint(f"[analytics] {report_type.title()} report generation failed: {exc}", "red")

    def _now(self) -> datetime:
        if self.timezone:
            return datetime.now(self.timezone)
        return datetime.utcnow()

    def _compute_next_daily(self, ref: Optional[datetime] = None) -> datetime:
        ref = ref or self._now()
        target = datetime.combine(ref.date(), self.daily_time)
        if self.timezone:
            target = target.replace(tzinfo=self.timezone)
        if target <= ref:
            target += timedelta(days=1)
        return target

    def _compute_next_weekly(self, ref: Optional[datetime] = None) -> datetime:
        ref = ref or self._now()
        dow = ref.weekday()
        days_ahead = self.weekly_day - dow
        if days_ahead < 0 or (days_ahead == 0 and ref.time() >= self.weekly_time):
            days_ahead += 7
        target_date = ref.date() + timedelta(days=days_ahead)
        target = datetime.combine(target_date, self.weekly_time)
        if self.timezone:
            target = target.replace(tzinfo=self.timezone)
        return target

