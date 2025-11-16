"""
Analytics package for Moon Dev trading bot.

Provides helpers to record structured events and consolidate them into
weekly performance summaries without disrupting the live trading loop.
"""

from .recorder import get_analytics_recorder, AnalyticsRecorder, NullAnalyticsRecorder
from .reporting import generate_period_summary, save_period_summary
from .reporter import AnalyticsReporter
from .report_scheduler import AnalyticsReportScheduler

__all__ = [
    "get_analytics_recorder",
    "AnalyticsRecorder",
    "NullAnalyticsRecorder",
    "generate_period_summary",
    "save_period_summary",
    "AnalyticsReporter",
    "AnalyticsReportScheduler",
]

