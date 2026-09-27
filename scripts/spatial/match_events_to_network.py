#!/usr/bin/env python3
"""Match iTIC events to the expanded OSM road catalog.

Confirmation requires spatial proximity plus road identity evidence from either
an OSM/config road name appearing in the event title or a route reference.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

EARTH_M = 6371008.8
TH_ROUTE_RE = re.compile(
    r"ทางหลวง(?:แผ่นดิน)?(?:หมายเลข)?\s*(\d{1,4})",
    re.IGNORECASE,
)
EN_ROUTE_RE = re.compile(
    r"\b(?:highway|route)\s*(?:no\.?\s*)?(\d{1,4})\b",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=Path, required=True)
    p.add_argument("--network", type=Path, required=True)
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--strong-distance-m", type=float, default=80.0)
    p.add_argument("--candidate-distance-m", type=float, default=150.0)
    return p.parse_args()


def xy_m(
    lon: float, lat: float, lon0: float, lat0: float
) -> tuple[float, float]:
    lat0r = math.radians(lat0)
    return (
        math.radians(lon - lon0) * EARTH_M * math.cos(lat0r),
        math.radians(lat - lat0) * EARTH_M,
    )


def point_segment_distance_m(
    lon: float, lat: float, a: list[float], b: list[float]
) -> float:
    ax, ay = xy_m(float(a[0]), float(a[1]), lon, lat)
    bx, by = xy_m(float(b[0]), float(b[1]), lon, lat)
    vx, vy = bx - ax, by - ay
    if vx == 0 and vy == 0:
        return math.hypot(ax, ay)
    t = max(
        0.0,
        min(1.0, -(ax * vx + ay * vy) / (vx * vx + vy * vy)),
    )
    px, py = ax + t * vx, ay + t * vy
    return math.hypot(px, py)


def point_line_distance_m(
    lon: float, lat: float, coords: list[list[float]]
) -> float:
    return min(
        point_segment_distance_m(lon, lat, a, b)
        for a, b in zip(coords, coords[1:])
    )


def clean_alias(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip().casefold())
    for prefix in ("ถนน", "road "):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text


def event_title(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(k) or "")
        for k in ("title", "title_en")
    ).casefold()


def event_text(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(k) or "")
        for k in ("title", "title_en", "description", "description_en")
    )


def event_route_refs(event: dict[str, Any]) -> set[str]:
    text = event_text(event)
    refs = set(TH_ROUTE_RE.findall(text))
    refs.update(EN_ROUTE_RE.findall(text))
    return refs


def candidate_title_support(
    event: dict[str, Any], candidate: dict[str, Any]
) -> bool:
    title = event_title(event)
    configured = set(event.get("road_title_matches") or [])
    if candidate["road_id"] in configured:
        return True

    aliases = candidate.get("aliases") or []
    for alias in aliases:
        cleaned = clean_alias(str(alias))
        if len(cleaned) >= 4 and cleaned in title:
            return True
    return False


def nearest_by_road(
    event: dict[str, Any], network: dict[str, Any]
) -> list[dict[str, Any]]:
    lat = float(event["latitude"])
    lon = float(event["longitude"])
    best: dict[str, dict[str, Any]] = {}

    for feature in network.get("features", []):
        props = feature.get("properties") or {}
        rid = props.get("road_id")
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if not rid or len(coords) < 2:
            continue
        distance = point_line_distance_m(lon, lat, coords)
        current = best.get(rid)
        aliases = list(props.get("aliases") or [])
        route_refs = list(props.get("route_refs") or [])
        if current is None or distance < current["distance_m"]:
            best[rid] = {
                "road_id": rid,
                "display_name": props.get("display_name") or rid,
                "priority": bool(props.get("priority")),
                "distance_m": round(distance, 1),
                "osm_way_id": props.get("osm_way_id"),
                "aliases": aliases,
                "route_refs": route_refs,
                "highway": props.get("highway"),
            }
        else:
            current["aliases"] = sorted(
                set(current.get("aliases") or []) | set(aliases)
            )
            current["route_refs"] = sorted(
                set(current.get("route_refs") or []) | set(route_refs)
            )

    return sorted(best.values(), key=lambda x: x["distance_m"])


def classify(
    event: dict[str, Any],
    candidates: list[dict[str, Any]],
    strong_m: float,
    candidate_m: float,
) -> dict[str, Any]:
    nearest = candidates[0] if candidates else None
    observed_refs = event_route_refs(event)

    if not nearest:
        return {
            "network_match_class": "NO_GEOMETRY",
            "network_road_id": None,
            "confirmed_road_id": None,
            "network_confirmed": False,
            "network_distance_m": None,
            "event_route_refs": sorted(observed_refs),
        }

    rid = nearest["road_id"]
    distance = float(nearest["distance_m"])
    title_support = candidate_title_support(event, nearest)
    candidate_refs = {str(x) for x in nearest.get("route_refs") or []}
    ref_support = bool(observed_refs & candidate_refs)

    if distance <= strong_m and title_support:
        match_class = "GEOMETRY+TITLE_CONFIRMED"
        confirmed = True
    elif distance <= strong_m and ref_support:
        match_class = "GEOMETRY+ROUTE_CONFIRMED"
        confirmed = True
    elif distance <= strong_m:
        match_class = "GEOMETRY_ONLY_CANDIDATE"
        confirmed = False
    elif distance <= candidate_m and (title_support or ref_support):
        match_class = "GEOMETRY+EVIDENCE_CANDIDATE"
        confirmed = False
    elif distance <= candidate_m:
        match_class = "GEOMETRY_CANDIDATE"
        confirmed = False
    else:
        match_class = "NETWORK_CONTEXT_ONLY"
        confirmed = False

    return {
        "network_match_class": match_class,
        "network_road_id": rid if distance <= candidate_m else None,
        "confirmed_road_id": rid if confirmed else None,
        "confirmed_road_name": (
            nearest.get("display_name") if confirmed else None
        ),
        "network_confirmed": confirmed,
        "network_distance_m": round(distance, 1),
        "event_route_refs": sorted(observed_refs),
        "route_ref_support": ref_support,
        "title_support": title_support,
        "nearest_core_road": nearest,
        "road_distance_candidates": candidates[:8],
    }


def main() -> int:
    args = parse_args()
    events = json.loads(args.events.read_text(encoding="utf-8"))
    network = json.loads(args.network.read_text(encoding="utf-8"))

    out: list[dict[str, Any]] = []
    classes: dict[str, int] = {}
    candidate_counts: dict[str, int] = {}
    confirmed_counts: dict[str, int] = {}

    for event in events:
        match = classify(
            event,
            nearest_by_road(event, network),
            args.strong_distance_m,
            args.candidate_distance_m,
        )
        row = dict(event)
        row.update(match)
        out.append(row)

        cls = match["network_match_class"]
        classes[cls] = classes.get(cls, 0) + 1
        rid = match.get("network_road_id")
        if rid:
            candidate_counts[rid] = candidate_counts.get(rid, 0) + 1
        rid = match.get("confirmed_road_id")
        if rid:
            confirmed_counts[rid] = confirmed_counts.get(rid, 0) + 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "events": len(out),
                "match_classes": classes,
                "candidate_road_records": candidate_counts,
                "confirmed_road_records": confirmed_counts,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
