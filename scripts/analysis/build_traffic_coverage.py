#!/usr/bin/env python3
"""Build Traffic Coverage v0.2 for Bangkok-wide speed sampling."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SPATIAL_DIR = Path(__file__).parents[1] / "spatial"
sys.path.insert(0, str(SPATIAL_DIR.resolve()))
import geo_admin  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--network", type=Path, default=Path("data/processed/osm/core_roads.geojson"))
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--traffic-state", type=Path, default=Path("data/processed/current_speed/traffic_state.json"))
    p.add_argument("--plan-output", type=Path, default=Path("data/processed/current_speed/traffic_sampling_plan.json"))
    p.add_argument("--output", type=Path, default=Path("data/processed/current_speed/traffic_coverage.json"))
    p.add_argument("--request-budget", type=int, default=None)
    p.add_argument("--rotation-slot", default=None)
    p.add_argument("--plan-only", action="store_true")
    return p.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_rank(slot: str, value: str) -> int:
    digest = hashlib.sha1(f"{slot}|{value}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def catalog_lookup(network: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for row in (network.get("properties") or {}).get("road_catalog") or []:
        rid = str(row.get("road_id") or "")
        if rid:
            out[rid] = row
    return out


def candidate_points(network: dict[str, Any], districts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build one representative probe candidate per road x district."""
    catalog = catalog_lookup(network)
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}

    for feature in network.get("features") or []:
        props = feature.get("properties") or {}
        rid = str(props.get("road_id") or "")
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if not rid or len(coords) < 2:
            continue

        meta = catalog.get(rid) or {}
        feature_length = float(props.get("length_m") or 0)
        seen_districts: set[str] = set()
        for point in geo_admin.sample_line_points(coords, max_points=14):
            if len(point) < 2:
                continue
            lon, lat = float(point[0]), float(point[1])
            district = geo_admin.district_for_point(lon, lat, districts)
            if not district:
                continue
            did = str(district["district_id"])
            if did in seen_districts:
                continue
            seen_districts.add(did)
            key = (rid, did)
            row = {
                "road_id": rid,
                "road_name": meta.get("display_name") or props.get("display_name") or rid,
                "network_tier": meta.get("network_tier") or props.get("network_tier") or "URBAN",
                "district_id": did,
                "district_name_th": district.get("district_name_th") or did,
                "district_name_en": district.get("district_name_en") or "",
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "road_total_length_m": float(meta.get("total_length_m") or props.get("group_total_length_m") or feature_length),
                "_feature_length_m": feature_length,
            }
            prior = by_pair.get(key)
            if prior is None or row["_feature_length_m"] > prior["_feature_length_m"]:
                by_pair[key] = row

    out = []
    for row in by_pair.values():
        item = dict(row)
        item.pop("_feature_length_m", None)
        out.append(item)
    out.sort(key=lambda x: (x["district_id"], x["network_tier"] != "STRATEGIC", x["road_id"]))
    return out


def choose_plan(
    candidates: list[dict[str, Any]],
    budget: int,
    strategic_target_share: float,
    rotation_slot: str,
) -> list[dict[str, Any]]:
    """Choose a deterministic rotating plan with district spread and unique roads."""
    budget = max(0, int(budget))
    if not candidates or budget == 0:
        return []

    by_district: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_district[str(row["district_id"])].append(row)

    district_order = sorted(by_district, key=lambda did: stable_rank(rotation_slot, f"district:{did}"))
    target_strategic = round(budget * min(1.0, max(0.0, strategic_target_share)))
    selected: list[dict[str, Any]] = []
    used_roads: set[str] = set()
    district_counts: Counter[str] = Counter()
    strategic_count = 0

    def candidate_key(row: dict[str, Any]) -> tuple:
        need_strategic = strategic_count < target_strategic
        tier_penalty = 0 if ((row["network_tier"] == "STRATEGIC") == need_strategic) else 1
        road_len = float(row.get("road_total_length_m") or 0)
        rotate = stable_rank(rotation_slot, f"road:{row['road_id']}:{row['district_id']}")
        return (tier_penalty, -road_len, rotate, row["road_id"])

    for did in district_order:
        if len(selected) >= budget:
            break
        options = [x for x in by_district[did] if x["road_id"] not in used_roads]
        if not options:
            continue
        chosen = sorted(options, key=candidate_key)[0]
        selected.append(chosen)
        used_roads.add(chosen["road_id"])
        district_counts[did] += 1
        if chosen["network_tier"] == "STRATEGIC":
            strategic_count += 1

    while len(selected) < budget:
        options = [x for x in candidates if x["road_id"] not in used_roads]
        if not options:
            break
        need_strategic = strategic_count < target_strategic

        def fill_key(row: dict[str, Any]) -> tuple:
            tier_penalty = 0 if ((row["network_tier"] == "STRATEGIC") == need_strategic) else 1
            did = str(row["district_id"])
            road_len = float(row.get("road_total_length_m") or 0)
            rotate = stable_rank(rotation_slot, f"fill:{row['road_id']}:{did}")
            return (district_counts[did], tier_penalty, -road_len, rotate, row["road_id"])

        chosen = sorted(options, key=fill_key)[0]
        selected.append(chosen)
        used_roads.add(chosen["road_id"])
        district_counts[str(chosen["district_id"])] += 1
        if chosen["network_tier"] == "STRATEGIC":
            strategic_count += 1

    return [{**row, "plan_rank": i + 1} for i, row in enumerate(selected)]


def build_plan(
    network: dict[str, Any],
    config: dict[str, Any],
    rotation_slot: str,
    request_budget: int | None = None,
) -> dict[str, Any]:
    districts = geo_admin.prepare_districts(geo_admin.load_geojson(Path(config["admin_geometry"]["path"])))
    candidates = candidate_points(network, districts)
    sampling_cfg = config.get("traffic_sampling") or {}
    budget = int(request_budget if request_budget is not None else sampling_cfg.get("request_budget_per_run", 30))
    share = float(sampling_cfg.get("strategic_target_share", 0.70))
    planned = choose_plan(candidates, budget, share, rotation_slot)

    return {
        "schema": "bkk-mobility-traffic-sampling-plan-v0.2",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "rotation_slot": rotation_slot,
        "request_budget": budget,
        "budget_role": "Internal project-side request cap; not a provider quota.",
        "strategic_target_share": share,
        "max_points_per_road": 1,
        "rotation_policy": "UTC-day deterministic rotation across eligible roads and districts",
        "coverage_basis": "road-district probe point; not lane-km, direction, or full road-length coverage",
        "eligible_candidate_count": len(candidates),
        "eligible_road_count": len({x["road_id"] for x in candidates}),
        "eligible_district_count": len({x["district_id"] for x in candidates}),
        "planned_request_count": len(planned),
        "planned_road_count": len({x["road_id"] for x in planned}),
        "planned_district_count": len({x["district_id"] for x in planned}),
        "planned_points": planned,
    }


def pct(num: int, den: int) -> float:
    return round(num / den, 4) if den else 0.0


def build_coverage(
    network: dict[str, Any],
    config: dict[str, Any],
    plan: dict[str, Any],
    traffic_state: dict[str, Any] | None,
) -> dict[str, Any]:
    districts = geo_admin.prepare_districts(geo_admin.load_geojson(Path(config["admin_geometry"]["path"])))
    district_meta = {str(x["district_id"]): x for x in districts}
    candidates = candidate_points(network, districts)
    catalog = catalog_lookup(network)
    planned = plan.get("planned_points") or []
    observations = (traffic_state or {}).get("observations") or []

    candidate_roads_by_district: dict[str, set[str]] = defaultdict(set)
    for row in candidates:
        candidate_roads_by_district[str(row["district_id"])].add(str(row["road_id"]))

    planned_roads_by_district: dict[str, set[str]] = defaultdict(set)
    for row in planned:
        did = str(row.get("district_id") or "")
        rid = str(row.get("road_id") or "")
        if did and rid:
            planned_roads_by_district[did].add(rid)

    observed_roads_by_district: dict[str, set[str]] = defaultdict(set)
    observed_road_ids: set[str] = set()
    for row in observations:
        rid = str(row.get("road_id") or "")
        if not rid:
            continue
        observed_road_ids.add(rid)
        did = str(row.get("district_id") or "")
        if not did:
            try:
                lon = float(row.get("sample_lon"))
                lat = float(row.get("sample_lat"))
            except (TypeError, ValueError):
                lon = lat = None
            if lon is not None and lat is not None:
                district = geo_admin.district_for_point(lon, lat, districts)
                if district:
                    did = str(district["district_id"])
        if did:
            observed_roads_by_district[did].add(rid)

    district_rows = []
    for did in sorted(district_meta):
        eligible = candidate_roads_by_district.get(did, set())
        planned_set = planned_roads_by_district.get(did, set())
        observed_set = observed_roads_by_district.get(did, set())
        meta = district_meta[did]
        district_rows.append({
            "district_id": did,
            "district_name_th": meta.get("district_name_th") or did,
            "district_name_en": meta.get("district_name_en") or "",
            "eligible_road_count": len(eligible),
            "planned_road_count": len(planned_set),
            "observed_road_count": len(observed_set),
            "planned_coverage_ratio": pct(len(planned_set), len(eligible)),
            "observed_coverage_ratio": pct(len(observed_set), len(eligible)),
        })

    tier_rows = []
    for tier in ("STRATEGIC", "URBAN"):
        eligible = {rid for rid, row in catalog.items() if str(row.get("network_tier") or "URBAN") == tier}
        planned_ids = {str(x.get("road_id")) for x in planned if str(x.get("network_tier") or "URBAN") == tier}
        observed_ids = observed_road_ids & eligible
        tier_rows.append({
            "network_tier": tier,
            "eligible_road_count": len(eligible),
            "planned_road_count": len(planned_ids),
            "observed_road_count": len(observed_ids),
            "planned_coverage_ratio": pct(len(planned_ids), len(eligible)),
            "observed_coverage_ratio": pct(len(observed_ids), len(eligible)),
        })

    eligible_road_ids = set(catalog)
    planned_road_ids = {str(x.get("road_id")) for x in planned if x.get("road_id")}
    observed_road_ids &= eligible_road_ids
    access_state = (traffic_state or {}).get("access_state") or "NO_TRAFFIC_STATE"

    return {
        "schema": "bkk-mobility-traffic-coverage-v0.2",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "access_state": access_state,
        "coverage_basis": {
            "road": "Distinct named road with >=1 usable speed observation.",
            "district": "Distinct road sampled at a probe point physically inside the district.",
            "caveat": "Coverage is road-count/probe coverage, not lane-km, direction, or full road-length coverage.",
        },
        "plan": {key: plan.get(key) for key in (
            "schema", "rotation_slot", "request_budget", "budget_role",
            "strategic_target_share", "max_points_per_road", "rotation_policy",
            "planned_request_count", "planned_road_count", "planned_district_count",
        )},
        "summary": {
            "eligible_road_count": len(eligible_road_ids),
            "eligible_district_count": len(district_rows),
            "planned_road_count": len(planned_road_ids),
            "planned_district_count": len({str(x.get("district_id")) for x in planned if x.get("district_id")}),
            "observed_road_count": len(observed_road_ids),
            "observed_district_count": sum(1 for row in district_rows if row["observed_road_count"] > 0),
            "planned_road_coverage_ratio": pct(len(planned_road_ids), len(eligible_road_ids)),
            "observed_road_coverage_ratio": pct(len(observed_road_ids), len(eligible_road_ids)),
            "usable_observation_count": len(observations),
        },
        "tier_coverage": tier_rows,
        "district_coverage": district_rows,
        "planned_points": planned,
        "observed_road_ids": sorted(observed_road_ids),
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    network = load(args.network)
    config = load(args.config)
    rotation_slot = args.rotation_slot or dt.datetime.now(dt.timezone.utc).date().isoformat()

    if args.plan_output.exists() and args.request_budget is None and args.rotation_slot is None:
        plan = load(args.plan_output)
    else:
        plan = build_plan(network, config, rotation_slot, args.request_budget)
        write_json(args.plan_output, plan)

    if args.plan_only:
        if not args.plan_output.exists():
            write_json(args.plan_output, plan)
        print(json.dumps({
            "plan_output": str(args.plan_output),
            "rotation_slot": plan["rotation_slot"],
            "request_budget": plan["request_budget"],
            "planned_request_count": plan["planned_request_count"],
            "planned_road_count": plan["planned_road_count"],
            "planned_district_count": plan["planned_district_count"],
        }, ensure_ascii=False, indent=2))
        return 0

    traffic_state = load(args.traffic_state) if args.traffic_state.exists() else None
    result = build_coverage(network, config, plan, traffic_state)
    write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "access_state": result["access_state"], **result["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
