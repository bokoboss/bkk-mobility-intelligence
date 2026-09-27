#!/usr/bin/env python3
"""Fetch and audit the latest iTIC/Longdo incident + free traffic feeds.

This is a latest-first Phase 0 ingestion tool. It stores raw responses locally,
creates a filtered incident snapshot for the configured study area, and writes
one manifest containing retrieval/freshness metadata.

It deliberately does not commit or publish fetched live data. Source terms for
live endpoints must remain separate from the CC BY 4.0 historical archives.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Iterable

EVENTS_URL = "https://event.longdo.com/feed/json"
TRAFFIC_URL = "https://traffic.longdo.com/api/feed/free"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.2"


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument("--output-dir", type=Path, default=Path("data/raw/current"))
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--events-url", default=EVENTS_URL)
    p.add_argument("--traffic-url", default=TRAFFIC_URL)
    return p.parse_args()


def fetch(url: str, timeout: float) -> dict[str, Any]:
    started = utc_now()
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            ended = utc_now()
            return {
                "ok": True,
                "requested_url": url,
                "final_url": response.geturl(),
                "http_status": getattr(response, "status", None),
                "content_type": response.headers.get("Content-Type"),
                "date_header": response.headers.get("Date"),
                "last_modified": response.headers.get("Last-Modified"),
                "retrieved_at_utc": ended.isoformat(),
                "elapsed_seconds": round((ended - started).total_seconds(), 3),
                "byte_count": len(body),
                "sha256": sha256(body),
                "body": body,
            }
    except urllib.error.HTTPError as exc:
        ended = utc_now()
        try:
            error_body = exc.read()
        except Exception:
            error_body = b""
        return {
            "ok": False,
            "requested_url": url,
            "final_url": exc.geturl(),
            "http_status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "date_header": exc.headers.get("Date") if exc.headers else None,
            "last_modified": exc.headers.get("Last-Modified") if exc.headers else None,
            "retrieved_at_utc": ended.isoformat(),
            "elapsed_seconds": round((ended - started).total_seconds(), 3),
            "byte_count": len(error_body),
            "sha256": sha256(error_body) if error_body else None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "body": error_body or None,
        }
    except Exception as exc:
        ended = utc_now()
        return {
            "ok": False,
            "requested_url": url,
            "final_url": None,
            "http_status": getattr(exc, "code", None),
            "content_type": None,
            "date_header": None,
            "last_modified": None,
            "retrieved_at_utc": ended.isoformat(),
            "elapsed_seconds": round((ended - started).total_seconds(), 3),
            "byte_count": 0,
            "sha256": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "body": None,
        }


def text_blob(record: Any) -> str:
    if isinstance(record, dict):
        return " ".join(text_blob(v) for v in record.values())
    if isinstance(record, list):
        return " ".join(text_blob(v) for v in record)
    return "" if record is None else str(record)


def detect_road_matches_in_text(text: str, config: dict[str, Any]) -> list[str]:
    hay = (text or "").casefold()
    out: list[str] = []
    for road in config.get("roads", []):
        if any(alias.casefold() in hay for alias in road.get("aliases", [])):
            out.append(road["id"])
    return out


def event_road_text_evidence(
    row: dict[str, Any], config: dict[str, Any]
) -> dict[str, list[str]]:
    title = " ".join(str(row.get(k) or "") for k in ("title", "title_en"))
    description = " ".join(
        str(row.get(k) or "") for k in ("description", "description_en")
    )
    return {
        "title_matches": detect_road_matches_in_text(title, config),
        "description_matches": detect_road_matches_in_text(description, config),
    }


def detect_road_matches(record: Any, config: dict[str, Any]) -> list[str]:
    """Generic text match for non-event payloads only.

    Event records use event_road_text_evidence() so provider/agency mentions in
    descriptions cannot be mistaken for strong road attribution.
    """
    return detect_road_matches_in_text(text_blob(record), config)


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_lat_lon(record: dict[str, Any]) -> tuple[float | None, float | None]:
    lat_keys = ("latitude", "lat", "y")
    lon_keys = ("longitude", "lon", "lng", "long", "x")
    lower = {str(k).lower(): v for k, v in record.items()}
    lat = next((to_float(lower[k]) for k in lat_keys if k in lower), None)
    lon = next((to_float(lower[k]) for k in lon_keys if k in lower), None)
    return lat, lon


def in_bbox(lat: float | None, lon: float | None, config: dict[str, Any]) -> bool:
    if lat is None or lon is None:
        return False
    b = config["bbox_wgs84"]
    return b["min_lat"] <= lat <= b["max_lat"] and b["min_lon"] <= lon <= b["max_lon"]


def parse_local_timestamp(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(value, fmt).replace(
                tzinfo=dt.timezone(dt.timedelta(hours=7))
            )
        except ValueError:
            pass
    return None


def audit_events(
    body: bytes, config: dict[str, Any], retrieved_at: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parsed = json.loads(body.decode("utf-8-sig"))
    if not isinstance(parsed, list) or any(not isinstance(x, dict) for x in parsed):
        raise ValueError("Expected event feed to be a JSON array of objects")

    retrieved = dt.datetime.fromisoformat(retrieved_at)
    latest_event_time: dt.datetime | None = None
    area_events: list[dict[str, Any]] = []
    invalid_coords = 0
    eids: list[str] = []

    for row in parsed:
        if row.get("eid") is not None:
            eids.append(str(row["eid"]))
        lat, lon = extract_lat_lon(row)
        if lat is None or lon is None:
            invalid_coords += 1
        t = parse_local_timestamp(str(row.get("start") or ""))
        if t and (latest_event_time is None or t > latest_event_time):
            latest_event_time = t
        if in_bbox(lat, lon, config):
            enriched = dict(row)
            enriched["study_area_match"] = True
            evidence = event_road_text_evidence(row, config)
            enriched["road_title_matches"] = evidence["title_matches"]
            enriched["road_description_matches"] = evidence["description_matches"]
            enriched["road_match_confidence"] = (
                "TITLE_STRONG"
                if evidence["title_matches"]
                else "DESCRIPTION_CONTEXT"
                if evidence["description_matches"]
                else "UNMATCHED"
            )
            area_events.append(enriched)

    event_age_hours = None
    if latest_event_time:
        event_age_hours = round(
            (retrieved - latest_event_time.astimezone(dt.timezone.utc)).total_seconds()
            / 3600,
            2,
        )

    return {
        "format": "json",
        "record_count": len(parsed),
        "unique_eid_count": len(set(eids)),
        "duplicate_eid_count": len(eids) - len(set(eids)),
        "invalid_or_missing_coordinates": invalid_coords,
        "study_area_event_count": len(area_events),
        "latest_event_start": latest_event_time.isoformat() if latest_event_time else None,
        "latest_event_start_age_hours_at_retrieval": event_age_hours,
        "freshness_note": (
            "Latest event age is diagnostic only; no recent event does not by itself "
            "prove the feed is stale."
        ),
    }, area_events


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1].lower()


def xml_leaf_map(element: ET.Element) -> dict[str, str]:
    flat: dict[str, str] = {}
    for node in element.iter():
        if list(node):
            continue
        text = (node.text or "").strip()
        if text:
            flat[strip_ns(node.tag)] = text
        for k, v in node.attrib.items():
            flat[f"@{k.lower()}"] = v
    return flat


def candidate_xml_records(root: ET.Element) -> Iterable[dict[str, str]]:
    children = list(root)
    if children:
        for child in children:
            yield xml_leaf_map(child)
        return
    yield xml_leaf_map(root)


def recursive_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from recursive_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from recursive_dicts(child)


def audit_traffic(
    body: bytes, content_type: str | None, config: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    stripped = body.lstrip()
    records: list[dict[str, Any]] = []
    fmt = "unknown"
    parse_error = None
    tag_counts: dict[str, int] = {}

    try:
        if stripped.startswith((b"{", b"[")):
            fmt = "json"
            parsed = json.loads(body.decode("utf-8-sig"))
            records = list(recursive_dicts(parsed))
        elif stripped.startswith(b"<"):
            fmt = "xml"
            root = ET.fromstring(body)
            for node in root.iter():
                key = strip_ns(node.tag)
                tag_counts[key] = tag_counts.get(key, 0) + 1
            records = [dict(x) for x in candidate_xml_records(root)]
        else:
            fmt = "text"
    except Exception as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    coordinate_candidates = 0
    area_coordinate_matches = 0
    area_name_matches = 0
    area_records: list[dict[str, Any]] = []
    for row in records:
        lat, lon = extract_lat_lon(row)
        road_matches = detect_road_matches(row, config)
        coordinate_match = False
        if lat is not None and lon is not None:
            coordinate_candidates += 1
            coordinate_match = in_bbox(lat, lon, config)
            if coordinate_match:
                area_coordinate_matches += 1
        if road_matches:
            area_name_matches += 1
        if coordinate_match or road_matches:
            enriched = dict(row)
            enriched["road_text_matches"] = road_matches
            enriched["study_area_match_method"] = (
                "coordinate+road_name"
                if coordinate_match and road_matches
                else "coordinate"
                if coordinate_match
                else "road_name"
            )
            area_records.append(enriched)

    status_like_keys = sorted(
        {
            k
            for row in records
            for k in row
            if any(
                token in k.lower()
                for token in (
                    "status",
                    "speed",
                    "link",
                    "road",
                    "name",
                    "direction",
                    "offset",
                    "time",
                    "date",
                )
            )
        }
    )[:100]
    return {
        "format": fmt,
        "content_type": content_type,
        "parse_error": parse_error,
        "candidate_record_count": len(records),
        "coordinate_candidate_count": coordinate_candidates,
        "study_area_coordinate_match_count": area_coordinate_matches,
        "study_area_road_name_match_count": area_name_matches,
        "study_area_record_count": len(area_records),
        "status_like_keys": status_like_keys,
        "top_xml_tags": sorted(
            tag_counts.items(), key=lambda x: (-x[1], x[0])
        )[:40],
        "area_filter_note": (
            "Traffic feed area extraction is opportunistic until the live payload "
            "schema/link geometry is validated. Zero matches must not be interpreted "
            "as zero traffic data in the area."
        ),
    }, area_records


def freshness_class(
    source: str, result: dict[str, Any], audit: dict[str, Any] | None
) -> str:
    if not result["ok"]:
        return "UNAVAILABLE"
    if source == "events":
        return "LIVE"
    if source == "traffic":
        return "LIVE" if audit and not audit.get("parse_error") else "UNKNOWN"
    return "UNKNOWN"


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def sanitized_result(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "body"}


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    run_time = utc_now()
    run_id = run_time.strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    events = fetch(args.events_url, args.timeout)
    traffic = fetch(args.traffic_url, args.timeout)

    manifest: dict[str, Any] = {
        "pipeline": "current-source-bundle-v1",
        "study_area_id": config["id"],
        "run_id": run_id,
        "run_started_at_utc": run_time.isoformat(),
        "sources": {},
    }

    event_audit = None
    if events["ok"]:
        write_bytes(run_dir / "events.raw.json", events["body"])
        try:
            event_audit, area_events = audit_events(
                events["body"], config, events["retrieved_at_utc"]
            )
            write_json(run_dir / "events.study_area.json", area_events)
        except Exception as exc:
            event_audit = {"parse_error": f"{type(exc).__name__}: {exc}"}
    manifest["sources"]["events"] = {
        **sanitized_result(events),
        "provider": (
            "Intelligent Traffic Information Center Foundation (iTIC Foundation) "
            "/ Longdo Traffic"
        ),
        "freshness_class": freshness_class("events", events, event_audit),
        "audit": event_audit,
    }

    traffic_audit = None
    if traffic["ok"]:
        suffix = (
            ".xml"
            if (traffic["body"] or b"").lstrip().startswith(b"<")
            else ".bin"
        )
        write_bytes(run_dir / f"traffic_free.raw{suffix}", traffic["body"])
        try:
            traffic_audit, area_traffic = audit_traffic(
                traffic["body"], traffic.get("content_type"), config
            )
            write_json(run_dir / "traffic_free.study_area.json", area_traffic)
        except Exception as exc:
            traffic_audit = {"parse_error": f"{type(exc).__name__}: {exc}"}
    manifest["sources"]["traffic_free"] = {
        **sanitized_result(traffic),
        "provider": (
            "Intelligent Traffic Information Center Foundation (iTIC Foundation) "
            "/ Longdo Traffic"
        ),
        "freshness_class": freshness_class("traffic", traffic, traffic_audit),
        "audit": traffic_audit,
        "official_feed_description": (
            "Free-Longdo: mobile probes from Longdo and iTIC applications; "
            "offset in meters."
        ),
    }

    manifest["pipeline_status"] = (
        "OK"
        if events["ok"] and traffic["ok"]
        else "PARTIAL"
        if events["ok"] or traffic["ok"]
        else "FAILED"
    )
    manifest["freshness_policy"] = {
        "principle": (
            "Successful retrieval and source freshness are separate concepts."
        ),
        "event_recency_warning": (
            "The newest event timestamp is not by itself a freshness SLA."
        ),
        "traffic_schema_warning": (
            "Area filtering remains provisional until link geometry/schema is "
            "verified from a real payload."
        ),
    }
    write_json(run_dir / "manifest.json", manifest)

    write_json(
        args.output_dir / "latest.json",
        {
            "run_id": run_id,
            "manifest": str((run_dir / "manifest.json").as_posix()),
            "pipeline_status": manifest["pipeline_status"],
        },
    )

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "pipeline_status": manifest["pipeline_status"],
                "events": manifest["sources"]["events"]["freshness_class"],
                "traffic_free": manifest["sources"]["traffic_free"][
                    "freshness_class"
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if manifest["pipeline_status"] != "FAILED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
