#!/usr/bin/env python3
"""Compare the live Longdo Traffic Index with a same-weekday/time 2026 baseline."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import math
from pathlib import Path
import statistics
import urllib.request

HISTORY_URL = "https://traffic.longdo.com/api/raw/trafficindex/2026"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.6"
ICT = dt.timezone(dt.timedelta(hours=7))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--current",
        type=Path,
        default=Path("data/raw/current_context/traffic_index.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/current_context/traffic_index_baseline.json"),
    )
    p.add_argument("--history-url", default=HISTORY_URL)
    p.add_argument("--timeout", type=float, default=30.0)
    return p.parse_args()


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def fetch_csv(url: str, timeout: float) -> list[dict[str, str]]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def parse_local(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value).replace(tzinfo=ICT)


def classify_percentile(pct: float | None) -> str:
    if pct is None:
        return "UNKNOWN"
    if pct >= 95:
        return "VERY_HIGH_FOR_TIME"
    if pct >= 80:
        return "HIGH_FOR_TIME"
    if pct <= 5:
        return "VERY_LOW_FOR_TIME"
    if pct <= 20:
        return "LOW_FOR_TIME"
    return "TYPICAL_FOR_TIME"


def main() -> int:
    args = parse_args()
    current_doc = json.loads(args.current.read_text(encoding="utf-8"))
    current = current_doc["data"]
    current_index = float(current["index"])
    source_utc = dt.datetime.fromisoformat(current["source_time_utc"])
    source_local = source_utc.astimezone(ICT)

    rows = fetch_csv(args.history_url, args.timeout)
    observations: list[tuple[dt.datetime, float]] = []
    for row in rows:
        try:
            local = parse_local(row["datetime"])
            value = float(row["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if local <= source_local:
            observations.append((local, value))

    same_slot = [
        value
        for local, value in observations
        if local.weekday() == source_local.weekday()
        and local.hour == source_local.hour
        and local.minute == source_local.minute
        and local.date() < source_local.date()
    ]

    current_day_rows = [
        (local, value)
        for local, value in observations
        if local.date() == source_local.date() and local <= source_local
    ]
    current_day_rows.sort()
    one_hour_target = source_local - dt.timedelta(hours=1)
    one_hour_prior = None
    if current_day_rows:
        nearest = min(
            current_day_rows,
            key=lambda x: abs((x[0] - one_hour_target).total_seconds()),
        )
        if abs((nearest[0] - one_hour_target).total_seconds()) <= 10 * 60:
            one_hour_prior = nearest

    rank = None
    if same_slot:
        less_or_equal = sum(v <= current_index for v in same_slot)
        rank = round(100 * less_or_equal / len(same_slot), 1)

    result = {
        "metric": "Longdo Traffic Index",
        "scope": "Bangkok and vicinity aggregate context",
        "current": {
            "index": current_index,
            "source_time_ict": source_local.isoformat(),
        },
        "baseline": {
            "rule": "same weekday and exact 5-minute local-time slot, prior dates in 2026",
            "sample_count": len(same_slot),
            "median": round(statistics.median(same_slot), 2) if same_slot else None,
            "mean": round(statistics.mean(same_slot), 2) if same_slot else None,
            "p10": round(percentile(same_slot, 0.10), 2) if same_slot else None,
            "p90": round(percentile(same_slot, 0.90), 2) if same_slot else None,
            "current_percentile_rank": rank,
            "classification": classify_percentile(rank),
        },
        "recent": {
            "one_hour_prior_time_ict": one_hour_prior[0].isoformat() if one_hour_prior else None,
            "one_hour_prior_index": one_hour_prior[1] if one_hour_prior else None,
            "change_last_hour": (
                round(current_index - one_hour_prior[1], 2)
                if one_hour_prior
                else None
            ),
        },
        "caveat": (
            "This is city/metropolitan context only and must not be interpreted "
            "as speed or congestion on any specific pilot road."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
