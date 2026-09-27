#!/usr/bin/env python3
"""Fetch exact core-road geometry from OpenStreetMap/Overpass.

Core geometry changes slowly relative to live traffic data. The script therefore
accepts a validated existing/cached GeoJSON and otherwise tries multiple public
Overpass endpoints. This prevents a transient Overpass outage from taking down
the latest-data pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "bkk-mobility-intelligence-phase0/0.7"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    p.add_argument(
        "--endpoint",
        action="append",
        default=[],
        help="Overpass interpreter endpoint; repeat to define fallback order.",
    )
    p.add_argument("--timeout", type=float, default=45.0)
    p.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore an existing valid geometry file and query Overpass again.",
    )
    return p.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def regex_escape(text: str) -> str:
    chars = r"\\.^$|?*+()[]{}"
    out = ""
    for ch in text:
        out += "\\" + ch if ch in chars else ch
    return out


def exact_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for road in config.get("roads", []):
        names.extend(road.get("osm_exact_names", []))
    return sorted({n.strip() for n in names if n and n.strip()})


def build_name_regex(config: dict[str, Any]) -> str:
    names = exact_names(config)
    if not names:
        raise ValueError("No osm_exact_names configured")
    return "^(" + "|".join(regex_escape(n) for n in names) + ")$"


def build_query(config: dict[str, Any]) -> str:
    b = config["bbox_wgs84"]
    bbox = f'{b["min_lat"]},{b["min_lon"]},{b["max_lat"]},{b["max_lon"]}'
    regex = build_name_regex(config)
    return f"""[out:json][timeout:40];
(
  way["highway"]["name"~"{regex}",i]({bbox});
  way["highway"]["name:th"~"{regex}",i]({bbox});
  way["highway"]["name:en"~"{regex}",i]({bbox});
);
out tags geom;"""


def fetch_overpass(
    endpoint: str, query: str, timeout: float
) -> dict[str, Any]:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_with_fallback(
    endpoints: list[str],
    query: str,
    timeout: float,
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    for index, endpoint in enumerate(endpoints):
        try:
            payload = fetch_overpass(endpoint, query, timeout)
            return payload, endpoint, errors
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(
                {
                    "endpoint": endpoint,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            if index < len(endpoints) - 1:
                time.sleep(1)
    raise RuntimeError(
        "All Overpass endpoints failed: "
        + "; ".join(f'{e["endpoint"]}: {e["error"]}' for e in errors)
    )


def tag_names(tags: dict[str, Any]) -> set[str]:
    return {
        str(tags.get(k)).strip().casefold()
        for k in ("name", "name:th", "name:en")
        if tags.get(k)
    }


def classify_road(
    tags: dict[str, Any], config: dict[str, Any]
) -> str | None:
    observed = tag_names(tags)
    for road in config.get("roads", []):
        expected = {
            str(name).strip().casefold()
            for name in road.get("osm_exact_names", [])
            if name
        }
        if observed & expected:
            return road["id"]
    return None


def to_geojson(
    payload: dict[str, Any],
    config: dict[str, Any],
    endpoint: str,
    prior_errors: list[dict[str, str]],
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    seen: set[int] = set()

    for el in payload.get("elements", []):
        if el.get("type") != "way" or el.get("id") in seen:
            continue

        tags = el.get("tags") or {}
        road_id = classify_road(tags, config)
        if not road_id:
            continue

        geom = el.get("geometry") or []
        coords = [
            [p["lon"], p["lat"]]
            for p in geom
            if "lon" in p and "lat" in p
        ]
        if len(coords) < 2:
            continue

        seen.add(el["id"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "road_id": road_id,
                    "osm_way_id": el["id"],
                    "name": tags.get("name"),
                    "name_th": tags.get("name:th"),
                    "name_en": tags.get("name:en"),
                    "highway": tags.get("highway"),
                    "oneway": tags.get("oneway"),
                    "lanes": tags.get("lanes"),
                    "source": "OpenStreetMap",
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "name": config.get("id", "study_network"),
        "properties": {
            "source": "OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "selection_rule": "exact configured main-road names only",
            "overpass_endpoint": endpoint,
            "fallback_errors_before_success": prior_errors,
        },
        "features": features,
    }


def road_counts(
    geojson: dict[str, Any],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for feature in geojson.get("features", []):
        rid = (feature.get("properties") or {}).get("road_id")
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return counts


def missing_roads(
    geojson: dict[str, Any],
    config: dict[str, Any],
) -> list[str]:
    counts = road_counts(geojson)
    return [
        road["id"]
        for road in config.get("roads", [])
        if counts.get(road["id"], 0) == 0
    ]


def validate_existing(
    path: Path,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if doc.get("type") != "FeatureCollection":
        return None
    if not doc.get("features") or missing_roads(doc, config):
        return None
    return doc


def print_summary(
    geojson: dict[str, Any],
    output: Path,
    geometry_source: str,
) -> None:
    print(
        json.dumps(
            {
                "feature_count": len(geojson.get("features", [])),
                "road_way_counts": road_counts(geojson),
                "missing_road_ids": [],
                "geometry_source": geometry_source,
                "overpass_endpoint": (
                    (geojson.get("properties") or {}).get("overpass_endpoint")
                ),
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    args = parse_args()
    config = load_config(args.config)

    if not args.refresh:
        existing = validate_existing(args.output, config)
        if existing is not None:
            print_summary(existing, args.output, "validated-existing-cache")
            return 0

    endpoints = args.endpoint or DEFAULT_OVERPASS_ENDPOINTS
    payload, endpoint, errors = fetch_with_fallback(
        endpoints,
        build_query(config),
        args.timeout,
    )
    geojson = to_geojson(
        payload,
        config,
        endpoint,
        errors,
    )

    missing = missing_roads(geojson, config)
    if not geojson["features"] or missing:
        print(
            json.dumps(
                {
                    "feature_count": len(geojson["features"]),
                    "road_way_counts": road_counts(geojson),
                    "missing_road_ids": missing,
                    "overpass_endpoint": endpoint,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print_summary(geojson, args.output, "fresh-overpass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
