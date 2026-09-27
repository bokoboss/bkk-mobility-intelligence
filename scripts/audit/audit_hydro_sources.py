#!/usr/bin/env python3
"""Audit public hydro source contracts for Flood Intelligence v0.2.

The audit is deliberately metadata-first: discover CKAN resource URLs, current
TMD precipitation products and machine-readable contracts without persisting
large source files.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "bkk-mobility-intelligence-hydro-audit/0.2"

CKAN_QUERIES = {
    "data_go_hii_rainfall": "https://data.go.th/api/3/action/package_show?id=hii-rainfall",
    "data_go_bma_radar": "https://data.go.th/api/3/action/package_show?id=69-05-disaster",
    "hii_spatial_rain": "https://datagov.hii.or.th/api/3/action/package_show?id=spatial-rain",
}

PAGE_SOURCES = {
    "hii_data_page": "https://data.hii.or.th/dataset/spatial-rain",
    "tmd_nwp": "https://hpc.tmd.go.th/download",
}

TOKENS = (
    "api", "json", "ajax", "station", "summary", "flood", "rain",
    "water", "latitude", "longitude", "lat", "lng", "prec1hr",
    "csv", "netcdf", "rainhistory", "download-files", "tiservice",
)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.options: list[dict[str, str | bool]] = []
        self.in_init_select = False
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))
        elif tag == "script" and attrs.get("src"):
            self.scripts.append(str(attrs["src"]))
        elif tag == "select" and attrs.get("id") == "download-init-time":
            self.in_init_select = True
        elif tag == "option" and self.in_init_select:
            value = str(attrs.get("value") or "").strip()
            if value:
                self.options.append({
                    "value": value,
                    "selected": "selected" in attrs,
                })
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.in_init_select = False
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())


def fetch(url: str, timeout: float = 35.0) -> tuple[bytes, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html,application/xhtml+xml,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        meta = {
            "status": getattr(resp, "status", None),
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type"),
            "content_length_read": len(body),
        }
    return body, meta


def text_body(body: bytes) -> str:
    return body.decode("utf-8", errors="replace")


def token_snippets(text: str, radius: int = 220) -> list[dict[str, str]]:
    compact = re.sub(r"\s+", " ", text)
    lower = compact.casefold()
    hits = []
    for token in TOKENS:
        pos = lower.find(token.casefold())
        if pos < 0:
            continue
        start = max(0, pos - radius)
        end = min(len(compact), pos + len(token) + radius)
        hits.append({"token": token, "snippet": compact[start:end]})
    return hits


def clean_resource(resource: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id", "name", "description", "format", "mimetype", "url",
        "url_type", "last_modified", "created", "resource_type",
    )
    out = {key: resource.get(key) for key in keys if key in resource}
    return out


def audit_ckan(name: str, url: str) -> dict[str, Any]:
    try:
        body, meta = fetch(url)
        payload = json.loads(text_body(body))
        result = payload.get("result") if isinstance(payload, dict) else None
        resources = result.get("resources") if isinstance(result, dict) else []
        return {
            "name": name,
            "requested_url": url,
            **meta,
            "success": payload.get("success") if isinstance(payload, dict) else None,
            "dataset_id": result.get("id") if isinstance(result, dict) else None,
            "dataset_name": result.get("name") if isinstance(result, dict) else None,
            "dataset_title": result.get("title") if isinstance(result, dict) else None,
            "license_title": result.get("license_title") if isinstance(result, dict) else None,
            "metadata_modified": result.get("metadata_modified") if isinstance(result, dict) else None,
            "resources": [
                clean_resource(x) for x in (resources or []) if isinstance(x, dict)
            ],
        }
    except Exception as exc:
        return {
            "name": name,
            "requested_url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def audit_page(name: str, url: str) -> dict[str, Any]:
    try:
        body, meta = fetch(url)
    except Exception as exc:
        return {
            "name": name,
            "requested_url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }
    text = text_body(body)
    parser = Parser()
    parser.feed(text)
    interesting = []
    for value in parser.links + parser.scripts:
        absolute = urllib.parse.urljoin(meta["final_url"], value)
        low = absolute.casefold()
        if any(token in low for token in ("api", "rain", "csv", "json", "download", "tiservice")):
            if absolute not in interesting:
                interesting.append(absolute)
    return {
        "name": name,
        "requested_url": url,
        **meta,
        "title": " ".join(x for x in parser.title_parts if x)[:300],
        "init_time_options": parser.options[:20],
        "interesting_urls": interesting[:80],
        "token_hits": token_snippets(text)[:30],
    }


def discover_tmd_precip() -> dict[str, Any]:
    page_url = PAGE_SOURCES["tmd_nwp"]
    try:
        body, meta = fetch(page_url)
        html = text_body(body)
        parser = Parser()
        parser.feed(html)
        values = [
            str(x.get("value") or "")
            for x in parser.options
            if re.fullmatch(r"\d{10}", str(x.get("value") or ""))
        ]
        init_time = max(values) if values else None
        if not init_time:
            matches = re.findall(r'<option[^>]+value=["\'](\d{10})["\']', html)
            init_time = max(matches) if matches else None
        if not init_time:
            return {"status": "NO_INIT_TIME", **meta}

        api = "https://hpc.tmd.go.th/api/download-files?" + urllib.parse.urlencode(
            {"init_time": init_time}
        )
        raw, api_meta = fetch(api)
        payload = json.loads(text_body(raw))
        files = payload.get("files") if isinstance(payload, dict) else []
        files = [x for x in (files or []) if isinstance(x, dict)]

        precip = []
        for item in files:
            hay = json.dumps(item, ensure_ascii=False).casefold()
            if "prec" in hay or "rain" in hay or "p24h" in hay:
                precip.append(item)

        compact = []
        for item in precip:
            compact.append({
                key: item.get(key)
                for key in (
                    "filename", "description", "domain", "domain_code",
                    "format", "size", "url"
                )
                if key in item
            })
        return {
            "status": "OK",
            "page_meta": meta,
            "api_meta": api_meta,
            "init_time": init_time,
            "file_count": len(files),
            "precip_files": compact,
        }
    except Exception as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def probe_resource_urls(ckan_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probes = []
    seen = set()
    for dataset in ckan_results:
        for resource in dataset.get("resources") or []:
            url = resource.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            low = url.casefold()
            if not any(token in low for token in ("hii", "rain", "tiservice", "json", "csv")):
                continue
            try:
                body, meta = fetch(url, timeout=20)
                sample = body[:500].decode("utf-8", errors="replace")
                probes.append({
                    "url": url,
                    **meta,
                    "sample_prefix": re.sub(r"\s+", " ", sample)[:500],
                })
            except Exception as exc:
                probes.append({
                    "url": url,
                    "error": f"{type(exc).__name__}: {exc}",
                })
            if len(probes) >= 20:
                return probes
    return probes


def main() -> int:
    ckan = [audit_ckan(name, url) for name, url in CKAN_QUERIES.items()]
    pages = [audit_page(name, url) for name, url in PAGE_SOURCES.items()]
    result = {
        "ckan": ckan,
        "pages": pages,
        "resource_probes": probe_resource_urls(ckan),
        "tmd_precip": discover_tmd_precip(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
