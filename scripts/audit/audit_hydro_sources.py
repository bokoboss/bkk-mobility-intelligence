#!/usr/bin/env python3
"""Audit public BMA/TMD hydro source contracts without persisting raw pages."""

from __future__ import annotations

from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "bkk-mobility-intelligence-hydro-audit/0.1"
SOURCES = {
    "bma_rain": "https://weather.bangkok.go.th/rain",
    "bma_flood": "https://weather.bangkok.go.th/flood/SummaryStation/IndexSummaryStation",
    "bma_water": "https://weather.bangkok.go.th/water",
    "tmd_nwp": "https://hpc.tmd.go.th/download",
}
TOKENS = (
    "api", "json", "ajax", "station", "summary", "flood", "rain",
    "water", "latitude", "longitude", "lat", "lng", "prec1hr",
    "csv", "netcdf", "rainhistory",
)


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.forms: list[dict[str, Any]] = []
        self.current_form: dict[str, Any] | None = None
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "a" and attrs.get("href"):
            self.links.append(str(attrs["href"]))
        elif tag == "script" and attrs.get("src"):
            self.scripts.append(str(attrs["src"]))
        elif tag == "form":
            self.current_form = {
                "action": attrs.get("action"),
                "method": (attrs.get("method") or "get").lower(),
                "id": attrs.get("id"),
                "fields": [],
            }
            self.forms.append(self.current_form)
        elif self.current_form is not None and tag in {"input", "select", "button"}:
            self.current_form["fields"].append({
                "tag": tag,
                "name": attrs.get("name"),
                "id": attrs.get("id"),
                "type": attrs.get("type"),
            })
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.current_form = None
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())


def fetch(url: str, timeout: float = 35.0) -> tuple[str, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        meta = {
            "status": getattr(resp, "status", None),
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type"),
            "content_length_read": len(body.encode("utf-8", errors="ignore")),
        }
    return body, meta


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


def interesting_urls(base: str, values: list[str]) -> list[str]:
    out = []
    for value in values:
        absolute = urllib.parse.urljoin(base, value)
        lowered = absolute.casefold()
        if any(token in lowered for token in ("api", "json", "csv", "station", "summary", "rain", "flood", "water", "prec", "download")):
            if absolute not in out:
                out.append(absolute)
    return out[:80]


def audit_source(name: str, url: str) -> dict[str, Any]:
    try:
        body, meta = fetch(url)
    except Exception as exc:
        return {
            "name": name,
            "requested_url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }

    stripped = body.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                sample = next(iter(payload.values()), None)
                return {
                    "name": name,
                    "requested_url": url,
                    **meta,
                    "payload_type": "json_object",
                    "top_level_keys": sorted(payload.keys())[:80],
                    "sample_value_type": type(sample).__name__,
                }
            return {
                "name": name,
                "requested_url": url,
                **meta,
                "payload_type": "json_array",
                "item_count": len(payload),
                "first_item_keys": sorted(payload[0].keys()) if payload and isinstance(payload[0], dict) else [],
            }
        except json.JSONDecodeError:
            pass

    parser = Parser()
    parser.feed(body)
    same_host = urllib.parse.urlparse(meta["final_url"]).hostname
    script_audits = []
    for src in parser.scripts:
        absolute = urllib.parse.urljoin(meta["final_url"], src)
        if urllib.parse.urlparse(absolute).hostname != same_host:
            continue
        try:
            js, _ = fetch(absolute, timeout=20)
        except Exception:
            continue
        hits = token_snippets(js)
        if hits:
            script_audits.append({"url": absolute, "hits": hits[:20]})
        if len(script_audits) >= 12:
            break

    return {
        "name": name,
        "requested_url": url,
        **meta,
        "title": " ".join(x for x in parser.title_parts if x)[:300],
        "forms": parser.forms[:10],
        "interesting_links": interesting_urls(meta["final_url"], parser.links),
        "interesting_scripts": interesting_urls(meta["final_url"], parser.scripts),
        "html_token_hits": token_snippets(body)[:30],
        "same_origin_script_hits": script_audits,
    }


def main() -> int:
    results = [audit_source(name, url) for name, url in SOURCES.items()]
    print(json.dumps({"sources": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
