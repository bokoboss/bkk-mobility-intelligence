#!/usr/bin/env python3
"""Build descriptive flood/rain intelligence from confirmed recent event episodes."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

FLOOD_TYPE = "6"
RAIN_TYPE = "5"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--history",
        type=Path,
        default=Path("data/processed/history/recent_incident_intelligence.json"),
    )
    p.add_argument(
        "--tmd-context",
        type=Path,
        default=Path("data/raw/current_context/tmd_precip_context.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/flood/flood_intelligence.json"),
    )
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_time(value: Any) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value))
    except ValueError:
        return None


def haversine_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    radius = 6371.0088
    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [
            float(a["latitude"]),
            float(a["longitude"]),
            float(b["latitude"]),
            float(b["longitude"]),
        ],
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * p
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def window(history: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return history["windows"][key]["clusters"]


def typed(items: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [x for x in items if str(x.get("event_type") or "") == event_type]


def ranked_flood_roads(history: dict[str, Any]) -> list[dict[str, Any]]:
    flood30 = typed(window(history, "30d"), FLOOD_TYPE)
    flood7 = typed(window(history, "7d"), FLOOD_TYPE)
    by_road: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "flood_30d": 0,
            "flood_7d": 0,
            "days": set(),
            "latest": None,
            "road_name": None,
        }
    )

    for item in flood30:
        road_id = item["road_id"]
        row = by_road[road_id]
        row["road_name"] = item.get("road_name") or road_id
        row["flood_30d"] += 1
        started = parse_time(item.get("first_start"))
        if started:
            row["days"].add(started.date().isoformat())
            current = row["latest"]
            row["latest"] = max(current, started.isoformat()) if current else started.isoformat()

    for item in flood7:
        by_road[item["road_id"]]["flood_7d"] += 1

    result = []
    for road_id, row in by_road.items():
        result.append(
            {
                "road_id": road_id,
                "road_name": row["road_name"] or road_id,
                "flood_30d": row["flood_30d"],
                "flood_7d": row["flood_7d"],
                "distinct_flood_days_30d": len(row["days"]),
                "latest_flood": row["latest"],
            }
        )
    result.sort(
        key=lambda x: (
            -x["flood_30d"],
            -x["distinct_flood_days_30d"],
            x["road_name"],
        )
    )
    return result


def build_hotspots(
    history: dict[str, Any],
    radius_km: float = 0.30,
) -> list[dict[str, Any]]:
    flood30 = typed(window(history, "30d"), FLOOD_TYPE)
    flood7_ids = {x["cluster_id"] for x in typed(window(history, "7d"), FLOOD_TYPE)}
    groups: list[dict[str, Any]] = []

    for road_id in sorted({x["road_id"] for x in flood30}):
        events = sorted(
            [x for x in flood30 if x["road_id"] == road_id],
            key=lambda x: str(x.get("first_start") or ""),
        )
        local: list[dict[str, Any]] = []
        for event in events:
            best = None
            best_distance = float("inf")
            for group in local:
                distance = haversine_km(group["anchor"], event)
                if distance <= radius_km and distance < best_distance:
                    best = group
                    best_distance = distance
            if best is None:
                local.append({"anchor": event, "items": [event]})
            else:
                best["items"].append(event)
        groups.extend(local)

    hotspots = []
    for group in groups:
        items = group["items"]
        if len(items) < 2:
            continue
        times = [parse_time(x.get("first_start")) for x in items]
        times = [x for x in times if x]
        days = sorted({x.date().isoformat() for x in times})
        lat = sum(float(x["latitude"]) for x in items) / len(items)
        lon = sum(float(x["longitude"]) for x in items) / len(items)
        seed = f"{items[0]['road_id']}|{round(lat, 4)}|{round(lon, 4)}"
        hotspots.append(
            {
                "hotspot_id": hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12],
                "road_id": items[0]["road_id"],
                "road_name": items[0].get("road_name"),
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "episode_count_30d": len(items),
                "episode_count_7d": sum(
                    1 for x in items if x.get("cluster_id") in flood7_ids
                ),
                "distinct_flood_days_30d": len(days),
                "flood_days": days,
                "latest_flood": max(times).isoformat() if times else None,
                "sample_title": items[-1].get("title"),
                "radius_rule_m": round(radius_km * 1000),
            }
        )

    hotspots.sort(
        key=lambda x: (
            -x["distinct_flood_days_30d"],
            -x["episode_count_30d"],
            x.get("road_name") or "",
        )
    )
    return hotspots


def build_associations(
    history: dict[str, Any],
    max_lag_minutes: float = 360.0,
    max_distance_km: float = 5.0,
) -> list[dict[str, Any]]:
    items = window(history, "30d")
    floods = typed(items, FLOOD_TYPE)
    rains = typed(items, RAIN_TYPE)
    pairs = []

    for flood in floods:
        flood_time = parse_time(flood.get("first_start"))
        if not flood_time:
            continue
        candidates = []
        for rain in rains:
            rain_time = parse_time(rain.get("first_start"))
            if not rain_time:
                continue
            lag = (flood_time - rain_time).total_seconds() / 60
            if not 0 <= lag <= max_lag_minutes:
                continue
            distance = haversine_km(rain, flood)
            if distance > max_distance_km:
                continue
            same_road = rain.get("road_id") == flood.get("road_id")
            score = (0 if same_road else 1, distance, lag)
            candidates.append((score, rain, lag, distance, same_road))

        if not candidates:
            continue
        candidates.sort(key=lambda x: x[0])
        _, rain, lag, distance, same_road = candidates[0]
        pairs.append(
            {
                "flood_cluster_id": flood["cluster_id"],
                "rain_cluster_id": rain["cluster_id"],
                "road_id": flood["road_id"],
                "road_name": flood.get("road_name"),
                "flood_title": flood.get("title"),
                "rain_title": rain.get("title"),
                "flood_start": flood.get("first_start"),
                "rain_start": rain.get("first_start"),
                "lag_minutes": round(lag, 1),
                "distance_km": round(distance, 2),
                "same_road": same_road,
                "flood_latitude": flood["latitude"],
                "flood_longitude": flood["longitude"],
                "rain_latitude": rain["latitude"],
                "rain_longitude": rain["longitude"],
            }
        )
    pairs.sort(key=lambda x: str(x.get("flood_start") or ""), reverse=True)
    return pairs


def association_summary(
    history: dict[str, Any],
    pairs: list[dict[str, Any]],
    window_key: str,
) -> dict[str, Any]:
    floods = typed(window(history, window_key), FLOOD_TYPE)
    ids = {x["cluster_id"] for x in floods}
    selected = [x for x in pairs if x["flood_cluster_id"] in ids]
    lags = [float(x["lag_minutes"]) for x in selected]
    return {
        "flood_count": len(floods),
        "associated_flood_count": len(selected),
        "association_coverage_pct": (
            round(len(selected) * 100 / len(floods), 1) if floods else 0.0
        ),
        "same_road_associations": sum(1 for x in selected if x["same_road"]),
        "median_lag_minutes": (
            round(statistics.median(lags), 1) if lags else None
        ),
        "p25_lag_minutes": (
            round(percentile(lags, 0.25), 1) if lags else None
        ),
        "p75_lag_minutes": (
            round(percentile(lags, 0.75), 1) if lags else None
        ),
    }


def main() -> int:
    args = parse_args()
    history = load(args.history)

    flood7 = typed(window(history, "7d"), FLOOD_TYPE)
    prior_flood7 = typed(window(history, "prior_7d"), FLOOD_TYPE)
    flood30 = typed(window(history, "30d"), FLOOD_TYPE)
    rain7 = typed(window(history, "7d"), RAIN_TYPE)
    rain30 = typed(window(history, "30d"), RAIN_TYPE)

    pairs = build_associations(history)
    hotspots = build_hotspots(history)
    roads = ranked_flood_roads(history)

    daily: dict[str, int] = defaultdict(int)
    for item in flood7:
        started = parse_time(item.get("first_start"))
        if started:
            daily[started.date().isoformat()] += 1
    peak_day = max(daily.items(), key=lambda x: x[1]) if daily else (None, 0)

    tmd_context = (
        load(args.tmd_context)
        if args.tmd_context.exists()
        else {"status": "NOT_FETCHED"}
    )

    result = {
        "schema": "bkk-mobility-flood-v0.1",
        "anchor_time_ict": history["anchor_time_ict"],
        "scope": "confirmed-road reported flood/rain episodes in Expanded V1",
        "metrics": {
            "flood_7d": len(flood7),
            "flood_prior_7d": len(prior_flood7),
            "flood_30d": len(flood30),
            "rain_7d": len(rain7),
            "rain_30d": len(rain30),
            "flood_7d_change": len(flood7) - len(prior_flood7),
            "flood_7d_change_pct": (
                round(
                    (len(flood7) - len(prior_flood7))
                    * 100
                    / len(prior_flood7),
                    1,
                )
                if prior_flood7
                else None
            ),
            "roads_with_flood_30d": len({x["road_id"] for x in flood30}),
            "recurring_hotspots_30d": len(hotspots),
            "peak_flood_day_7d": peak_day[0],
            "peak_flood_day_count": peak_day[1],
        },
        "rain_flood_association": {
            "rule": {
                "lookback_hours": 6,
                "max_distance_km": 5,
                "preference": "same road, then nearest spatial match, then shorter lag",
            },
            "interpretation": (
                "descriptive temporal-spatial association only; "
                "not causal attribution"
            ),
            "7d": association_summary(history, pairs, "7d"),
            "30d": association_summary(history, pairs, "30d"),
            "pairs_30d": pairs,
        },
        "top_flood_roads_30d": roads[:20],
        "hotspots_30d": hotspots[:100],
        "sources": {
            "longdo_events": {
                "status": "READY",
                "use": "reported rain/flood episodes + confirmed road matching",
            },
            "tmd_nwp": tmd_context,
            "bma_street_flood": {
                "status": "OFFICIAL_SOURCE_DISCOVERED_NOT_MACHINE_INGESTED",
                "url": "https://weather.bangkok.go.th/flood/",
                "reason": (
                    "automated runner connection reset; "
                    "no stable machine contract validated yet"
                ),
            },
            "bma_rain": {
                "status": "OFFICIAL_SOURCE_DISCOVERED_NOT_MACHINE_INGESTED",
                "url": "https://weather.bangkok.go.th/rain",
                "reason": (
                    "automated runner connection reset; "
                    "no stable machine contract validated yet"
                ),
            },
        },
        "limitations": [
            "Longdo rain/flood events are reported observations, not complete sensor coverage.",
            "Rain-to-flood association is not a causal estimate.",
            "Flood event stop times may be administrative/reporting times and are not treated as physical drainage recovery.",
            "BMA measured street-water and rain-gauge feeds are not yet ingested automatically.",
            "TMD NWP metadata is context only until precipitation grid values are spatially sampled.",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "flood_7d": len(flood7),
                "flood_prior_7d": len(prior_flood7),
                "flood_30d": len(flood30),
                "rain_7d": len(rain7),
                "hotspots_30d": len(hotspots),
                "rain_flood_7d": result["rain_flood_association"]["7d"],
                "top_flood_roads": roads[:5],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
