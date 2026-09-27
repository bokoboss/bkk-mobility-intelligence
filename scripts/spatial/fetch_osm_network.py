#!/usr/bin/env python3
"""Fetch an expanded named-road network from OpenStreetMap/Overpass.

Priority roads keep stable configured IDs. Other named major roads are
discovered dynamically from selected OSM highway classes, grouped by canonical
name, filtered by total in-area length, and assigned stable hash IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

EARTH_M = 6371008.8
DEFAULT_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "bkk-mobility-intelligence-phase0/0.9"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    p.add_argument("--endpoint", action="append", default=[])
    p.add_argument("--timeout", type=float, default=50.0)
    p.add_argument("--refresh", action="store_true")
    return p.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def regex_escape(text: str) -> str:
    return re.escape(text)


def exact_priority_names(config: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for road in config.get("roads", []):
        names.extend(road.get("osm_exact_names", []))
    return sorted({n.strip() for n in names if n and n.strip()})


def priority_name_regex(config: dict[str, Any]) -> str:
    names = exact_priority_names(config)
    return "^(" + "|".join(regex_escape(n) for n in names) + ")$" if names else "^$"


def highway_class_regex(config: dict[str, Any]) -> str:
    classes = config.get("network", {}).get(
        "include_highway_classes",
        ["trunk", "primary", "secondary", "tertiary"],
    )
    cleaned = [str(x).strip() for x in classes if str(x).strip()]
    if not cleaned:
        raise ValueError("No OSM highway classes configured")
    return "^(" + "|".join(regex_escape(x) for x in cleaned) + ")$"


def build_query(config: dict[str, Any]) -> str:
    b = config["bbox_wgs84"]
    bbox = f'{b["min_lat"]},{b["min_lon"]},{b["max_lat"]},{b["max_lon"]}'
    cls = highway_class_regex(config)
    priority = priority_name_regex(config)
    return f"""[out:json][timeout:45];
(
  way["highway"~"{cls}"]["name"]({bbox});
  way["highway"~"{cls}"]["name:th"]({bbox});
  way["highway"~"{cls}"]["name:en"]({bbox});
  way["highway"]["name"~"{priority}",i]({bbox});
  way["highway"]["name:th"~"{priority}",i]({bbox});
  way["highway"]["name:en"~"{priority}",i]({bbox});
);
out tags geom;"""


def fetch_overpass(endpoint: str, query: str, timeout: float) -> dict[str, Any]:
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
    endpoints: list[str], query: str, timeout: float
) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    for index, endpoint in enumerate(endpoints):
        try:
            return fetch_overpass(endpoint, query, timeout), endpoint, errors
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(
                {"endpoint": endpoint, "error": f"{type(exc).__name__}: {exc}"}
            )
            if index < len(endpoints) - 1:
                time.sleep(1)
    raise RuntimeError(
        "All Overpass endpoints failed: "
        + "; ".join(f'{x["endpoint"]}: {x["error"]}' for x in errors)
    )


def clean_name(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def canonical_name(tags: dict[str, Any]) -> str | None:
    return (
        clean_name(tags.get("name:th"))
        or clean_name(tags.get("name"))
        or clean_name(tags.get("name:en"))
    )


def normalized_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def split_refs(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    parts = re.split(r"[;,/]", str(value))
    return sorted({x.strip() for x in parts if x.strip()})


def priority_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for road in config.get("roads", []):
        for name in road.get("osm_exact_names", []):
            lookup[normalized_name(name)] = road
    return lookup


def priority_for_tags(
    tags: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any] | None:
    lookup = priority_lookup(config)
    names = {
        normalized_name(n)
        for n in (
            clean_name(tags.get("name")),
            clean_name(tags.get("name:th")),
            clean_name(tags.get("name:en")),
        )
        if n
    }
    for name in names:
        if name in lookup:
            return lookup[name]
    return None


def dynamic_road_id(name: str) -> str:
    digest = hashlib.sha1(normalized_name(name).encode("utf-8")).hexdigest()[:10]
    return "osm_" + digest


def haversine_m(a: list[float], b: list[float]) -> float:
    lon1, lat1 = map(math.radians, (float(a[0]), float(a[1])))
    lon2, lat2 = map(math.radians, (float(b[0]), float(b[1])))
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_M * math.asin(min(1.0, math.sqrt(h)))


def line_length_m(coords: list[list[float]]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(coords, coords[1:]))


def raw_features(
    payload: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for el in payload.get("elements", []):
        if el.get("type") != "way" or el.get("id") in seen:
            continue
        tags = el.get("tags") or {}
        name = canonical_name(tags)
        geom = el.get("geometry") or []
        coords = [
            [float(p["lon"]), float(p["lat"])]
            for p in geom
            if "lon" in p and "lat" in p
        ]
        if not name or len(coords) < 2:
            continue

        priority = priority_for_tags(tags, config)
        if priority:
            road_id = priority["id"]
            display_name = priority.get("display_name") or name
            aliases = sorted(
                {
                    *[x for x in priority.get("aliases", []) if x],
                    *[
                        x
                        for x in (
                            clean_name(tags.get("name")),
                            clean_name(tags.get("name:th")),
                            clean_name(tags.get("name:en")),
                        )
                        if x
                    ],
                }
            )
            route_refs = sorted(
                {
                    *[str(x) for x in priority.get("route_refs", [])],
                    *split_refs(tags.get("ref")),
                }
            )
            is_priority = True
        else:
            road_id = dynamic_road_id(name)
            display_name = name
            aliases = sorted(
                {
                    x
                    for x in (
                        clean_name(tags.get("name")),
                        clean_name(tags.get("name:th")),
                        clean_name(tags.get("name:en")),
                    )
                    if x
                }
            )
            route_refs = split_refs(tags.get("ref"))
            is_priority = False

        seen.add(el["id"])
        out.append(
            {
                "type": "Feature",
                "properties": {
                    "road_id": road_id,
                    "display_name": display_name,
                    "priority": is_priority,
                    "aliases": aliases,
                    "route_refs": route_refs,
                    "osm_way_id": el["id"],
                    "name": clean_name(tags.get("name")),
                    "name_th": clean_name(tags.get("name:th")),
                    "name_en": clean_name(tags.get("name:en")),
                    "highway": tags.get("highway"),
                    "oneway": tags.get("oneway"),
                    "lanes": tags.get("lanes"),
                    "ref": tags.get("ref"),
                    "length_m": round(line_length_m(coords), 1),
                    "source": "OpenStreetMap",
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )
    return out


def select_network_features(
    features: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for feature in features:
        props = feature["properties"]
        rid = props["road_id"]
        group = groups.setdefault(
            rid,
            {
                "priority": bool(props.get("priority")),
                "total_length_m": 0.0,
                "features": [],
            },
        )
        group["priority"] = group["priority"] or bool(props.get("priority"))
        group["total_length_m"] += float(props.get("length_m") or 0)
        group["features"].append(feature)

    net = config.get("network", {})
    min_length = float(net.get("min_group_length_m", 900))
    max_nonpriority = int(net.get("max_nonpriority_roads", 80))

    priority_ids = {
        rid for rid, group in groups.items() if bool(group["priority"])
    }
    nonpriority = [
        (rid, group)
        for rid, group in groups.items()
        if rid not in priority_ids and group["total_length_m"] >= min_length
    ]
    nonpriority.sort(key=lambda x: x[1]["total_length_m"], reverse=True)
    selected_ids = priority_ids | {
        rid for rid, _ in nonpriority[:max_nonpriority]
    }

    selected: list[dict[str, Any]] = []
    for feature in features:
        rid = feature["properties"]["road_id"]
        if rid not in selected_ids:
            continue
        feature["properties"]["group_total_length_m"] = round(
            groups[rid]["total_length_m"], 1
        )
        selected.append(feature)
    return selected


def road_catalog(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for feature in features:
        p = feature["properties"]
        rid = p["road_id"]
        item = catalog.setdefault(
            rid,
            {
                "road_id": rid,
                "display_name": p.get("display_name") or rid,
                "priority": bool(p.get("priority")),
                "aliases": set(),
                "route_refs": set(),
                "highway_classes": set(),
                "total_length_m": float(p.get("group_total_length_m") or 0),
            },
        )
        item["priority"] = item["priority"] or bool(p.get("priority"))
        item["aliases"].update(p.get("aliases") or [])
        item["route_refs"].update(p.get("route_refs") or [])
        if p.get("highway"):
            item["highway_classes"].add(str(p["highway"]))
        item["total_length_m"] = max(
            item["total_length_m"],
            float(p.get("group_total_length_m") or 0),
        )

    out: list[dict[str, Any]] = []
    for item in catalog.values():
        out.append(
            {
                **item,
                "aliases": sorted(item["aliases"]),
                "route_refs": sorted(item["route_refs"]),
                "highway_classes": sorted(item["highway_classes"]),
                "total_length_m": round(item["total_length_m"], 1),
            }
        )
    out.sort(
        key=lambda x: (
            not x["priority"],
            -x["total_length_m"],
            x["display_name"],
        )
    )
    return out


def to_geojson(
    payload: dict[str, Any],
    config: dict[str, Any],
    endpoint: str,
    prior_errors: list[dict[str, str]],
) -> dict[str, Any]:
    selected = select_network_features(raw_features(payload, config), config)
    return {
        "type": "FeatureCollection",
        "name": config.get("id", "study_network"),
        "properties": {
            "source": "OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "selection_rule": (
                "priority roads + longest named configured OSM highway classes"
            ),
            "overpass_endpoint": endpoint,
            "fallback_errors_before_success": prior_errors,
            "road_catalog": road_catalog(selected),
        },
        "features": selected,
    }


def priority_ids(config: dict[str, Any]) -> set[str]:
    return {road["id"] for road in config.get("roads", [])}


def road_ids(geojson: dict[str, Any]) -> set[str]:
    return {
        (feature.get("properties") or {}).get("road_id")
        for feature in geojson.get("features", [])
        if (feature.get("properties") or {}).get("road_id")
    }


def missing_priority_roads(
    geojson: dict[str, Any], config: dict[str, Any]
) -> list[str]:
    present = road_ids(geojson)
    return sorted(priority_ids(config) - present)


def validate_existing(
    path: Path, config: dict[str, Any]
) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if doc.get("type") != "FeatureCollection":
        return None
    if not doc.get("features") or missing_priority_roads(doc, config):
        return None
    if (doc.get("name") or "") != config.get("id"):
        return None
    return doc


def print_summary(
    geojson: dict[str, Any], output: Path, geometry_source: str
) -> None:
    catalog = (geojson.get("properties") or {}).get("road_catalog") or []
    priority_count = sum(1 for x in catalog if x.get("priority"))
    print(
        json.dumps(
            {
                "feature_count": len(geojson.get("features", [])),
                "road_count": len(catalog),
                "priority_road_count": priority_count,
                "dynamic_road_count": len(catalog) - priority_count,
                "missing_priority_road_ids": [],
                "geometry_source": geometry_source,
                "overpass_endpoint": (
                    (geojson.get("properties") or {}).get("overpass_endpoint")
                ),
                "top_roads": catalog[:20],
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

    payload, endpoint, errors = fetch_with_fallback(
        args.endpoint or DEFAULT_OVERPASS_ENDPOINTS,
        build_query(config),
        args.timeout,
    )
    geojson = to_geojson(payload, config, endpoint, errors)
    missing = missing_priority_roads(geojson, config)
    if not geojson["features"] or missing:
        print(
            json.dumps(
                {
                    "feature_count": len(geojson["features"]),
                    "missing_priority_road_ids": missing,
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
