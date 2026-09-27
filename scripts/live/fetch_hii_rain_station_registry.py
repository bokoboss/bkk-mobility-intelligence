#!/usr/bin/env python3
"""Build the HII rain/water station registry for the pilot envelope.

This adapter validates station metadata and the current-month static archive.
It never substitutes historical files for missing current observations.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
from typing import Any

ROOT = "https://tiservice.hii.or.th/opendata/data_catalog/hourly_rain"
META_URL = ROOT + "/0all_stn_metadata.csv"
USER_AGENT = "bkk-mobility-intelligence-hii-registry/0.1"
ICT = dt.timezone(dt.timedelta(hours=7))


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, default=Path("config/study_area.json"))
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/flood/hii_station_registry.json"),
    )
    p.add_argument("--timeout", type=float, default=35.0)
    return p.parse_args()


def fetch(url: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def decode(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp874", "tis-620"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def classify_station(value: Any) -> str:
    text = str(value or "").strip()
    if "น้ำฝน" in text:
        return "RAIN"
    if "ระดับน้ำ" in text:
        return "WATER_LEVEL"
    return "OTHER"


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    bbox = config["bbox_wgs84"]

    stations: list[dict[str, Any]] = []
    error = None
    try:
        raw = fetch(META_URL, args.timeout)
        reader = csv.DictReader(io.StringIO(decode(raw)))
        for row in reader:
            lat = to_float(row.get("Latitude"))
            lon = to_float(row.get("Longitude"))
            if lat is None or lon is None:
                continue
            if not (
                float(bbox["min_lat"]) <= lat <= float(bbox["max_lat"])
                and float(bbox["min_lon"]) <= lon <= float(bbox["max_lon"])
            ):
                continue
            stations.append(
                {
                    "station_code": str(row.get("Station_Code") or "").strip(),
                    "station_name": str(row.get("Station_Name") or "").strip(),
                    "latitude": lat,
                    "longitude": lon,
                    "station_type": str(row.get("Station_Type_Name") or "").strip(),
                    "station_class": classify_station(row.get("Station_Type_Name")),
                    "province": str(row.get("Province_Name") or "").strip(),
                    "district": str(row.get("Amphoe_Name") or "").strip(),
                    "shared_data": str(row.get("Shared_data") or "").strip(),
                }
            )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    now = dt.datetime.now(ICT)
    month = now.strftime("%Y%m")
    month_url = f"{ROOT}/{month[:4]}/{month}/"
    month_files: list[str] = []
    month_error = None
    try:
        html = decode(fetch(month_url, args.timeout))
        parser = LinkParser()
        parser.feed(html)
        month_files = sorted(
            {
                urllib.parse.urljoin(month_url, href)
                for href in parser.links
                if href.casefold().endswith(".csv")
            }
        )
    except Exception as exc:
        month_error = f"{type(exc).__name__}: {exc}"

    rain = [x for x in stations if x["station_class"] == "RAIN"]
    water = [x for x in stations if x["station_class"] == "WATER_LEVEL"]
    current_status = (
        "CURRENT_MONTH_ARCHIVE_AVAILABLE"
        if month_files
        else "ARCHIVE_MONTH_NOT_PUBLISHED"
    )
    if error:
        current_status = "METADATA_UNAVAILABLE"

    result = {
        "schema": "hii-station-registry-v0.1",
        "provider": "Hydro-Informatics Institute (HII)",
        "study_area_id": config.get("id"),
        "metadata_url": META_URL,
        "current_month_url": month_url,
        "status": current_status,
        "metadata_error": error,
        "current_month_error": month_error,
        "station_count": len(stations),
        "rain_station_count": len(rain),
        "water_level_station_count": len(water),
        "stations": stations,
        "rain_stations": rain,
        "water_level_stations": water,
        "current_month_csv_count": len(month_files),
        "current_month_files": month_files[:30],
        "current_observation_available": bool(month_files),
        "license_note": (
            "HII rainfall catalog states Creative Commons Attribution "
            "Non-Commercial; verify reuse conditions before commercial deployment."
        ),
        "interpretation": (
            "Station registry is valid metadata. No current rainfall value is "
            "reported when the current-month archive has no CSV files."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "station_count": len(stations),
                "rain_stations": rain,
                "water_level_station_count": len(water),
                "current_month_csv_count": len(month_files),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
