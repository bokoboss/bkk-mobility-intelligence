#!/usr/bin/env python3
"""Targeted source-schema audit for Flood Intelligence v0.2.

Discovers:
- HII hourly-rain station metadata and current-month file schema;
- TMD Domain-2 precipitation CSV schema without downloading the full grid.
"""

from __future__ import annotations

import csv
import datetime as dt
from html.parser import HTMLParser
import io
import json
import re
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "bkk-mobility-intelligence-hydro-audit/0.3"
HII_ROOT = "https://tiservice.hii.or.th/opendata/data_catalog/hourly_rain"
HII_META = HII_ROOT + "/0all_stn_metadata.csv"
TMD_PAGE = "https://hpc.tmd.go.th/download"
STUDY_BBOX = {
    "min_lon": 100.57,
    "min_lat": 13.755,
    "max_lon": 100.79,
    "max_lat": 13.93,
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.init_times: list[str] = []
        self.in_init_select = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))
        elif tag == "select" and attrs.get("id") == "download-init-time":
            self.in_init_select = True
        elif tag == "option" and self.in_init_select:
            value = str(attrs.get("value") or "").strip()
            if re.fullmatch(r"\d{10}", value):
                self.init_times.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.in_init_select = False


def request(url: str, timeout: float = 35.0, accept: str = "*/*"):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_bytes(url: str, timeout: float = 35.0) -> bytes:
    with request(url, timeout=timeout) as resp:
        return resp.read()


def decode_csv_bytes(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp874", "tis-620"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def detect_field(fieldnames: list[str], exact: tuple[str, ...], contains: tuple[str, ...]) -> str | None:
    lowered = {str(x).strip().casefold(): x for x in fieldnames}
    for name in exact:
        if name in lowered:
            return lowered[name]
    for field in fieldnames:
        low = str(field).strip().casefold()
        if any(token in low for token in contains):
            return field
    return None


def audit_hii_metadata() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = fetch_bytes(HII_META, timeout=35)
    text = decode_csv_bytes(raw)
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = [str(x or "").strip() for x in (reader.fieldnames or [])]

    lat_field = detect_field(
        fieldnames,
        ("latitude", "lat", "station_lat"),
        ("latitude", "_lat", " lat"),
    )
    lon_field = detect_field(
        fieldnames,
        ("longitude", "lon", "lng", "station_lon"),
        ("longitude", "_lon", "_lng", " lon", " lng"),
    )
    id_field = detect_field(
        fieldnames,
        ("station_code", "station_id", "tele_station_id", "id"),
        ("station_code", "station_id", "stationcode", "tele_station"),
    )
    name_field = detect_field(
        fieldnames,
        ("station_name", "name", "station_name_th"),
        ("station_name", "stationname"),
    )

    bbox_rows = []
    sample_rows = []
    row_count = 0
    for row in reader:
        row_count += 1
        compact = {
            k: row.get(k)
            for k in fieldnames[:30]
        }
        if len(sample_rows) < 3:
            sample_rows.append(compact)

        lat = to_float(row.get(lat_field)) if lat_field else None
        lon = to_float(row.get(lon_field)) if lon_field else None
        if lat is None or lon is None:
            continue
        if (
            STUDY_BBOX["min_lat"] <= lat <= STUDY_BBOX["max_lat"]
            and STUDY_BBOX["min_lon"] <= lon <= STUDY_BBOX["max_lon"]
        ):
            bbox_rows.append({
                "station_id": row.get(id_field) if id_field else None,
                "station_name": row.get(name_field) if name_field else None,
                "latitude": lat,
                "longitude": lon,
                "row": compact,
            })

    return (
        {
            "url": HII_META,
            "byte_count": len(raw),
            "fieldnames": fieldnames,
            "detected_fields": {
                "station_id": id_field,
                "station_name": name_field,
                "latitude": lat_field,
                "longitude": lon_field,
            },
            "row_count": row_count,
            "bbox_station_count": len(bbox_rows),
            "sample_rows": sample_rows,
        },
        bbox_rows[:30],
    )


def audit_hii_month(stations: list[dict[str, Any]]) -> dict[str, Any]:
    month = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).strftime("%Y%m")
    url = f"{HII_ROOT}/{month[:4]}/{month}/"
    html = fetch_bytes(url, timeout=30).decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    csv_links = [
        x for x in parser.links
        if x.casefold().endswith(".csv") and not x.startswith("?")
    ]

    station_ids = [
        str(x.get("station_id") or "").strip()
        for x in stations
        if str(x.get("station_id") or "").strip()
    ]
    matched = []
    for href in csv_links:
        stem = href.rsplit("/", 1)[-1].removesuffix(".csv")
        for station_id in station_ids:
            if station_id == stem or station_id in stem or stem in station_id:
                matched.append({
                    "href": href,
                    "station_id": station_id,
                })
                break

    chosen = matched[0]["href"] if matched else (csv_links[0] if csv_links else None)
    sample = None
    if chosen:
        file_url = urllib.parse.urljoin(url, chosen)
        raw = fetch_bytes(file_url, timeout=30)
        text = decode_csv_bytes(raw)
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        sample = {
            "url": file_url,
            "byte_count": len(raw),
            "fieldnames": [str(x or "").strip() for x in (reader.fieldnames or [])],
            "row_count": len(rows),
            "first_rows": rows[:3],
            "last_rows": rows[-3:],
        }

    return {
        "url": url,
        "csv_file_count": len(csv_links),
        "first_csv_files": csv_links[:30],
        "matched_study_station_files": matched[:30],
        "sample_station_file": sample,
    }


def tmd_file_list() -> tuple[str, list[dict[str, Any]]]:
    html = fetch_bytes(TMD_PAGE, timeout=30).decode("utf-8", errors="replace")
    parser = LinkParser()
    parser.feed(html)
    if not parser.init_times:
        raise RuntimeError("TMD init time not found")
    init_time = max(parser.init_times)
    api = (
        "https://hpc.tmd.go.th/api/download-files?"
        + urllib.parse.urlencode({"init_time": init_time})
    )
    payload = json.loads(fetch_bytes(api, timeout=30).decode("utf-8"))
    files = payload.get("files") if isinstance(payload, dict) else []
    return init_time, [x for x in (files or []) if isinstance(x, dict)]


def stream_csv_sample(url: str, rows: int = 4) -> dict[str, Any]:
    with request(url, timeout=35, accept="text/csv,*/*") as resp:
        wrapped = io.TextIOWrapper(resp, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.reader(wrapped)
        out = []
        for _ in range(rows):
            try:
                out.append(next(reader))
            except StopIteration:
                break
        return {
            "url": url,
            "content_type": resp.headers.get("Content-Type"),
            "content_length": resp.headers.get("Content-Length"),
            "rows": out,
        }


def audit_tmd_csv() -> dict[str, Any]:
    init_time, files = tmd_file_list()
    wanted = {}
    for item in files:
        filename = str(item.get("filename") or "")
        if filename.startswith("p1h.d02.") and filename.endswith(".csv"):
            wanted["p1h_d02"] = item
        if filename.startswith("p24h.d02.") and filename.endswith(".csv"):
            wanted["p24h_d02"] = item

    samples = {}
    for key, item in wanted.items():
        path = str(item.get("url") or "")
        url = urllib.parse.urljoin("https://hpc.tmd.go.th", path)
        samples[key] = {
            "metadata": {
                k: item.get(k)
                for k in ("filename", "description", "domain", "format", "size", "url")
            },
            "sample": stream_csv_sample(url),
        }

    return {
        "init_time": init_time,
        "samples": samples,
    }


def main() -> int:
    result: dict[str, Any] = {}
    try:
        meta, stations = audit_hii_metadata()
        result["hii_metadata"] = meta
        result["hii_study_stations"] = stations
        result["hii_current_month"] = audit_hii_month(stations)
    except Exception as exc:
        result["hii_error"] = f"{type(exc).__name__}: {exc}"

    try:
        result["tmd_csv"] = audit_tmd_csv()
    except Exception as exc:
        result["tmd_error"] = f"{type(exc).__name__}: {exc}"

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
