#!/usr/bin/env python3
"""Fetch exact core-road geometry from OpenStreetMap/Overpass.

General event text aliases are intentionally NOT used for the OSM query because
substring matches pull in side streets such as ซอยรามอินทรา. Core geometry uses
the explicit per-road osm_exact_names list in config/study_area.json.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.4"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/osm/core_roads.geojson"),
    )
    p.add_argument("--endpoint", default=DEFAULT_OVERPASS)
    p.add_argument("--timeout", type=float, default=60.0)
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
    return f"""[out:json][timeout:45];
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
    payload: dict[str, Any], config: dict[str, Any]
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
        },
        "features": features,
    }


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    geojson = to_geojson(
        fetch_overpass(
            args.endpoint,
            build_query(config),
            args.timeout,
        ),
        config,
    )

    counts: dict[str, int] = {}
    for feature in geojson["features"]:
        rid = feature["properties"]["road_id"]
        counts[rid] = counts.get(rid, 0) + 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    missing = [
        road["id"]
        for road in config.get("roads", [])
        if counts.get(road["id"], 0) == 0
    ]
    print(
        json.dumps(
            {
                "feature_count": len(geojson["features"]),
                "road_way_counts": counts,
                "missing_road_ids": missing,
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if geojson["features"] and not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
