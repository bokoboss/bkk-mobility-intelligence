#!/usr/bin/env python3
"""Build a frontend-neutral latest-status contract from validated Phase 0 data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--latest-pointer", type=Path, default=Path("data/raw/current/latest.json"))
    p.add_argument(
        "--traffic-index",
        type=Path,
        default=Path("data/raw/current_context/traffic_index.json"),
    )
    p.add_argument(
        "--traffic-index-baseline",
        type=Path,
        default=Path("data/processed/current_context/traffic_index_baseline.json"),
    )
    p.add_argument(
        "--cameras",
        type=Path,
        default=Path("data/raw/current_context/cameras.study_area.json"),
    )
    p.add_argument(
        "--speed",
        type=Path,
        default=Path("data/processed/current_speed/longdo_speed.json"),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/now/latest_status.json"),
    )
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    pointer = load(args.latest_pointer)
    manifest_path = Path(pointer["manifest"])
    run_dir = manifest_path.parent
    manifest = load(manifest_path)
    clusters_doc = load(run_dir / "incidents.confirmed_clusters.json")
    ti = load(args.traffic_index)
    ti_baseline = load(args.traffic_index_baseline)
    cameras = load(args.cameras)

    roads = {
        "ram_inthra": {"confirmed_incidents": []},
        "prasert_manukitch": {"confirmed_incidents": []},
        "pradit_manutham": {"confirmed_incidents": []},
        "nuan_chan": {"confirmed_incidents": []},
    }
    for cluster in clusters_doc.get("clusters", []):
        rid = cluster.get("road_id")
        if rid in roads:
            roads[rid]["confirmed_incidents"].append(cluster)

    speed = None
    if args.speed.exists():
        speed = load(args.speed)

    for rid, road in roads.items():
        road["confirmed_incident_count"] = len(road["confirmed_incidents"])
        road["speed_status"] = (
            "AVAILABLE_EXPERIMENTAL" if speed is not None else "UNAVAILABLE"
        )
        road["data_statement"] = (
            "No confirmed incident in current feed"
            if road["confirmed_incident_count"] == 0
            else "Confirmed incident activity present"
        )
        road["data_statement_caveat"] = (
            "No confirmed incident does not prove the road is disruption-free; "
            "the event feed is not assumed to be a complete census."
        )

    result = {
        "schema": "bkk-mobility-now-v0.1",
        "study_area_id": manifest.get("study_area_id"),
        "generated_from_run": manifest.get("run_id"),
        "source_status": {
            "events": manifest["sources"]["events"]["freshness_class"],
            "anonymous_traffic_free": manifest["sources"]["traffic_free"][
                "freshness_class"
            ],
            "segment_speed": (
                "AVAILABLE_EXPERIMENTAL" if speed is not None else "UNAVAILABLE"
            ),
        },
        "city_context": {
            "traffic_index": ti["data"],
            "traffic_index_baseline": ti_baseline,
        },
        "network_incidents": {
            "confirmed_record_count": clusters_doc["summary"][
                "confirmed_record_count"
            ],
            "distinct_confirmed_incidents": clusters_doc["summary"][
                "confirmed_cluster_count"
            ],
            "clusters_by_road": clusters_doc["summary"]["clusters_by_road"],
        },
        "camera_context": {
            "study_area_camera_records": cameras["study_area_camera_records"],
            "within_1km_of_bbox": cameras["within_1km_of_bbox"],
            "within_3km_of_bbox": cameras["within_3km_of_bbox"],
            "nearest_cameras": cameras["nearest_cameras"][:5],
            "role": "visual context only",
        },
        "roads": roads,
        "readiness": {
            "incident_now": "READY",
            "city_context_now": "READY",
            "segment_speed_now": (
                "EXPERIMENTAL" if speed is not None else "BLOCKED_ON_PROVIDER_ACCESS"
            ),
            "current_vs_baseline_segment": "BLOCKED_ON_SEGMENT_SPEED",
            "now_dashboard": "READY_FOR_INCIDENT_AND_CONTEXT_POC",
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "readiness": result["readiness"],
                "distinct_confirmed_incidents": result["network_incidents"][
                    "distinct_confirmed_incidents"
                ],
                "traffic_index": result["city_context"]["traffic_index"]["index"],
                "traffic_index_class": result["city_context"][
                    "traffic_index_baseline"
                ]["baseline"]["classification"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
