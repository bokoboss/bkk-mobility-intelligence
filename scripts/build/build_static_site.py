#!/usr/bin/env python3
"""Build the zero-dependency static Now dashboard from validated data outputs.

The analytical OSM file keeps every way fragment. The dashboard receives a
render-optimized network with one MultiLineString feature per road, reducing DOM
nodes and repeated metadata while preserving the analytical source unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--web-dir", type=Path, default=Path("web"))
    p.add_argument("--output-dir", type=Path, default=Path("dist"))
    p.add_argument("--status", type=Path, default=Path("data/processed/now/latest_status.json"))
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument(
        "--history",
        type=Path,
        default=Path("data/processed/history/recent_incident_intelligence.json"),
    )
    p.add_argument(
        "--flood",
        type=Path,
        default=Path("data/processed/flood/flood_intelligence.json"),
    )
    return p.parse_args()


def rounded_line(coords: list[list[float]]) -> list[list[float]]:
    return [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in coords]


def render_network(network: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for feature in network.get("features", []):
        props = feature.get("properties") or {}
        rid = props.get("road_id")
        geom = feature.get("geometry") or {}
        if not rid or geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue

        group = groups.setdefault(
            rid,
            {
                "properties": {
                    "road_id": rid,
                    "display_name": props.get("display_name") or rid,
                    "priority": bool(props.get("priority")),
                },
                "lines": [],
            },
        )
        group["properties"]["priority"] = (
            group["properties"]["priority"] or bool(props.get("priority"))
        )
        group["lines"].append(rounded_line(coords))

    features = [
        {
            "type": "Feature",
            "properties": group["properties"],
            "geometry": {
                "type": "MultiLineString",
                "coordinates": group["lines"],
            },
        }
        for group in groups.values()
    ]
    features.sort(
        key=lambda f: (
            not bool(f["properties"].get("priority")),
            str(f["properties"].get("display_name") or ""),
        )
    )

    return {
        "type": "FeatureCollection",
        "name": network.get("name"),
        "properties": {
            "source": "OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "attribution": "© OpenStreetMap contributors",
            "render_optimized": True,
            "road_feature_count": len(features),
        },
        "features": features,
    }


def main() -> int:
    args = parse_args()
    required = [
        args.web_dir / "index.html",
        args.web_dir / "styles.css",
        args.web_dir / "app.js",
        args.status,
        args.network,
        args.history,
        args.flood,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing dashboard inputs: " + ", ".join(missing))

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    data_dir = args.output_dir / "data"
    data_dir.mkdir(parents=True)

    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(args.web_dir / name, args.output_dir / name)

    shutil.copy2(args.status, data_dir / "latest_status.json")
    shutil.copy2(args.history, data_dir / "recent_incident_intelligence.json")
    shutil.copy2(args.flood, data_dir / "flood_intelligence.json")

    full_network = json.loads(args.network.read_text(encoding="utf-8"))
    web_network = render_network(full_network)
    (data_dir / "core_roads.geojson").write_text(
        json.dumps(web_network, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    status = json.loads(args.status.read_text(encoding="utf-8"))
    network_bytes = (data_dir / "core_roads.geojson").stat().st_size
    build_info = {
        "schema": "bkk-mobility-static-build-v0.2",
        "generated_from_run": status.get("generated_from_run"),
        "study_area_id": status.get("study_area_id"),
        "render_network_feature_count": len(web_network["features"]),
        "render_network_bytes": network_bytes,
        "files": [
            "index.html",
            "styles.css",
            "app.js",
            "data/latest_status.json",
            "data/core_roads.geojson",
            "data/recent_incident_intelligence.json",
            "data/flood_intelligence.json",
        ],
    }
    (data_dir / "build_info.json").write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "generated_from_run": status.get("generated_from_run"),
                "render_network_feature_count": len(web_network["features"]),
                "render_network_bytes": network_bytes,
                "readiness": status.get("readiness"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
