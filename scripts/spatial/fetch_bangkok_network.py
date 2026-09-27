#!/usr/bin/env python3
"""Fetch Bangkok-wide named major roads using tiled Overpass queries.

The citywide road query is split into small bbox tiles so no single Overpass
request carries the whole Bangkok network. OSM way IDs are deduplicated across
tiles, roads are grouped by stable name-based IDs, clipped to the Bangkok
50-district geometry, and annotated with district membership.
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

import geo_admin

EARTH_M = 6371008.8
ENDPOINTS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
USER_AGENT = "bkk-mobility-intelligence-citywide/1.0"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--output", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument("--timeout", type=float, default=35.0)
    p.add_argument("--endpoint", action="append", default=[])
    return p.parse_args()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def clean_name(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    return text or None


def split_refs(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    return sorted({x.strip() for x in re.split(r"[;,/]", str(value)) if x.strip()})


def dynamic_road_id(name: str) -> str:
    return "osm_" + hashlib.sha1(normalized_name(name).encode("utf-8")).hexdigest()[:10]


def exact_priority_names(config: dict[str, Any]) -> list[str]:
    return sorted({
        str(name).strip()
        for road in config.get("roads", [])
        for name in road.get("osm_exact_names", [])
        if str(name).strip()
    })


def priority_lookup(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for road in config.get("roads", []):
        for name in road.get("osm_exact_names", []):
            out[normalized_name(name)] = road
    return out


def priority_for_tags(tags: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    lookup = priority_lookup(config)
    for value in (tags.get("name"), tags.get("name:th"), tags.get("name:en")):
        name = clean_name(value)
        if name and normalized_name(name) in lookup:
            return lookup[normalized_name(name)]
    return None


def canonical_name(tags: dict[str, Any]) -> str | None:
    return clean_name(tags.get("name:th")) or clean_name(tags.get("name")) or clean_name(tags.get("name:en"))


def excluded_name(name: str, config: dict[str, Any]) -> bool:
    hay = normalized_name(name)
    patterns = config.get("network", {}).get("exclude_name_patterns", [])
    return any(normalized_name(str(x)) in hay for x in patterns)


def highway_classes(config: dict[str, Any]) -> list[str]:
    return [str(x).strip() for x in config.get("network", {}).get("include_highway_classes", []) if str(x).strip()]


def class_regex(config: dict[str, Any]) -> str:
    values = highway_classes(config)
    if not values:
        raise ValueError("network.include_highway_classes is empty")
    return "^(" + "|".join(re.escape(x) for x in values) + ")$"


def tile_bboxes(config: dict[str, Any]) -> list[dict[str, float]]:
    b = config["bbox_wgs84"]
    rows = max(1, int(config.get("network", {}).get("tile_rows", 3)))
    cols = max(1, int(config.get("network", {}).get("tile_cols", 3)))
    lat_step = (float(b["max_lat"]) - float(b["min_lat"])) / rows
    lon_step = (float(b["max_lon"]) - float(b["min_lon"])) / cols
    tiles = []
    for r in range(rows):
        for c in range(cols):
            tiles.append({
                "min_lat": float(b["min_lat"]) + r * lat_step,
                "max_lat": float(b["min_lat"]) + (r + 1) * lat_step,
                "min_lon": float(b["min_lon"]) + c * lon_step,
                "max_lon": float(b["min_lon"]) + (c + 1) * lon_step,
                "row": r,
                "col": c,
            })
    return tiles


def build_query(config: dict[str, Any], bbox: dict[str, float] | None = None) -> str:
    b = bbox or config["bbox_wgs84"]
    box = f'{b["min_lat"]},{b["min_lon"]},{b["max_lat"]},{b["max_lon"]}'
    cls = class_regex(config)
    priority = exact_priority_names(config)
    priority_re = "^(" + "|".join(re.escape(x) for x in priority) + ")$" if priority else "^$"
    return f"""[out:json][timeout:30];
(
  way["highway"~"{cls}"]["name"]({box});
  way["highway"~"{cls}"]["name:th"]({box});
  way["highway"~"{cls}"]["name:en"]({box});
  way["highway"]["name"~"{priority_re}",i]({box});
  way["highway"]["name:th"~"{priority_re}",i]({box});
);
out tags geom;"""


def fetch_overpass(endpoint: str, query: str, timeout: float) -> dict[str, Any]:
    body = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(endpoint, data=body, headers={
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_tile(endpoints: list[str], query: str, timeout: float) -> tuple[dict[str, Any], str, list[dict[str, str]]]:
    errors = []
    for endpoint in endpoints:
        try:
            return fetch_overpass(endpoint, query, timeout), endpoint, errors
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append({"endpoint": endpoint, "error": f"{type(exc).__name__}: {exc}"})
            time.sleep(0.5)
    raise RuntimeError("all Overpass endpoints failed: " + "; ".join(x["error"] for x in errors))


def haversine_m(a: list[float], b: list[float]) -> float:
    lon1, lat1 = map(math.radians, (float(a[0]), float(a[1])))
    lon2, lat2 = map(math.radians, (float(b[0]), float(b[1])))
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 2 * EARTH_M * math.asin(min(1.0, math.sqrt(h)))


def line_length_m(coords: list[list[float]]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(coords, coords[1:]))


def network_tier(highway: Any) -> str:
    value = str(highway or "")
    return "STRATEGIC" if value in {"motorway", "trunk", "primary", "secondary"} else "URBAN"


def inside_bangkok(coords: list[list[float]], districts: list[dict[str, Any]]) -> bool:
    for point in geo_admin.sample_line_points(coords, max_points=18):
        if len(point) >= 2 and geo_admin.district_for_point(float(point[0]), float(point[1]), districts):
            return True
    return False


def raw_features(elements: list[dict[str, Any]], config: dict[str, Any], districts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for el in elements:
        if el.get("type") != "way":
            continue
        tags = el.get("tags") or {}
        name = canonical_name(tags)
        geom = el.get("geometry") or []
        coords = [[float(p["lon"]), float(p["lat"])] for p in geom if "lon" in p and "lat" in p]
        if not name or len(coords) < 2 or not inside_bangkok(coords, districts):
            continue
        priority = priority_for_tags(tags, config)
        if not priority and excluded_name(name, config):
            continue
        if priority:
            road_id = priority["id"]
            display_name = priority.get("display_name") or name
            aliases = sorted({
                *[str(x) for x in priority.get("aliases", []) if x],
                *[x for x in (clean_name(tags.get("name")), clean_name(tags.get("name:th")), clean_name(tags.get("name:en"))) if x],
            })
            refs = sorted({*[str(x) for x in priority.get("route_refs", [])], *split_refs(tags.get("ref"))})
            is_priority = True
        else:
            road_id = dynamic_road_id(name)
            display_name = name
            aliases = sorted({x for x in (clean_name(tags.get("name")), clean_name(tags.get("name:th")), clean_name(tags.get("name:en"))) if x})
            refs = split_refs(tags.get("ref"))
            is_priority = False
        memberships = geo_admin.districts_for_line(coords, districts)
        out.append({
            "type": "Feature",
            "properties": {
                "road_id": road_id,
                "display_name": display_name,
                "priority": is_priority,
                "network_tier": network_tier(tags.get("highway")),
                "aliases": aliases,
                "route_refs": refs,
                "osm_way_id": el.get("id"),
                "highway": tags.get("highway"),
                "ref": tags.get("ref"),
                "length_m": round(line_length_m(coords), 1),
                "district_ids": [x["district_id"] for x in memberships],
                "district_names": [x["district_name_th"] for x in memberships],
                "source": "OpenStreetMap",
            },
            "geometry": {"type": "LineString", "coordinates": coords},
        })
    return out


def select_network_features(features: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for feature in features:
        p = feature["properties"]
        group = groups.setdefault(p["road_id"], {
            "priority": False,
            "total_length_m": 0.0,
            "tiers": set(),
            "features": [],
        })
        group["priority"] = group["priority"] or bool(p.get("priority"))
        group["total_length_m"] += float(p.get("length_m") or 0)
        group["tiers"].add(str(p.get("network_tier") or "URBAN"))
        group["features"].append(feature)

    net = config.get("network", {})
    strategic_min = float(net.get("min_group_length_m_strategic", 300))
    urban_min = float(net.get("min_group_length_m_urban", 1200))
    selected_ids = set()
    for rid, group in groups.items():
        tier = "STRATEGIC" if "STRATEGIC" in group["tiers"] else "URBAN"
        threshold = strategic_min if tier == "STRATEGIC" else urban_min
        if group["priority"] or group["total_length_m"] >= threshold:
            selected_ids.add(rid)

    max_nonpriority = int(net.get("max_nonpriority_roads") or 0)
    if max_nonpriority > 0:
        priority_ids = {rid for rid in selected_ids if groups[rid]["priority"]}
        dynamic = [rid for rid in selected_ids if rid not in priority_ids]
        dynamic.sort(key=lambda rid: groups[rid]["total_length_m"], reverse=True)
        selected_ids = priority_ids | set(dynamic[:max_nonpriority])

    out = []
    for feature in features:
        rid = feature["properties"]["road_id"]
        if rid in selected_ids:
            feature["properties"]["group_total_length_m"] = round(groups[rid]["total_length_m"], 1)
            out.append(feature)
    return out


def road_catalog(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for feature in features:
        p = feature["properties"]
        rid = p["road_id"]
        row = groups.setdefault(rid, {
            "road_id": rid,
            "display_name": p.get("display_name") or rid,
            "priority": bool(p.get("priority")),
            "network_tier": p.get("network_tier") or "URBAN",
            "aliases": set(),
            "route_refs": set(),
            "highway_classes": set(),
            "district_ids": set(),
            "district_names": set(),
            "total_length_m": 0.0,
        })
        row["priority"] = row["priority"] or bool(p.get("priority"))
        if p.get("network_tier") == "STRATEGIC":
            row["network_tier"] = "STRATEGIC"
        row["aliases"].update(p.get("aliases") or [])
        row["route_refs"].update(p.get("route_refs") or [])
        if p.get("highway"):
            row["highway_classes"].add(str(p["highway"]))
        row["district_ids"].update(p.get("district_ids") or [])
        row["district_names"].update(p.get("district_names") or [])
        row["total_length_m"] = max(row["total_length_m"], float(p.get("group_total_length_m") or 0))

    out = []
    for row in groups.values():
        out.append({
            **row,
            "aliases": sorted(row["aliases"]),
            "route_refs": sorted(row["route_refs"]),
            "highway_classes": sorted(row["highway_classes"]),
            "district_ids": sorted(row["district_ids"]),
            "district_names": sorted(row["district_names"]),
            "total_length_m": round(row["total_length_m"], 1),
        })
    out.sort(key=lambda x: (
        not x["priority"],
        x["network_tier"] != "STRATEGIC",
        -x["total_length_m"],
        x["display_name"],
    ))
    return out


def main() -> int:
    args = parse_args()
    config = load(args.config)
    admin_path = Path(config["admin_geometry"]["path"])
    admin_doc = geo_admin.load_geojson(admin_path)
    districts = geo_admin.prepare_districts(admin_doc)
    if len(districts) != int(config["admin_geometry"].get("district_count", 50)):
        raise RuntimeError(f"district geometry count mismatch: {len(districts)}")

    endpoints = args.endpoint or ENDPOINTS
    elements_by_id: dict[int, dict[str, Any]] = {}
    tile_results = []
    for tile in tile_bboxes(config):
        query = build_query(config, tile)
        payload, endpoint, errors = fetch_tile(endpoints, query, args.timeout)
        count_before = len(elements_by_id)
        for el in payload.get("elements", []):
            if el.get("type") == "way" and isinstance(el.get("id"), int):
                elements_by_id[el["id"]] = el
        tile_results.append({
            "row": tile["row"],
            "col": tile["col"],
            "endpoint": endpoint,
            "element_count": len(payload.get("elements", [])),
            "new_way_count": len(elements_by_id) - count_before,
            "fallback_errors": errors,
        })
        print(json.dumps(tile_results[-1], ensure_ascii=False))

    raw = raw_features(list(elements_by_id.values()), config, districts)
    selected = select_network_features(raw, config)
    catalog = road_catalog(selected)
    strategic = sum(1 for x in catalog if x["network_tier"] == "STRATEGIC")
    priority = sum(1 for x in catalog if x["priority"])

    result = {
        "type": "FeatureCollection",
        "name": config["id"],
        "properties": {
            "source": "OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "selection_rule": "Bangkok polygon clip + named strategic roads + sufficiently long named tertiary roads",
            "admin_geometry_path": str(admin_path),
            "district_count": len(districts),
            "tile_count": len(tile_results),
            "tile_results": tile_results,
            "road_catalog": catalog,
        },
        "features": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "feature_count": len(selected),
        "road_count": len(catalog),
        "priority_road_count": priority,
        "strategic_road_count": strategic,
        "urban_road_count": len(catalog) - strategic,
        "district_count": len(districts),
        "tile_count": len(tile_results),
        "top_roads": catalog[:20],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
