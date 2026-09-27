#!/usr/bin/env python3
"""Build the latest frontend-neutral status contract for the expanded network."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--latest-pointer", type=Path, default=Path("data/raw/current/latest.json"))
    p.add_argument("--traffic-index", type=Path, default=Path("data/raw/current_context/traffic_index.json"))
    p.add_argument("--traffic-index-baseline", type=Path, default=Path("data/processed/current_context/traffic_index_baseline.json"))
    p.add_argument("--cameras", type=Path, default=Path("data/raw/current_context/cameras.study_area.json"))
    p.add_argument("--speed", type=Path, default=Path("data/processed/current_speed/longdo_speed.json"))
    p.add_argument("--traffic-state", type=Path, default=Path("data/processed/current_speed/traffic_state.json"))
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument("--output", type=Path, default=Path("data/processed/now/latest_status.json"))
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def network_roads(network: dict[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = (network.get("properties") or {}).get("road_catalog") or []
    return {
        item["road_id"]: {
            "display_name": item.get("display_name") or item["road_id"],
            "priority": bool(item.get("priority")),
            "aliases": item.get("aliases") or [],
            "route_refs": item.get("route_refs") or [],
            "highway_classes": item.get("highway_classes") or [],
            "network_tier": item.get("network_tier"),
            "district_ids": item.get("district_ids") or [],
            "district_names": item.get("district_names") or [],
            "total_length_m": item.get("total_length_m"),
            "confirmed_incidents": [],
        }
        for item in catalog
    }


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
    config = load(args.config)
    network = load(args.network)

    roads = network_roads(network)
    for road in config.get("roads", []):
        roads.setdefault(
            road["id"],
            {
                "display_name": road.get("display_name") or road["id"],
                "priority": True,
                "aliases": road.get("aliases") or [],
                "route_refs": road.get("route_refs") or [],
                "highway_classes": [],
                "network_tier": "FOCUS",
                "district_ids": [],
                "district_names": [],
                "total_length_m": None,
                "confirmed_incidents": [],
            },
        )

    for cluster in clusters_doc.get("clusters", []):
        rid = cluster.get("road_id")
        if rid not in roads:
            roads[rid] = {
                "display_name": cluster.get("road_name") or rid,
                "priority": False,
                "aliases": [],
                "route_refs": cluster.get("event_route_refs") or [],
                "highway_classes": [],
                "network_tier": None,
                "district_ids": [cluster.get("district_id")] if cluster.get("district_id") else [],
                "district_names": [cluster.get("district_name_th")] if cluster.get("district_name_th") else [],
                "total_length_m": None,
                "confirmed_incidents": [],
            }
        roads[rid]["confirmed_incidents"].append(cluster)

    traffic_state = load(args.traffic_state) if args.traffic_state.exists() else None
    traffic_roads = (traffic_state or {}).get("roads") or {}
    traffic_summary = (traffic_state or {}).get("summary") or {}
    traffic_access = (traffic_state or {}).get("access_state") or "BLOCKED_NO_TRAFFIC_STATE"

    for rid, road in roads.items():
        state = traffic_roads.get(rid) or {
            "status": "NO_SAMPLE",
            "sample_count": 0,
            "median_speed_kmh": None,
            "movement_class": "UNKNOWN",
            "baseline_state": "NOT_BUILT",
            "abnormality_state": "NOT_EVALUATED",
        }
        road["confirmed_incident_count"] = len(road["confirmed_incidents"])
        road["traffic_state"] = state
        road["speed_status"] = state.get("status") or "NO_SAMPLE"
        road["data_statement"] = (
            "Confirmed incident activity present"
            if road["confirmed_incident_count"]
            else "No confirmed incident in current feed"
        )
        road["data_statement_caveat"] = (
            "No confirmed incident does not prove the road is disruption-free; "
            "the event feed is not assumed to be a complete census."
        )

    priority_count = sum(1 for road in roads.values() if road.get("priority"))
    active_roads = sum(
        1 for road in roads.values() if road.get("confirmed_incident_count", 0) > 0
    )
    sampled_road_count = sum(
        1 for road in roads.values()
        if int((road.get("traffic_state") or {}).get("sample_count") or 0) > 0
    )

    district_counts: dict[str, dict[str, Any]] = {}
    for cluster in clusters_doc.get("clusters", []):
        did = str(cluster.get("district_id") or "")
        if not did:
            continue
        row = district_counts.setdefault(
            did,
            {
                "district_id": did,
                "district_name_th": cluster.get("district_name_th") or did,
                "district_name_en": cluster.get("district_name_en") or "",
                "confirmed_incident_count": 0,
            },
        )
        row["confirmed_incident_count"] += 1
    district_rows = sorted(
        district_counts.values(),
        key=lambda x: (-x["confirmed_incident_count"], x["district_name_th"]),
    )

    strategic_count = sum(
        1 for road in roads.values() if road.get("network_tier") == "STRATEGIC"
    )
    urban_count = sum(
        1 for road in roads.values() if road.get("network_tier") == "URBAN"
    )

    result = {
        "schema": "bkk-mobility-now-v0.3",
        "study_area_id": manifest.get("study_area_id"),
        "study_area_name": config.get("name"),
        "study_area_bbox_wgs84": config.get("bbox_wgs84"),
        "generated_from_run": manifest.get("run_id"),
        "source_status": {
            "events": manifest["sources"]["events"]["freshness_class"],
            "anonymous_traffic_free": manifest["sources"]["traffic_free"]["freshness_class"],
            "segment_speed": traffic_access,
        },
        "source_details": {
            "events": {
                "provider": manifest["sources"]["events"].get("provider"),
                "retrieved_at_utc": manifest["sources"]["events"].get("retrieved_at_utc"),
                "latest_event_start": (manifest["sources"]["events"].get("audit") or {}).get("latest_event_start"),
                "latest_event_age_hours": (manifest["sources"]["events"].get("audit") or {}).get("latest_event_start_age_hours_at_retrieval"),
            },
            "traffic_index": {
                "provider": ti.get("provider"),
                "source_time_utc": ti["data"].get("source_time_utc"),
                "retrieved_at_utc": ti["data"].get("retrieved_at_utc"),
                "age_minutes_at_retrieval": ti["data"].get("age_minutes_at_retrieval"),
            },
            "segment_speed": {
                "provider": (traffic_state or {}).get("provider"),
                "retrieved_at_utc": (traffic_state or {}).get("retrieved_at_utc"),
                "access_state": traffic_access,
                "sampled_road_count": traffic_summary.get("sampled_road_count", 0),
                "road_count": traffic_summary.get("road_count", len(roads)),
                "sampling_coverage_ratio": traffic_summary.get("sampling_coverage_ratio", 0.0),
                "usable_observation_count": traffic_summary.get("usable_observation_count", 0),
                "interpretation": traffic_summary.get("interpretation"),
            },
        },
        "city_context": {
            "traffic_index": ti["data"],
            "traffic_index_baseline": ti_baseline,
        },
        "network_summary": {
            "road_count": len(roads),
            "priority_road_count": priority_count,
            "dynamic_road_count": len(roads) - priority_count,
            "roads_with_confirmed_incidents": active_roads,
            "roads_with_speed_samples": sampled_road_count,
            "strategic_road_count": strategic_count,
            "urban_road_count": urban_count,
            "district_count": int((config.get("admin_geometry") or {}).get("district_count", 50)),
        },
        "district_summary": {
            "district_count": int((config.get("admin_geometry") or {}).get("district_count", 50)),
            "districts_with_confirmed_incidents": len(district_rows),
            "top_current_districts": district_rows[:15],
        },
        "network_incidents": {
            "confirmed_record_count": clusters_doc["summary"]["confirmed_record_count"],
            "distinct_confirmed_incidents": clusters_doc["summary"]["confirmed_cluster_count"],
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
                "EXPERIMENTAL_PARTIAL" if sampled_road_count else "BLOCKED_ON_PROVIDER_ACCESS"
            ),
            "current_vs_baseline_segment": (
                "BLOCKED_ON_ROAD_TIME_BASELINE"
                if sampled_road_count
                else "BLOCKED_ON_SEGMENT_SPEED"
            ),
            "now_dashboard": "READY_FOR_BANGKOK_WIDE_INCIDENT_AND_CONTEXT_POC",
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
                "study_area": result["study_area_name"],
                "network_summary": result["network_summary"],
                "readiness": result["readiness"],
                "distinct_confirmed_incidents": result["network_incidents"]["distinct_confirmed_incidents"],
                "traffic_index": result["city_context"]["traffic_index"]["index"],
                "traffic_index_class": result["city_context"]["traffic_index_baseline"]["baseline"]["classification"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
