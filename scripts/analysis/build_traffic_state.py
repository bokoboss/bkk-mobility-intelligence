#!/usr/bin/env python3
"""Build a provider-neutral current road traffic-state contract.

The contract is deliberately conservative: speed observations are summarized as
absolute movement bands only. It does not call a road "abnormal" until a
road/time-specific historical baseline exists.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--network",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    p.add_argument(
        "--speed",
        type=Path,
        default=Path("data/processed/current_speed/longdo_speed.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/current_speed/traffic_state.json"),
    )
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def movement_class(speed_kmh: float) -> str:
    """Classify absolute observed speed without claiming abnormality."""
    if speed_kmh <= 10:
        return "STOP_AND_GO"
    if speed_kmh <= 20:
        return "SLOW"
    if speed_kmh <= 35:
        return "MOVING"
    return "FREE_FLOW_LIKE"


def iter_response_records(value: Any) -> Iterable[dict[str, Any]]:
    """Yield response objects that look like traffic-speed observations."""
    if isinstance(value, list):
        for item in value:
            yield from iter_response_records(item)
        return
    if not isinstance(value, dict):
        return

    if "speed" in value:
        yield value
        return

    for key in ("data", "result", "results", "items"):
        if key in value:
            yield from iter_response_records(value[key])


def normalized_sample(sample: dict[str, Any]) -> list[dict[str, Any]]:
    road_id = str(sample.get("road_id") or "")
    if not road_id:
        return []

    out: list[dict[str, Any]] = []
    for record in iter_response_records(sample.get("response")):
        try:
            speed_mps = float(record["speed"])
        except (KeyError, TypeError, ValueError):
            continue
        if speed_mps < 0 or speed_mps > 80:
            continue
        speed_kmh = speed_mps * 3.6
        out.append(
            {
                "road_id": road_id,
                "sample_lon": sample.get("lon"),
                "sample_lat": sample.get("lat"),
                "district_id": sample.get("district_id"),
                "district_name_th": sample.get("district_name_th"),
                "plan_rank": sample.get("plan_rank"),
                "provider_road": record.get("road"),
                "direction": record.get("dir") or record.get("direction"),
                "speed_mps": round(speed_mps, 3),
                "speed_kmh": round(speed_kmh, 1),
                "source": record.get("source") or "unknown",
                "movement_class": movement_class(speed_kmh),
            }
        )
    return out


def road_catalog(network: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = (network.get("properties") or {}).get("road_catalog") or []
    roads: dict[str, dict[str, Any]] = {}
    for item in catalog:
        rid = str(item.get("road_id") or "")
        if not rid:
            continue
        roads[rid] = {
            "road_id": rid,
            "display_name": item.get("display_name") or rid,
            "network_tier": item.get("network_tier"),
            "priority": bool(item.get("priority")),
            "district_ids": item.get("district_ids") or [],
            "district_names": item.get("district_names") or [],
        }
    return roads


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac


def build(network: dict[str, Any], speed_doc: dict[str, Any] | None) -> dict[str, Any]:
    roads = road_catalog(network)
    raw_samples = (speed_doc or {}).get("samples") or []
    normalized: list[dict[str, Any]] = []
    for sample in raw_samples:
        if isinstance(sample, dict):
            normalized.extend(normalized_sample(sample))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in normalized:
        grouped.setdefault(row["road_id"], []).append(row)

    road_rows: dict[str, dict[str, Any]] = {}
    for rid, meta in roads.items():
        rows = grouped.get(rid, [])
        speeds = [float(row["speed_kmh"]) for row in rows]
        median_speed = statistics.median(speeds) if speeds else None
        provider_names = sorted({str(row.get("provider_road")) for row in rows if row.get("provider_road")})
        direction_counts = Counter(str(row.get("direction") or "unknown") for row in rows)
        source_counts = Counter(str(row.get("source") or "unknown") for row in rows)
        road_rows[rid] = {
            **meta,
            "status": "SAMPLED_EXPERIMENTAL" if rows else "NO_SAMPLE",
            "sample_count": len(rows),
            "median_speed_kmh": round(float(median_speed), 1) if median_speed is not None else None,
            "p10_speed_kmh": round(float(percentile(speeds, 0.10)), 1) if speeds else None,
            "p90_speed_kmh": round(float(percentile(speeds, 0.90)), 1) if speeds else None,
            "movement_class": movement_class(float(median_speed)) if median_speed is not None else "UNKNOWN",
            "provider_road_names": provider_names,
            "direction_counts": dict(sorted(direction_counts.items())),
            "source_counts": dict(sorted(source_counts.items())),
            "baseline_state": "NOT_BUILT",
            "abnormality_state": "NOT_EVALUATED",
        }

    sampled_road_count = sum(1 for row in road_rows.values() if row["sample_count"] > 0)
    road_count = len(road_rows)
    declared_status = str((speed_doc or {}).get("status") or "")
    if normalized:
        access_state = "PARTIAL_EXPERIMENTAL"
    elif declared_status == "BLOCKED_MISSING_API_KEY":
        access_state = "BLOCKED_MISSING_API_KEY"
    elif speed_doc is None:
        access_state = "BLOCKED_NO_SPEED_ARTIFACT"
    else:
        access_state = declared_status or "NO_USABLE_SAMPLES"

    return {
        "schema": "bkk-mobility-traffic-state-v0.1",
        "provider": (speed_doc or {}).get("provider") or "Longdo Map Traffic Speed adapter",
        "retrieved_at_utc": (speed_doc or {}).get("retrieved_at_utc"),
        "access_state": access_state,
        "summary": {
            "road_count": road_count,
            "sampled_road_count": sampled_road_count,
            "sampling_coverage_ratio": round(sampled_road_count / road_count, 4) if road_count else 0.0,
            "usable_observation_count": len(normalized),
            "adapter_error_count": len((speed_doc or {}).get("errors") or []),
            "interpretation": "Absolute observed speed bands only; not road-specific abnormality.",
        },
        "movement_band_definition": {
            "STOP_AND_GO": "<= 10 km/h",
            "SLOW": "> 10 to 20 km/h",
            "MOVING": "> 20 to 35 km/h",
            "FREE_FLOW_LIKE": "> 35 km/h",
            "caveat": "Bands are descriptive, not LOS and not abnormality thresholds.",
        },
        "roads": road_rows,
        "observations": normalized,
    }


def main() -> int:
    args = parse_args()
    network = load(args.network)
    speed_doc = load(args.speed) if args.speed.exists() else None
    result = build(network, speed_doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "access_state": result["access_state"],
                **result["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
