"""
Analytics reporting utilities sitting on top of the event recorder.

Generates daily/weekly summaries, asks an LLM for commentary, and stores the
rendered reports for the dashboard and notifications.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from termcolor import cprint

from src import config as app_config
from src.analytics.reporting import generate_period_summary
from src.models.model_factory import model_factory

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime(ISO_FORMAT)


def _truncate_series(series: List[Dict], limit: int = 50) -> List[Dict]:
    if not series:
        return []
    if len(series) <= limit:
        return series
    return series[-limit:]


@dataclass
class NarrativeResult:
    headline: str
    key_takeaways: List[str]
    risk_notes: List[str]
    next_actions: List[str]
    tone: str
    summary: str
    raw_text: str


class AnalyticsReporter:
    """Generates structured analytics reports and LLM narratives."""

    def __init__(
        self,
        reports_dir: str = app_config.ANALYTICS_REPORTS_DIR,
        model_type: str = app_config.ANALYTICS_REPORT_MODEL_TYPE,
        model_name: str = app_config.ANALYTICS_REPORT_MODEL_NAME,
        max_output_tokens: int = app_config.ANALYTICS_REPORT_MAX_OUTPUT_TOKENS,
        tone: str = app_config.ANALYTICS_REPORT_TONE,
        daily_days: int = app_config.ANALYTICS_DAILY_SUMMARY_DAYS,
        weekly_days: int = app_config.ANALYTICS_WEEKLY_SUMMARY_DAYS,
    ) -> None:
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.model_type = model_type
        self.model_name = model_name
        self.max_output_tokens = max_output_tokens
        self.tone = tone
        self.daily_days = max(daily_days, 1)
        self.weekly_days = max(weekly_days, 1)

        self._model = None

    # ------------------------------------------------------------------ #
    # Public helpers
    # ------------------------------------------------------------------ #
    def generate_report(self, report_type: str) -> Optional[Dict]:
        """Create and persist a report of the requested type."""
        report_type = report_type.lower()

        if report_type not in {"daily", "weekly"}:
            cprint(f"[analytics] Unsupported report type requested: {report_type}", "red")
            return None

        days = self.daily_days if report_type == "daily" else self.weekly_days
        summary = generate_period_summary(days=days)

        narrative = self._build_narrative(report_type, summary)

        report_payload = {
            "report_type": report_type,
            "generated_at": _utc_now_iso(),
            "period": summary["period"],
            "metrics": summary,
            "narrative": narrative.__dict__ if narrative else None,
            "model": {
                "type": self.model_type,
                "name": getattr(self._model, "model_name", self.model_name),
            },
        }

        filename = self._report_filename(report_type, report_payload["generated_at"])
        with filename.open("w", encoding="utf-8") as handle:
            json.dump(report_payload, handle, indent=2)

        return report_payload

    def load_latest_report(self, report_type: str) -> Optional[Dict]:
        """Load the latest generated report of a given type."""
        files = sorted(
            self.reports_dir.glob(f"{report_type.lower()}_*.json"),
            reverse=True,
        )
        for file_path in files:
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    return json.load(handle)
            except Exception as exc:
                cprint(f"[analytics] Failed to load report {file_path.name}: {exc}", "yellow")
        return None

    def list_reports(self, report_type: str, limit: int = 10) -> List[Dict]:
        """Return the most recent reports for listing/history views."""
        items: List[Dict] = []
        files = sorted(
            self.reports_dir.glob(f"{report_type.lower()}_*.json"),
            reverse=True,
        )
        for file_path in files[:limit]:
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    items.append(json.load(handle))
            except Exception as exc:
                cprint(f"[analytics] Failed to load report {file_path.name}: {exc}", "yellow")
        return items

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _report_filename(self, report_type: str, generated_at: str) -> Path:
        timestamp = generated_at.replace(":", "").replace("-", "")
        return self.reports_dir / f"{report_type}_{timestamp}.json"

    def _build_llm_payload(self, report_type: str, summary: Dict) -> Dict:
        """Reduce the full summary to the key context we want to send to the LLM."""
        flow = summary["trading"].get("flow_by_token_usd", {})
        top_tokens = sorted(flow.items(), key=lambda item: abs(item[1]), reverse=True)[:5]

        payload = {
            "report_type": report_type,
            "period": summary["period"],
            "performance": summary["performance"],
            "trading": {
                "total_trades": summary["trading"]["total_trades"],
                "buy_count": summary["trading"]["buy_count"],
                "sell_count": summary["trading"]["sell_count"],
                "net_capital_flow_usd": summary["trading"]["net_capital_flow_usd"],
                "top_token_flows": top_tokens,
                "recent": summary["trading"]["recent"][:5],
            },
            "signals": {
                "total_signals": summary["signals"]["total_signals"],
                "average_confidence": summary["signals"]["average_confidence"],
                "action_breakdown": summary["signals"]["action_breakdown"],
                "recent": summary["signals"]["recent"][:5],
            },
            "portfolio": {
                "series_tail": _truncate_series(summary["portfolio"]["series"], limit=30),
                "last_snapshot": summary["portfolio"]["last_snapshot"],
            },
        }
        return payload

    def _build_narrative(self, report_type: str, summary: Dict) -> NarrativeResult:
        payload = self._build_llm_payload(report_type, summary)
        formatted_payload = json.dumps(payload, indent=2)

        system_prompt = (
            "You are a trading performance analyst with deep expertise in cryptocurrency and meme coin trades. "
            "Write concise, insight-packed recaps of the trading bot's results. "
            "Base every statement on the provided metrics, be direct, "
            f"and keep the tone {self.tone}."
        )

        user_prompt = (
            "Summarize the trading performance for stakeholders.\n"
            "You must return a valid JSON object with the following structure:\n"
            "{\n"
            '  "headline": string,\n'
            '  "key_takeaways": [string, ...],\n'
            '  "risk_notes": [string, ...],\n'
            '  "next_actions": [string, ...],\n'
            '  "tone": string,\n'
            '  "summary": string,\n'
            '  "strategy": {\n'
            '    "name": string,\n'
            '    "pattern": string,\n'
            '    "evidence": [string, ...],\n'
            '    "expected_edge": string,\n'
            '    "pros": [string, ...],\n'
            '    "cons": [string, ...],\n'
            '    "confidence": number\n'
            '  } | null\n'
            "}\n"
            "Analyze the metrics for repeatable, data-backed edges. "
            "Only include a strategy object if the evidence shows a convincing, potentially profitable pattern; otherwise set \"strategy\" to null. "
            "If proposing a strategy, steelman the case with concrete metrics (e.g., clustered PnL, token flow surges, signal win rates) "
            "and list equally concrete drawbacks or failure modes.\n"
            "Keep key_takeaways to 3 items max. Mention concrete metrics (with units) when relevant. "
            "Highlight anomalies, risk, and what to watch next.\n\n"
            f"Report type: {report_type.upper()}\n"
            f"Metrics:\n{formatted_payload}"
        )

        response = self._invoke_model(system_prompt, user_prompt)

        if response:
            parsed = self._parse_narrative_json(response.content)
            if parsed:
                return parsed

        # Fallback narrative if parsing fails
        return self._fallback_narrative(report_type, summary, response.content if response else "")

    def _invoke_model(self, system_prompt: str, user_prompt: str):
        """Call the model factory with defensive error handling."""
        try:
            if not self._model:
                self._model = model_factory.get_model(self.model_type, self.model_name)
            if not self._model:
                cprint(f"[analytics] Model '{self.model_type}' not available for reporting.", "red")
                return None

            cprint(f"[analytics] Requesting {self.model_type}:{self._model.model_name} summary...", "cyan")
            return self._model.generate_response(
                system_prompt=system_prompt,
                user_content=user_prompt,
                max_tokens=self.max_output_tokens,
            )
        except Exception as exc:
            cprint(f"[analytics] LLM summary generation failed: {exc}", "red")
            return None

    def _parse_narrative_json(self, content: str) -> Optional[NarrativeResult]:
        try:
            # Some models may wrap JSON in code fences
            stripped = content.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`")
                if stripped.lower().startswith("json"):
                    stripped = stripped[4:]
            data = json.loads(stripped)

            return NarrativeResult(
                headline=str(data.get("headline", "")).strip() or "Performance Update",
                key_takeaways=[str(item).strip() for item in data.get("key_takeaways", [])][:5],
                risk_notes=[str(item).strip() for item in data.get("risk_notes", [])][:5],
                next_actions=[str(item).strip() for item in data.get("next_actions", [])][:5],
                tone=str(data.get("tone", "")).strip() or "neutral",
                summary=str(data.get("summary", "")).strip(),
                raw_text=content.strip(),
            )
        except Exception as exc:
            cprint(f"[analytics] Failed to parse LLM JSON summary: {exc}", "yellow")
            return None

    def _fallback_narrative(self, report_type: str, summary: Dict, raw_text: str) -> NarrativeResult:
        performance = summary["performance"]
        trading = summary["trading"]

        headline = f"{report_type.title()} performance update: return {performance['return_pct']:.2f}%"
        summary_text = (
            f"Portfolio moved from ${performance['start_value_usd']:.2f} to "
            f"${performance['end_value_usd']:.2f}, a net change of "
            f"${performance['absolute_return_usd']:.2f} ({performance['return_pct']:.2f}%). "
            f"Total trades: {trading['total_trades']} (buys {trading['buy_count']}, "
            f"sells {trading['sell_count']})."
        )

        return NarrativeResult(
            headline=headline,
            key_takeaways=[
                summary_text,
                f"Max drawdown hit {performance['max_drawdown_pct']:.2f}%.",
            ],
            risk_notes=[
                "LLM summary unavailable, using automated fallback.",
            ],
            next_actions=["Review individual trades for further insights."],
            tone="neutral",
            summary=summary_text,
            raw_text=raw_text,
        )

