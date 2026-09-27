#!/usr/bin/env python3
"""Fetch machine-readable TMD NWP precipitation dataset metadata.

This intentionally stops at dataset metadata for v0.1. It does not interpret
forecast grid values as observed rainfall.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://hpc.tmd.go.th"
DOWNLOAD_PAGE = BASE + "/download"
USER_AGENT = "bkk-mobility-intelligence-tmd/0.1"


class InitTimeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_select = False
        self.options: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "select" and attrs.get("id") == "download-init-time":
            self.in_select = True
        elif tag == "option" and self.in_select:
            value = str(attrs.get("value") or "").strip()
            if re.fullmatch(r"\d{10}", value):
                self.options.append(
                    {
                        "value": value,
                        "selected": "selected" in attrs,
                    }
                )

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.in_select = False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--page", default=DOWNLOAD_PAGE)
    p.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/current_context/tmd_precip_context.json"),
    )
    p.add_argument("--timeout", type=float, default=30.0)
    return p.parse_args()


def fetch_text(url: str, timeout: float) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def choose_init_time(html: str) -> str | None:
    parser = InitTimeParser()
    parser.feed(html)
    selected = [x["value"] for x in parser.options if x["selected"]]
    if selected:
        return max(selected)
    values = [x["value"] for x in parser.options]
    if values:
        return max(values)

    # Defensive fallback for server-rendered option markup.
    candidates = re.findall(r'<option[^>]+value=["\'](\d{10})["\']', html)
    return max(candidates) if candidates else None


def scalar_metadata(item: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
    return result


def choose_precip_file(files: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = []
    for item in files:
        hay = json.dumps(item, ensure_ascii=False).casefold()
        score = 0
        if "prec1hr" in hay:
            score += 100
        elif "prec" in hay:
            score += 40
        if "d02" in hay or "domain 2" in hay or "3km" in hay:
            score += 20
        if "csv" in hay:
            score += 10
        if score:
            ranked.append((score, item))
    ranked.sort(key=lambda x: -x[0])
    return ranked[0][1] if ranked else None


def infer_download_url(init_time: str, item: dict[str, Any]) -> str | None:
    for key in ("download_url", "url", "href", "path"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return urllib.parse.urljoin(BASE, value.strip())
    for key in ("filename", "file_name", "name"):
        value = item.get(key)
        if isinstance(value, str) and value.casefold().endswith(".csv"):
            return f"{BASE}/static/csv/{init_time}/{value}"
    return None


def main() -> int:
    args = parse_args()
    result: dict[str, Any] = {
        "provider": "Thai Meteorological Department NWP",
        "page_url": args.page,
        "api_contract": "/api/download-files?init_time=<YYYYMMDDHH>",
        "status": "UNAVAILABLE",
        "use": "forecast precipitation dataset metadata only",
        "not_observed_rainfall": True,
    }

    try:
        html = fetch_text(args.page, args.timeout)
        init_time = choose_init_time(html)
        if not init_time:
            result["status"] = "NO_INITIAL_TIME_DISCOVERED"
        else:
            api_url = (
                BASE
                + "/api/download-files?"
                + urllib.parse.urlencode({"init_time": init_time})
            )
            payload = json.loads(fetch_text(api_url, args.timeout))
            files = payload.get("files") if isinstance(payload, dict) else None
            files = files if isinstance(files, list) else []
            candidate = choose_precip_file(
                [x for x in files if isinstance(x, dict)]
            )
            result.update(
                {
                    "initial_time": payload.get("initial_time", init_time)
                    if isinstance(payload, dict)
                    else init_time,
                    "api_status": payload.get("status")
                    if isinstance(payload, dict)
                    else None,
                    "file_count": len(files),
                }
            )
            if candidate:
                result["status"] = "READY_METADATA"
                result["precip_candidate"] = scalar_metadata(candidate)
                result["download_url"] = infer_download_url(init_time, candidate)
            else:
                result["status"] = "NO_PRECIP_DATASET_DISCOVERED"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # Context enrichment is optional; do not block the main live dashboard.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
