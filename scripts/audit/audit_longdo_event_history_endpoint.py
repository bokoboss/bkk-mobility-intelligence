#!/usr/bin/env python3
"""Safely inspect the documented current-year Longdo event-history endpoint.

The script requests only an initial byte range and caps the bytes read even if
the origin ignores Range. It is an endpoint/schema qualification tool, not a
full-year downloader.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import urllib.request
import zipfile

DEFAULT_URL = "https://event.longdo.com/feed/2026"
USER_AGENT = "bkk-mobility-intelligence-phase0/0.8"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--max-bytes", type=int, default=65536)
    p.add_argument("--timeout", type=float, default=30.0)
    return p.parse_args()


def detect_format(body: bytes, content_type: str | None) -> str:
    stripped = body.lstrip()
    ctype = (content_type or "").lower()
    if body.startswith(b"PK\x03\x04"):
        return "zip"
    if body.startswith(b"\x1f\x8b"):
        return "gzip"
    if stripped.startswith((b"{", b"[")) or "json" in ctype:
        return "json"
    if stripped.startswith(b"<") or "xml" in ctype:
        return "xml"
    if "csv" in ctype:
        return "csv"
    text = body[:4096].decode("utf-8-sig", errors="replace")
    if re.search(r"^[^\n,]+,[^\n,]+", text):
        return "csv_or_delimited_text"
    return "binary_or_text"


def preview_payload(body: bytes, fmt: str) -> dict:
    result: dict = {}
    if fmt == "json":
        try:
            parsed = json.loads(body.decode("utf-8-sig"))
            result["json_type"] = type(parsed).__name__
            if isinstance(parsed, list):
                result["sample_count_in_prefix"] = len(parsed)
                if parsed and isinstance(parsed[0], dict):
                    result["first_record_keys"] = sorted(parsed[0].keys())
                    result["first_record"] = parsed[0]
            elif isinstance(parsed, dict):
                result["top_level_keys"] = sorted(parsed.keys())
        except Exception as exc:
            result["partial_json_parse_error"] = f"{type(exc).__name__}: {exc}"
    elif fmt in {"csv", "csv_or_delimited_text", "xml", "binary_or_text"}:
        text = body.decode("utf-8-sig", errors="replace")
        result["text_preview"] = text[:2000]
        result["line_preview"] = text.splitlines()[:12]
    elif fmt == "gzip":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as gz:
                sample = gz.read(8192).decode("utf-8-sig", errors="replace")
            result["decompressed_preview"] = sample[:2000]
        except Exception as exc:
            result["partial_gzip_error"] = f"{type(exc).__name__}: {exc}"
    elif fmt == "zip":
        try:
            with zipfile.ZipFile(io.BytesIO(body)) as zf:
                result["zip_names"] = zf.namelist()[:30]
        except Exception as exc:
            result["partial_zip_error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    args = parse_args()
    req = urllib.request.Request(
        args.url,
        headers={
            "User-Agent": USER_AGENT,
            "Range": f"bytes=0-{args.max_bytes - 1}",
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(req, timeout=args.timeout) as resp:
        body = resp.read(args.max_bytes)
        headers = {
            "status": getattr(resp, "status", None),
            "final_url": resp.geturl(),
            "content_type": resp.headers.get("Content-Type"),
            "content_length": resp.headers.get("Content-Length"),
            "content_range": resp.headers.get("Content-Range"),
            "content_disposition": resp.headers.get("Content-Disposition"),
            "last_modified": resp.headers.get("Last-Modified"),
        }

    fmt = detect_format(body, headers["content_type"])
    report = {
        "requested_url": args.url,
        "bytes_read": len(body),
        "format_guess": fmt,
        "response": headers,
        "preview": preview_payload(body, fmt),
        "safety_note": (
            "Only an initial capped prefix was read; row counts/file size are not "
            "inferred unless the server supplied headers."
        ),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
