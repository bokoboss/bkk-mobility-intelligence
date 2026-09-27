#!/usr/bin/env python3
"""Optional Longdo Map traffic-speed adapter."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any

ENDPOINT = "https://api.longdo.com/RouteService/json/traffic/speed"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.3"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--network", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--key-env", default="LONGDO_MAP_API_KEY")
    p.add_argument("--max-points", type=int, default=8)
    p.add_argument("--range", dest="search_range", type=float, default=0.001)
    p.add_argument("--timeout", type=float, default=20.0)
    return p.parse_args()


def midpoint(coords: list[list[float]]) -> tuple[float, float]:
    point = coords[len(coords) // 2]
    return float(point[0]), float(point[1])


def sampling_points(network: dict[str, Any], max_points: int) -> list[dict[str, Any]]:
    by_road: dict[str, list[dict[str, Any]]] = {}
    for feature in network.get("features", []):
        rid = (feature.get("properties") or {}).get("road_id")
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if rid and len(coords) >= 2:
            lon, lat = midpoint(coords)
            by_road.setdefault(rid, []).append({"road_id": rid, "lon": lon, "lat": lat})

    out: list[dict[str, Any]] = []
    while len(out) < max_points and any(by_road.values()):
        for rid in sorted(by_road):
            if by_road[rid] and len(out) < max_points:
                out.append(by_road[rid].pop(0))
    return out


def fetch_one(
    key: str,
    point: dict[str, Any],
    search_range: float,
    timeout: float,
) -> dict[str, Any]:
    params = {
        "lon": point["lon"],
        "lat": point["lat"],
        "range": search_range,
        "locale": "th",
        "key": key,
    }
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {**point, "response": data}


def main() -> int:
    args = parse_args()
    retrieved_at = dt.datetime.now(dt.timezone.utc).isoformat()
    key = os.environ.get(args.key_env)

    if not key:
        result = {
            "schema": "bkk-mobility-longdo-speed-v0.2",
            "provider": "Longdo Map Traffic Speed",
            "endpoint": ENDPOINT,
            "retrieved_at_utc": retrieved_at,
            "status": "BLOCKED_MISSING_API_KEY",
            "access_dependency": args.key_env,
            "requested_points": 0,
            "samples": [],
            "errors": [],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": result["status"],
            "dependency": args.key_env,
            "output": str(args.output),
        }, ensure_ascii=False, indent=2))
        return 0

    network = json.loads(args.network.read_text(encoding="utf-8"))
    points = sampling_points(network, args.max_points)
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for point in points:
        try:
            rows.append(fetch_one(key, point, args.search_range, args.timeout))
        except Exception as exc:
            errors.append({**point, "error": f"{type(exc).__name__}: {exc}"})

    if rows and errors:
        status = "OK_PARTIAL"
    elif rows:
        status = "OK"
    else:
        status = "NO_USABLE_DATA"

    result = {
        "schema": "bkk-mobility-longdo-speed-v0.2",
        "provider": "Longdo Map Traffic Speed",
        "endpoint": ENDPOINT,
        "retrieved_at_utc": retrieved_at,
        "status": status,
        "access_dependency": args.key_env,
        "requested_points": len(points),
        "samples": rows,
        "errors": errors,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": status,
        "requested_points": len(points),
        "successful": len(rows),
        "errors": len(errors),
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
