"""
Batch utilities to transform recorded analytics events into digestible summaries.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

from src import config as app_config


ISO_TS = "%Y-%m-%dT%H:%M:%S.%fZ"


def _parse_timestamp(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, ISO_TS).replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []

    rows: List[Dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _filter_events_by_period(
    events: Iterable[Dict],
    start: datetime,
    end: datetime,
) -> List[Dict]:
    filtered: List[Dict] = []
    for row in events:
        ts = row.get("timestamp")
        if not ts:
            continue
        dt = _parse_timestamp(ts)
        if start <= dt <= end:
            filtered.append({**row, "_timestamp": dt})
    return filtered


def _to_dataframe(events: Iterable[Dict]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame()
    df = pd.DataFrame(events)
    if "_timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["_timestamp"], utc=True)
        df = df.drop(columns=["_timestamp"])
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _compute_drawdown(values: pd.Series) -> float:
    if values.empty:
        return 0.0
    cumulative_max = values.cummax()
    drawdowns = (values - cumulative_max) / cumulative_max.replace(0, pd.NA)
    return float(drawdowns.min() * 100) if not drawdowns.empty else 0.0


def _default_period(days: int) -> Tuple[datetime, datetime]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return start, end


def generate_period_summary(
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    days: Optional[int] = None,
    analytics_dir: Optional[Path] = None,
) -> Dict[str, Dict]:
    days = days or app_config.ANALYTICS_DEFAULT_ROLLUP_DAYS
    analytics_dir = analytics_dir or Path(app_config.ANALYTICS_DATA_DIR)

    if start is None or end is None:
        start, end = _default_period(days)
    else:
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

    cycles = _filter_events_by_period(_read_jsonl(analytics_dir / "cycles.jsonl"), start, end)
    signals = _filter_events_by_period(_read_jsonl(analytics_dir / "signals.jsonl"), start, end)
    trades = _filter_events_by_period(_read_jsonl(analytics_dir / "trades.jsonl"), start, end)
    snapshots = _filter_events_by_period(_read_jsonl(analytics_dir / "snapshots.jsonl"), start, end)

    cycle_df = _to_dataframe(cycles)
    signal_df = _to_dataframe(signals)
    trades_df = _to_dataframe(trades)
    snapshots_df = _to_dataframe(snapshots).sort_values("timestamp")

    # Portfolio performance
    start_value = float(snapshots_df["total_value_usd"].iloc[0]) if not snapshots_df.empty else 0.0
    end_value = float(snapshots_df["total_value_usd"].iloc[-1]) if not snapshots_df.empty else start_value
    absolute_return = end_value - start_value
    return_pct = (absolute_return / start_value * 100) if start_value else 0.0
    drawdown_pct = _compute_drawdown(snapshots_df["total_value_usd"]) if not snapshots_df.empty else 0.0

    # Trading stats
    total_trades = int(len(trades_df)) if not trades_df.empty else 0
    buys = int((trades_df["direction"] == "BUY").sum()) if not trades_df.empty else 0
    sells = int((trades_df["direction"] == "SELL").sum()) if not trades_df.empty else 0
    net_capital = float(trades_df["usd_delta"].sum()) if not trades_df.empty else 0.0

    flow_by_token: Dict[str, float] = defaultdict(float)
    if not trades_df.empty:
        grouped = trades_df.groupby("token")["usd_delta"].sum()
        flow_by_token = {token: float(value) for token, value in grouped.items()}
        trades_df = trades_df.sort_values("timestamp", ascending=False)

    recent_trades: List[Dict] = []
    if not trades_df.empty:
        for _, row in trades_df.head(20).iterrows():
            recent_trades.append({
                "timestamp": row["timestamp"].isoformat() if pd.notnull(row.get("timestamp")) else None,
                "token": row.get("token"),
                "direction": row.get("direction"),
                "usd_delta": float(row.get("usd_delta", 0.0) or 0.0),
                "before_usd": float(row.get("before_usd", 0.0) or 0.0),
                "after_usd": float(row.get("after_usd", 0.0) or 0.0),
                "confidence": float(row.get("confidence")) if pd.notnull(row.get("confidence")) else None,
                "allocation_source": row.get("allocation_source"),
            })

    # Signal stats
    avg_confidence = 0.0
    if not signal_df.empty and "confidence" in signal_df.columns:
        avg_confidence = float(signal_df["confidence"].dropna().astype(float).mean())

    action_breakdown: Dict[str, int] = {}
    if not signal_df.empty:
        action_breakdown = signal_df["action"].value_counts().to_dict()
        signal_df = signal_df.sort_values("timestamp", ascending=False)

    recent_signals: List[Dict] = []
    if not signal_df.empty:
        for _, row in signal_df.head(20).iterrows():
            recent_signals.append({
                "timestamp": row["timestamp"].isoformat() if pd.notnull(row.get("timestamp")) else None,
                "token": row.get("token"),
                "action": row.get("action"),
                "confidence": float(row.get("confidence", 0.0) or 0.0),
            })

    portfolio_series: List[Dict] = []
    if not snapshots_df.empty:
        trimmed = snapshots_df[["timestamp", "total_value_usd", "cash_value_usd"]].copy()
        trimmed = trimmed.tail(200)
        for _, row in trimmed.iterrows():
            portfolio_series.append({
                "timestamp": row["timestamp"].isoformat() if pd.notnull(row["timestamp"]) else None,
                "total_value_usd": float(row.get("total_value_usd", 0.0) or 0.0),
                "cash_value_usd": float(row.get("cash_value_usd", 0.0) or 0.0),
            })

    summary = {
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": (end - start).days or days,
        },
        "performance": {
            "start_value_usd": start_value,
            "end_value_usd": end_value,
            "absolute_return_usd": absolute_return,
            "return_pct": return_pct,
            "max_drawdown_pct": drawdown_pct,
        },
        "trading": {
            "total_trades": total_trades,
            "buy_count": buys,
            "sell_count": sells,
            "net_capital_flow_usd": net_capital,
            "flow_by_token_usd": flow_by_token,
            "recent": recent_trades,
        },
        "signals": {
            "total_signals": int(len(signal_df)),
            "average_confidence": avg_confidence,
            "action_breakdown": action_breakdown,
            "recent": recent_signals,
        },
        "cycles_observed": int(len(cycle_df)),
        "portfolio": {
            "series": portfolio_series,
            "last_snapshot": portfolio_series[-1] if portfolio_series else None,
        },
    }

    return summary


def save_period_summary(summary: Dict[str, Dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate analytics summary for Moon Dev trading bot.")
    parser.add_argument("--days", type=int, default=app_config.ANALYTICS_DEFAULT_ROLLUP_DAYS, help="Number of days to include.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to save the summary JSON.")
    parser.add_argument("--start", type=str, default=None, help="Explicit period start (ISO 8601).")
    parser.add_argument("--end", type=str, default=None, help="Explicit period end (ISO 8601).")
    parser.add_argument("--analytics-dir", type=Path, default=Path(app_config.ANALYTICS_DATA_DIR), help="Directory containing analytics files.")
    return parser.parse_args()


def main() -> None:
    args = _parse_cli_args()

    start_dt = datetime.fromisoformat(args.start) if args.start else None
    end_dt = datetime.fromisoformat(args.end) if args.end else None

    summary = generate_period_summary(
        start=start_dt,
        end=end_dt,
        days=args.days,
        analytics_dir=args.analytics_dir,
    )

    print(json.dumps(summary, indent=2))

    if args.output:
        save_period_summary(summary, args.output)
    else:
        default_path = args.analytics_dir / "latest_summary.json"
        save_period_summary(summary, default_path)


if __name__ == "__main__":
    main()

