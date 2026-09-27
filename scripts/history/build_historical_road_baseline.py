#!/usr/bin/env python3
"""Combine daily probe profiles into Historical Traffic Baseline v0.3."""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
from collections import defaultdict
from pathlib import Path
import statistics
from typing import Any, Iterable

WEEKDAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--daily-dir", type=Path, default=Path("data/processed/historical_probe/daily"))
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--output", type=Path, default=Path("data/processed/history/road_time_baseline_v0_3.json"))
    p.add_argument("--reference-year", type=int, default=None)
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(x) for x in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def iter_daily_docs(daily_dir: Path, reference_year: int | None = None) -> Iterable[dict[str, Any]]:
    paths = sorted(list(daily_dir.glob("*.json")) + list(daily_dir.glob("*.json.gz")))
    for path in paths:
        opener = gzip.open if path.suffix.lower() == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            doc = json.load(f)
        date_text = str(doc.get("date") or "")
        if reference_year is not None and not date_text.startswith(f"{reference_year:04d}-"):
            continue
        yield doc


def catalog(network: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["road_id"]): row
        for row in (network.get("properties") or {}).get("road_catalog") or []
        if row.get("road_id")
    }


def readiness_class(
    day_count: int,
    total_vehicle_count: int,
    min_days: int,
    min_total_vehicles: int,
) -> str:
    if day_count >= min_days and total_vehicle_count >= min_total_vehicles:
        return "BASELINE_READY"
    if day_count >= max(3, min_days // 2):
        return "LIMITED_BASELINE"
    return "INSUFFICIENT_BASELINE"


def build_baseline(
    daily_docs: Iterable[dict[str, Any]],
    network: dict[str, Any],
    config: dict[str, Any],
    reference_year: int | None = None,
) -> dict[str, Any]:
    baseline_cfg = config.get("historical_baseline") or {}
    min_days = int(baseline_cfg.get("min_days_per_weekday_bin", 8))
    min_total_vehicles = int(baseline_cfg.get("min_total_vehicles_per_bin", 40))
    min_ready_bins_road = int(baseline_cfg.get("min_ready_bins_per_road", 24))
    time_bin_minutes = int(baseline_cfg.get("time_bin_minutes", 30))

    roads = catalog(network)
    groups: dict[tuple[str, int, int], dict[str, Any]] = defaultdict(
        lambda: {
            "daily_medians": [],
            "total_vehicle_count": 0,
            "total_probe_count": 0,
            "dates": set(),
        }
    )
    source_dates: set[str] = set()
    profile_day_count = 0
    profile_row_count = 0

    for doc in daily_docs:
        date_text = str(doc.get("date") or "")
        if not date_text:
            continue
        source_dates.add(date_text)
        profile_day_count += 1
        for row in doc.get("rows") or []:
            rid = str(row.get("road_id") or "")
            if rid not in roads:
                continue
            weekday = int(row.get("weekday", -1))
            bin_index = int(row.get("time_bin_index", -1))
            if weekday not in range(7) or bin_index < 0:
                continue
            try:
                daily_median = float(row["daily_median_speed_kmh"])
            except (KeyError, TypeError, ValueError):
                continue
            key = (rid, weekday, bin_index)
            group = groups[key]
            group["daily_medians"].append(daily_median)
            group["total_vehicle_count"] += int(row.get("vehicle_count") or 0)
            group["total_probe_count"] += int(row.get("probe_count") or 0)
            group["dates"].add(date_text)
            profile_row_count += 1

    baseline_rows = []
    road_stats: dict[str, dict[str, int]] = defaultdict(
        lambda: {"ready": 0, "limited": 0, "insufficient": 0, "any": 0}
    )
    for (rid, weekday, bin_index), group in groups.items():
        values = group["daily_medians"]
        day_count = len(group["dates"])
        quality = readiness_class(
            day_count,
            group["total_vehicle_count"],
            min_days,
            min_total_vehicles,
        )
        road_stats[rid]["any"] += 1
        if quality == "BASELINE_READY":
            road_stats[rid]["ready"] += 1
        elif quality == "LIMITED_BASELINE":
            road_stats[rid]["limited"] += 1
        else:
            road_stats[rid]["insufficient"] += 1

        start_minute = bin_index * time_bin_minutes
        hh, mm = divmod(start_minute, 60)
        baseline_rows.append({
            "road_id": rid,
            "road_name": roads[rid].get("display_name") or rid,
            "network_tier": roads[rid].get("network_tier") or "URBAN",
            "weekday": weekday,
            "weekday_name": WEEKDAY_NAMES[weekday],
            "time_bin_index": bin_index,
            "time_bin_start": f"{hh:02d}:{mm:02d}",
            "day_count": day_count,
            "total_vehicle_count": group["total_vehicle_count"],
            "total_probe_count": group["total_probe_count"],
            "median_speed_kmh": round(float(statistics.median(values)), 1),
            "p10_speed_kmh": round(float(percentile(values, 0.10)), 1),
            "p25_speed_kmh": round(float(percentile(values, 0.25)), 1),
            "p75_speed_kmh": round(float(percentile(values, 0.75)), 1),
            "p90_speed_kmh": round(float(percentile(values, 0.90)), 1),
            "quality": quality,
        })

    baseline_rows.sort(key=lambda x: (x["road_id"], x["weekday"], x["time_bin_index"]))

    road_rows = []
    ready_road_ids: set[str] = set()
    for rid, meta in roads.items():
        stats = road_stats.get(rid) or {"ready": 0, "limited": 0, "insufficient": 0, "any": 0}
        if stats["ready"] >= min_ready_bins_road:
            road_state = "ROAD_BASELINE_READY"
            ready_road_ids.add(rid)
        elif stats["ready"] > 0 or stats["limited"] > 0:
            road_state = "ROAD_BASELINE_PARTIAL"
        else:
            road_state = "ROAD_BASELINE_INSUFFICIENT"
        road_rows.append({
            "road_id": rid,
            "road_name": meta.get("display_name") or rid,
            "network_tier": meta.get("network_tier") or "URBAN",
            "district_ids": meta.get("district_ids") or [],
            "district_names": meta.get("district_names") or [],
            "ready_bin_count": stats["ready"],
            "limited_bin_count": stats["limited"],
            "insufficient_bin_count": stats["insufficient"],
            "observed_bin_count": stats["any"],
            "road_baseline_state": road_state,
        })

    def coverage_rows(key_name: str, keys: list[str]) -> list[dict[str, Any]]:
        rows = []
        for key in keys:
            if key_name == "network_tier":
                eligible = {rid for rid, meta in roads.items() if str(meta.get("network_tier") or "URBAN") == key}
            else:
                eligible = {rid for rid, meta in roads.items() if key in {str(x) for x in meta.get("district_ids") or []}}
            ready = eligible & ready_road_ids
            rows.append({
                key_name: key,
                "eligible_road_count": len(eligible),
                "ready_road_count": len(ready),
                "ready_road_coverage_ratio": round(len(ready) / len(eligible), 4) if eligible else 0.0,
            })
        return rows

    district_ids = sorted({
        str(did)
        for meta in roads.values()
        for did in (meta.get("district_ids") or [])
        if str(did)
    })
    district_names = {}
    for meta in roads.values():
        for did, name in zip(meta.get("district_ids") or [], meta.get("district_names") or []):
            district_names[str(did)] = str(name)

    district_cov = coverage_rows("district_id", district_ids)
    for row in district_cov:
        row["district_name_th"] = district_names.get(row["district_id"], row["district_id"])

    ready_bin_count = sum(1 for row in baseline_rows if row["quality"] == "BASELINE_READY")
    all_bin_count = len(baseline_rows)
    eligible_road_count = len(roads)
    ready_road_count = len(ready_road_ids)

    return {
        "schema": "bkk-mobility-road-time-baseline-v0.3",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reference_year": reference_year,
        "timezone": "Asia/Bangkok",
        "direction_state": "NOT_AVAILABLE_IN_PUBLISHED_RAW_FORMAT",
        "time_bin_minutes": time_bin_minutes,
        "methodology": {
            "daily_profile": "per-vehicle median speed -> daily road/time-bin distribution",
            "baseline_profile": "distribution of daily medians, equal day weighting",
            "map_matching": "nearest OSM road segment with distance and ambiguity rejection",
            "quality_thresholds": {
                "min_days_per_weekday_bin": min_days,
                "min_total_vehicles_per_bin": min_total_vehicles,
                "min_ready_bins_per_road": min_ready_bins_road,
            },
        },
        "summary": {
            "profile_day_count": profile_day_count,
            "profile_row_count": profile_row_count,
            "source_date_min": min(source_dates) if source_dates else None,
            "source_date_max": max(source_dates) if source_dates else None,
            "eligible_road_count": eligible_road_count,
            "roads_with_any_baseline_bin": sum(1 for row in road_rows if row["observed_bin_count"] > 0),
            "ready_road_count": ready_road_count,
            "ready_road_coverage_ratio": round(ready_road_count / eligible_road_count, 4) if eligible_road_count else 0.0,
            "baseline_bin_count": all_bin_count,
            "ready_bin_count": ready_bin_count,
            "ready_bin_ratio": round(ready_bin_count / all_bin_count, 4) if all_bin_count else 0.0,
        },
        "tier_coverage": coverage_rows("network_tier", ["STRATEGIC", "URBAN"]),
        "district_coverage": district_cov,
        "roads": road_rows,
        "baseline_bins": baseline_rows,
    }


def main() -> int:
    args = parse_args()
    network = load(args.network)
    config = load(args.config)
    baseline_cfg = config.get("historical_baseline") or {}
    reference_year = (
        args.reference_year
        if args.reference_year is not None
        else int(baseline_cfg.get("reference_year", 2025))
    )
    docs = list(iter_daily_docs(args.daily_dir, reference_year=reference_year))
    result = build_baseline(docs, network, config, reference_year=reference_year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "reference_year": reference_year,
        **result["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
