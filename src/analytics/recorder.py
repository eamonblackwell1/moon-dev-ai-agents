"""
Utilities for capturing structured analytics events from the live trading loop.

All writes are gated behind `config.ANALYTICS_ENABLED` and persist to JSONL files
so we can build metrics and reports without touching production trading logic.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, Optional

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency
    np = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover - optional dependency
    pd = None  # type: ignore

from src import config as app_config

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat_utc(dt: Optional[datetime] = None) -> str:
    dt = dt or _utc_now()
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


def _sanitize_value(value: Any) -> Any:
    """Convert pandas/numpy/native objects into JSON-serialisable structures."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return _isoformat_utc(value)
    if isinstance(value, dict):
        return {str(k): _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(v) for v in value]

    if np is not None and isinstance(value, np.generic):
        return value.item()

    if pd is not None:
        if isinstance(value, pd.Timestamp):
            return _isoformat_utc(value.to_pydatetime())
        if isinstance(value, pd.Series):
            return _sanitize_value(value.to_dict())
        if isinstance(value, pd.DataFrame):
            return _sanitize_value(value.to_dict(orient="records"))

    # Fallback to string representation
    return str(value)


class NullAnalyticsRecorder:
    """No-op recorder used when analytics are disabled."""

    enabled = False

    def start_cycle(self, *_: Any, **__: Any) -> str:
        return ""

    def end_cycle(self, *_: Any, **__: Any) -> None:
        return None

    def record_signal_evaluation(self, *_: Any, **__: Any) -> None:
        return None

    def record_trade_execution(self, *_: Any, **__: Any) -> None:
        return None

    def record_portfolio_snapshot(self, *_: Any, **__: Any) -> None:
        return None

    def record_note(self, *_: Any, **__: Any) -> None:
        return None


class AnalyticsRecorder:
    """Shared analytics recorder instance."""

    _instance: Optional["AnalyticsRecorder"] = None
    _instance_lock: Lock = Lock()

    def __init__(
        self,
        enabled: bool,
        analytics_dir: str,
        max_file_size_bytes: int,
        snapshot_token_limit: int,
    ) -> None:
        self.enabled = enabled
        self.analytics_dir = Path(analytics_dir)
        self.max_file_size_bytes = max(max_file_size_bytes, 1024 * 128)  # minimum 128 KB
        self.snapshot_token_limit = max(snapshot_token_limit, 1)
        self.session_id = os.getenv("ANALYTICS_SESSION_ID", str(uuid.uuid4()))
        self._write_lock = Lock()

        self._event_files = {
            "cycles": self.analytics_dir / "cycles.jsonl",
            "signals": self.analytics_dir / "signals.jsonl",
            "trades": self.analytics_dir / "trades.jsonl",
            "snapshots": self.analytics_dir / "snapshots.jsonl",
            "notes": self.analytics_dir / "notes.jsonl",
        }

        if self.enabled:
            self.analytics_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------- #
    # Singleton factory
    # --------------------------------------------------------------------- #
    @classmethod
    def get_instance(cls) -> "AnalyticsRecorder":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(
                    enabled=bool(app_config.ANALYTICS_ENABLED),
                    analytics_dir=app_config.ANALYTICS_DATA_DIR,
                    max_file_size_bytes=app_config.ANALYTICS_MAX_FILE_SIZE_BYTES,
                    snapshot_token_limit=app_config.ANALYTICS_SNAPSHOT_TOKEN_LIMIT,
                )
            return cls._instance

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def start_cycle(
        self,
        label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        cycle_id = str(uuid.uuid4())
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "label": label,
            "metadata": metadata or {},
        }
        self._append_event("cycles", {**payload, "event": "cycle_start"})
        return cycle_id

    def end_cycle(
        self,
        cycle_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "metadata": metadata or {},
        }
        self._append_event("cycles", {**payload, "event": "cycle_end"})

    def record_signal_evaluation(
        self,
        *,
        cycle_id: str,
        token: str,
        action: str,
        confidence: Optional[float],
        reasoning: str,
        market_snapshot: Optional[Dict[str, Any]] = None,
        strategy_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "token": token,
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "market_snapshot": market_snapshot or {},
            "strategy_context": strategy_context or {},
        }
        self._append_event("signals", payload)

    def record_trade_execution(
        self,
        *,
        cycle_id: str,
        token: str,
        direction: str,
        usd_delta: float,
        before_usd: float,
        after_usd: float,
        target_usd: Optional[float] = None,
        confidence: Optional[float] = None,
        allocation_source: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "token": token,
            "direction": direction,
            "usd_delta": usd_delta,
            "before_usd": before_usd,
            "after_usd": after_usd,
            "target_usd": target_usd,
            "confidence": confidence,
            "allocation_source": allocation_source,
            "extra": extra or {},
        }
        self._append_event("trades", payload)

    def record_portfolio_snapshot(
        self,
        *,
        cycle_id: str,
        stage: str,
        total_value_usd: float,
        cash_value_usd: Optional[float] = None,
        positions: Optional[Iterable[Dict[str, Any]]] = None,
        risk_notes: Optional[str] = None,
    ) -> None:
        limited_positions = self._limit_positions(positions or [])
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "stage": stage,
            "total_value_usd": total_value_usd,
            "cash_value_usd": cash_value_usd,
            "positions": limited_positions,
            "risk_notes": risk_notes or "",
        }
        self._append_event("snapshots", payload)

    def record_note(
        self,
        *,
        cycle_id: Optional[str],
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "cycle_id": cycle_id,
            "session_id": self.session_id,
            "level": level,
            "message": message,
            "context": context or {},
        }
        self._append_event("notes", payload)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _append_event(self, file_key: str, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        file_path = self._event_files[file_key]
        event = {"timestamp": _isoformat_utc(), **self._sanitize_payload(payload)}

        try:
            with self._write_lock:
                if file_path.exists() and file_path.stat().st_size >= self.max_file_size_bytes:
                    self._rotate_file(file_path)

                with file_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as exc:  # pragma: no cover - logging fallback
            print(f"[analytics] Failed to append {file_key} event: {exc}")

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {key: _sanitize_value(value) for key, value in payload.items()}

    def _rotate_file(self, file_path: Path) -> None:
        rotated_name = file_path.with_name(
            f"{file_path.stem}_{_isoformat_utc().replace(':', '-')}{file_path.suffix}"
        )
        file_path.rename(rotated_name)

    def _limit_positions(self, positions: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        positions_list = list(positions)
        if not positions_list:
            return []
        sorted_positions = sorted(
            positions_list,
            key=lambda item: float(item.get("usd_value", 0.0) or 0.0),
            reverse=True,
        )
        trimmed = sorted_positions[: self.snapshot_token_limit]
        return [self._sanitize_payload(pos) for pos in trimmed]


def get_analytics_recorder() -> AnalyticsRecorder | NullAnalyticsRecorder:
    if not getattr(app_config, "ANALYTICS_ENABLED", False):
        return NullAnalyticsRecorder()
    return AnalyticsRecorder.get_instance()

