"""
Batch utilities to transform recorded analytics events into digestible summaries.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests

from src import config as app_config


ISO_TS = "%Y-%m-%dT%H:%M:%S.%fZ"

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_DEFAULT_QUERY = "solana meme"
DEXSCREENER_CHAIN_ID = "solana"
DEXSCREENER_TIMEOUT = 10
DEXSCREENER_DEFAULT_MIN_LIQUIDITY = 100_000
DEXSCREENER_MAX_PAIRS = 30


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


def _resolve_data_root(analytics_dir: Path) -> Optional[Path]:
    if analytics_dir is None:
        return None
    try:
        resolved = analytics_dir.resolve()
    except FileNotFoundError:
        resolved = analytics_dir

    candidates = [resolved, resolved.parent]
    for candidate in candidates:
        try:
            if (candidate / "meme_scanner").exists() or (candidate / "paper_trading").exists():
                return candidate
        except Exception:
            continue
    return resolved.parent if resolved.parent != resolved else resolved


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _assign_age_bucket(age_hours: Optional[float]) -> str:
    if age_hours is None:
        return "unknown"
    if age_hours < 72:
        return "<72h"
    if age_hours < 96:
        return "72-96h"
    if age_hours < 168:
        return "4-7d"
    if age_hours < 336:
        return "7-14d"
    return ">14d"


def _assign_liquidity_tier(liquidity_usd: Optional[float]) -> str:
    if liquidity_usd is None:
        return "unknown"
    if liquidity_usd < 250_000:
        return "<250k"
    if liquidity_usd < 750_000:
        return "250k-750k"
    return ">750k"


def _assign_score_decile(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score < 0.5:
        return "<0.5"
    capped = min(max(score, 0.5), 1.0)
    step = 0.05
    index = int(math.floor((capped - 0.5) / step + 1e-9))
    lower = 0.5 + index * step
    upper = min(1.0, lower + step)
    return f"{lower:.2f}-{upper:.2f}"


def _assign_hold_bucket(days: Optional[float]) -> str:
    if days is None:
        return "unknown"
    if days < 2:
        return "<2d"
    if days <= 5:
        return "2-5d"
    return ">5d"


def _load_latest_scan_metadata(data_root: Optional[Path]) -> Dict[str, Dict]:
    if not data_root:
        return {}
    scanner_dir = data_root / "meme_scanner"
    if not scanner_dir.exists():
        return {}

    for file_path in sorted(scanner_dir.glob("scan_results_*.csv"), reverse=True):
        try:
            df = pd.read_csv(file_path)
        except Exception:
            continue
        if df.empty:
            continue

        metadata: Dict[str, Dict] = {}
        for _, row in df.iterrows():
            meta = {
                "token_address": row.get("token_address"),
                "token_symbol": row.get("token_symbol"),
                "age_hours": _safe_float(row.get("age_hours")),
                "liquidity_usd": _safe_float(row.get("liquidity_usd")),
                "revival_score": _safe_float(row.get("revival_score")),
            }
            meta["age_bucket"] = _assign_age_bucket(meta["age_hours"])
            meta["liquidity_tier"] = _assign_liquidity_tier(meta["liquidity_usd"])
            meta["score_decile"] = _assign_score_decile(meta["revival_score"])

            for key in filter(lambda v: isinstance(v, str) and v, {meta["token_address"], meta["token_symbol"]}):
                metadata.setdefault(key, dict(meta))

        if metadata:
            return metadata
    return {}


def _compute_velocity(current: Dict[str, float], previous: Optional[Dict[str, float]]) -> Dict[str, float]:
    previous = previous or {}
    keys = set(current) | set(previous)
    return {key: float(current.get(key, 0.0) - previous.get(key, 0.0)) for key in keys}


def _load_rollup_cache(cache_path: Path) -> Dict:
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_rollup_cache(cache_path: Path, payload: Dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
    except Exception:
        pass


def _load_trades_history(data_root: Optional[Path]) -> pd.DataFrame:
    if not data_root:
        return pd.DataFrame()
    history_path = data_root / "paper_trading" / "trades_history.csv"
    if not history_path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(history_path)
    except Exception:
        return pd.DataFrame()

    for column in ("pnl_usd", "hold_days"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    if "exit_type" in df.columns:
        df["exit_type"] = df["exit_type"].astype(str)
    return df


def _fetch_dexscreener_pairs(
    query: str = DEXSCREENER_DEFAULT_QUERY,
    *,
    chain_id: str = DEXSCREENER_CHAIN_ID,
    timeout: int = DEXSCREENER_TIMEOUT,
) -> List[Dict]:
    try:
        response = requests.get(
            DEXSCREENER_SEARCH_URL,
            params={"q": query, "chainId": chain_id},
            timeout=timeout,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        pairs = payload.get("pairs", [])
        return [pair for pair in pairs if pair.get("chainId") == chain_id][:DEXSCREENER_MAX_PAIRS]
    except Exception:
        return []


def _liquidity_weight(pair: Dict) -> float:
    return max(_safe_float(((pair or {}).get("liquidity") or {}).get("usd")) or 0.0, 0.0)


def _compute_liquidity_weighted_change(
    pairs: Iterable[Dict],
    field: str,
) -> Optional[float]:
    total_liquidity = 0.0
    weighted_sum = 0.0
    for pair in pairs:
        liquidity = _liquidity_weight(pair)
        if liquidity <= 0:
            continue
        price_change = _safe_float((pair.get("priceChange") or {}).get(field))
        if price_change is None:
            continue
        total_liquidity += liquidity
        weighted_sum += liquidity * price_change
    if total_liquidity <= 0:
        return None
    return weighted_sum / total_liquidity


def _compute_market_regime_snapshot(
    *,
    min_liquidity: float = DEXSCREENER_DEFAULT_MIN_LIQUIDITY,
) -> Dict[str, Optional[float]]:
    pairs = _fetch_dexscreener_pairs()
    filtered = [pair for pair in pairs if _liquidity_weight(pair) >= min_liquidity]

    if not filtered:
        return {
            "pair_count": 0,
            "total_liquidity_usd": 0.0,
            "weighted_return_h1_pct": None,
            "weighted_return_h6_pct": None,
            "weighted_return_h24_pct": None,
            "breadth_positive_h24": None,
            "score": None,
            "query": DEXSCREENER_DEFAULT_QUERY,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    total_liquidity = sum(_liquidity_weight(pair) for pair in filtered)
    weighted_h1 = _compute_liquidity_weighted_change(filtered, "h1")
    weighted_h6 = _compute_liquidity_weighted_change(filtered, "h6")
    weighted_h24 = _compute_liquidity_weighted_change(filtered, "h24")

    positive_h24 = 0
    for pair in filtered:
        change = _safe_float((pair.get("priceChange") or {}).get("h24"))
        if change is not None and change > 0:
            positive_h24 += 1
    breadth = positive_h24 / len(filtered) if filtered else None

    score = None
    if weighted_h6 is not None or breadth is not None:
        components = []
        if weighted_h6 is not None:
            components.append(weighted_h6 / 20.0)
        if breadth is not None:
            components.append((breadth - 0.5) * 0.8)
        if components:
            raw_score = 0.5 + sum(components)
            score = max(0.0, min(1.0, raw_score))

    return {
        "pair_count": len(filtered),
        "total_liquidity_usd": total_liquidity,
        "weighted_return_h1_pct": weighted_h1,
        "weighted_return_h6_pct": weighted_h6,
        "weighted_return_h24_pct": weighted_h24,
        "breadth_positive_h24": breadth,
        "score": score,
        "query": DEXSCREENER_DEFAULT_QUERY,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

def generate_period_summary(
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    days: Optional[int] = None,
    analytics_dir: Optional[Path] = None,
) -> Dict[str, Dict]:
    days = days or app_config.ANALYTICS_DEFAULT_ROLLUP_DAYS
    analytics_dir = Path(analytics_dir or Path(app_config.ANALYTICS_DATA_DIR))
    data_root = _resolve_data_root(analytics_dir)

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

    flow_by_token: Dict[str, float] = {}
    flow_token_metadata: Dict[str, Optional[Dict]] = {}
    flow_by_age: Dict[str, float] = defaultdict(float)
    flow_by_liquidity: Dict[str, float] = defaultdict(float)
    flow_by_score_decile: Dict[str, float] = defaultdict(float)

    if not trades_df.empty:
        grouped = trades_df.groupby("token")["usd_delta"].sum()
        flow_by_token = {token: float(value) for token, value in grouped.items()}
        trades_df = trades_df.sort_values("timestamp", ascending=False)

        token_metadata = _load_latest_scan_metadata(data_root)
        for token, amount in flow_by_token.items():
            metadata = None
            if token_metadata:
                metadata = token_metadata.get(token)
                if metadata is None and isinstance(token, str):
                    metadata = token_metadata.get(token.lower()) or token_metadata.get(token.upper())

            age_bucket = metadata.get("age_bucket") if metadata else "unmatched"
            liquidity_tier = metadata.get("liquidity_tier") if metadata else "unmatched"
            score_decile = metadata.get("score_decile") if metadata else "unmatched"

            flow_by_age[age_bucket] += amount
            flow_by_liquidity[liquidity_tier] += amount
            flow_by_score_decile[score_decile] += amount

            if metadata:
                flow_token_metadata[token] = {
                    "token_address": metadata.get("token_address"),
                    "token_symbol": metadata.get("token_symbol"),
                    "age_hours": metadata.get("age_hours"),
                    "liquidity_usd": metadata.get("liquidity_usd"),
                    "revival_score": metadata.get("revival_score"),
                    "age_bucket": age_bucket,
                    "liquidity_tier": liquidity_tier,
                    "score_decile": score_decile,
                }
            else:
                flow_token_metadata[token] = None

    flow_by_age_dict = {bucket: float(value) for bucket, value in flow_by_age.items()}
    flow_by_liquidity_dict = {bucket: float(value) for bucket, value in flow_by_liquidity.items()}
    flow_by_score_decile_dict = {bucket: float(value) for bucket, value in flow_by_score_decile.items()}

    rollup_cache_path = analytics_dir / "flow_rollups_cache.json"
    rollup_cache = _load_rollup_cache(rollup_cache_path)
    previous_snapshot = rollup_cache.get("latest")
    if previous_snapshot and previous_snapshot.get("days") != days:
        previous_snapshot = None

    flow_velocity = {
        "by_age": _compute_velocity(flow_by_age_dict, (previous_snapshot or {}).get("flow_by_age")),
        "by_liquidity": _compute_velocity(flow_by_liquidity_dict, (previous_snapshot or {}).get("flow_by_liquidity")),
        "by_score_decile": _compute_velocity(flow_by_score_decile_dict, (previous_snapshot or {}).get("flow_by_score_decile")),
    }

    rollup_cache["latest"] = {
        "days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flow_by_age": flow_by_age_dict,
        "flow_by_liquidity": flow_by_liquidity_dict,
        "flow_by_score_decile": flow_by_score_decile_dict,
    }
    _save_rollup_cache(rollup_cache_path, rollup_cache)

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

    pnl_by_exit_type: Dict[str, Dict[str, float]] = {}
    hold_time_buckets: Dict[str, Dict[str, float]] = {}
    trades_history_df = _load_trades_history(data_root)
    if not trades_history_df.empty:
        if {"exit_type", "pnl_usd"}.issubset(trades_history_df.columns):
            automated_exits = trades_history_df[
                trades_history_df["exit_type"].isin({"take_profit_1", "take_profit_2", "stop_loss", "time_based"})
            ]
            if not automated_exits.empty:
                for exit_type, group in automated_exits.groupby("exit_type"):
                    pnl_by_exit_type[exit_type] = {
                        "trade_count": int(len(group)),
                        "total_pnl_usd": float(group["pnl_usd"].sum(skipna=True)),
                    }

        if {"hold_days", "pnl_usd"}.issubset(trades_history_df.columns):
            hold_ready = trades_history_df.dropna(subset=["hold_days", "pnl_usd"]).copy()
            if not hold_ready.empty:
                hold_ready["hold_bucket"] = hold_ready["hold_days"].apply(_assign_hold_bucket)
                for bucket, group in hold_ready.groupby("hold_bucket"):
                    total = int(len(group))
                    wins = int((group["pnl_usd"] > 0).sum())
                    win_rate = wins / total if total else 0.0
                    hold_time_buckets[bucket] = {
                        "trade_count": total,
                        "win_rate": win_rate,
                        "average_pnl_usd": float(group["pnl_usd"].mean(skipna=True)),
                    }

    market_regime_snapshot = _compute_market_regime_snapshot()

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
            "flow_by_age": flow_by_age_dict,
            "flow_by_liquidity": flow_by_liquidity_dict,
            "flow_by_score_decile": flow_by_score_decile_dict,
            "flow_velocity": flow_velocity,
            "flow_token_metadata": flow_token_metadata,
            "pnl_by_exit_type": pnl_by_exit_type,
            "hold_time_buckets": hold_time_buckets,
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
        "market_regime": market_regime_snapshot,
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

