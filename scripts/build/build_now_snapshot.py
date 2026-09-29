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
    p.add_argument("--traffic-coverage", type=Path, default=Path("data/processed/current_speed/traffic_coverage.json"))
    p.add_argument("--historical-baseline", type=Path, default=Path("data/processed/history/road_time_baseline_v0_3.json"))
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
    traffic_coverage = load(args.traffic_coverage) if args.traffic_coverage.exists() else None
    historical_baseline = load(args.historical_baseline) if args.historical_baseline.exists() else None
    historical_summary = (historical_baseline or {}).get("summary") or {}
    if historical_baseline is None:
        historical_state = "CLOUD_BATCH_REQUIRED"
    elif int(historical_summary.get("ready_road_count", 0)) > 0:
        historical_state = "READY_PARTIAL"
    else:
        historical_state = "BUILT_INSUFFICIENT"

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
    coverage_summary = (traffic_coverage or {}).get("summary") or {}
    planned_road_ids = {
        str(x.get("road_id")) for x in (traffic_coverage or {}).get("planned_points") or []
        if x.get("road_id")
    }
    observed_road_ids = set((traffic_coverage or {}).get("observed_road_ids") or [])

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
        road["traffic_coverage"] = {
            "planned_this_run": rid in planned_road_ids,
            "observed_this_run": rid in observed_road_ids,
        }
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
        "schema": "bkk-mobility-now-v0.5",
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
            "traffic_coverage": {
                "schema": (traffic_coverage or {}).get("schema"),
                "access_state": (traffic_coverage or {}).get("access_state"),
                "request_budget": ((traffic_coverage or {}).get("plan") or {}).get("request_budget"),
                "planned_road_count": coverage_summary.get("planned_road_count", 0),
                "planned_district_count": coverage_summary.get("planned_district_count", 0),
                "observed_road_count": coverage_summary.get("observed_road_count", 0),
                "observed_district_count": coverage_summary.get("observed_district_count", 0),
                "planned_road_coverage_ratio": coverage_summary.get("planned_road_coverage_ratio", 0.0),
                "observed_road_coverage_ratio": coverage_summary.get("observed_road_coverage_ratio", 0.0),
            },
            "historical_baseline": {
                "schema": (historical_baseline or {}).get("schema"),
                "state": historical_state,
                "reference_year": (historical_baseline or {}).get("reference_year")
                    or (config.get("historical_baseline") or {}).get("reference_year"),
                "direction_state": (historical_baseline or {}).get("direction_state")
                    or (config.get("historical_baseline") or {}).get("direction_state"),
                "profile_day_count": historical_summary.get("profile_day_count", 0),
                "ready_road_count": historical_summary.get("ready_road_count", 0),
                "eligible_road_count": historical_summary.get("eligible_road_count", len(roads)),
                "ready_road_coverage_ratio": historical_summary.get("ready_road_coverage_ratio", 0.0),
                "ready_bin_count": historical_summary.get("ready_bin_count", 0),
                "source_date_min": historical_summary.get("source_date_min"),
                "source_date_max": historical_summary.get("source_date_max"),
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
            "traffic_coverage_planned_roads": coverage_summary.get("planned_road_count", 0),
            "traffic_coverage_observed_roads": coverage_summary.get("observed_road_count", 0),
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
            "traffic_coverage": "READY" if traffic_coverage is not None else "MISSING",
            "historical_road_time_baseline": historical_state,
            "current_vs_baseline_segment": (
                "READY_FOR_V0_4_JOIN"
                if sampled_road_count and historical_state == "READY_PARTIAL"
                else "BLOCKED_ON_ROAD_TIME_BASELINE"
                if sampled_road_count
                else "BLOCKED_ON_SEGMENT_SPEED"
            ),
            "now_dashboard": "READY_FOR_HISTORICAL_BASELINE_V0_3_PIPELINE",
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
