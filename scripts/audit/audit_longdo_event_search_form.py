#!/usr/bin/env python3
"""Inspect public Longdo event-search HTML + same-origin JavaScript contract.

Prints only form field metadata, script URLs and small code snippets around
search-related tokens. It does not submit a search.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import re
import urllib.parse
import urllib.request

URL = "https://traffic.longdo.com/en/event"
USER_AGENT = "bkk-mobility-intelligence-search-audit/0.2"
TOKENS = (
    "search-submit",
    "searchBtn",
    "event/form/page",
    "pagger",
    "eventtype",
    "reported",
    "startdate",
    "enddate",
    "datepicker",
    "$.ajax",
    "ajax(",
)


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self.current_form: dict | None = None
        self.current_select: dict | None = None
        self.script_srcs: list[str] = []
        self.in_script = False
        self.inline_script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "form":
            self.current_form = {
                "action": attrs.get("action"),
                "method": (attrs.get("method") or "get").lower(),
                "id": attrs.get("id"),
                "class": attrs.get("class"),
                "fields": [],
            }
            self.forms.append(self.current_form)
        elif self.current_form is not None and tag in {"input", "button"}:
            self.current_form["fields"].append({
                "tag": tag,
                "name": attrs.get("name"),
                "type": attrs.get("type"),
                "value": attrs.get("value"),
                "id": attrs.get("id"),
                "class": attrs.get("class"),
            })
        elif self.current_form is not None and tag == "select":
            self.current_select = {
                "tag": "select",
                "name": attrs.get("name"),
                "id": attrs.get("id"),
                "class": attrs.get("class"),
                "options": [],
            }
            self.current_form["fields"].append(self.current_select)
        elif self.current_select is not None and tag == "option":
            self.current_select["options"].append({
                "value": attrs.get("value"),
                "selected": "selected" in attrs,
            })

        if tag == "script":
            src = attrs.get("src")
            if src:
                self.script_srcs.append(src)
            else:
                self.in_script = True

    def handle_data(self, data: str) -> None:
        if self.in_script:
            self.inline_script_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.current_select = None
        elif tag == "form":
            self.current_form = None
            self.current_select = None
        elif tag == "script":
            self.in_script = False


def fetch_text(url: str, timeout: float = 30.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def snippets(text: str, tokens: tuple[str, ...] = TOKENS, radius: int = 500) -> list[dict]:
    out: list[dict] = []
    lower = text.casefold()
    for token in tokens:
        pos = lower.find(token.casefold())
        if pos < 0:
            continue
        start = max(0, pos - radius)
        end = min(len(text), pos + len(token) + radius)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        out.append({"token": token, "snippet": snippet})
    return out


def main() -> int:
    body = fetch_text(URL)
    parser = PageParser()
    parser.feed(body)

    script_audits: list[dict] = []
    for src in parser.script_srcs:
        absolute = urllib.parse.urljoin(URL, src)
        parsed = urllib.parse.urlparse(absolute)
        if parsed.hostname != "traffic.longdo.com":
            continue
        try:
            js = fetch_text(absolute)
        except Exception as exc:
            script_audits.append({
                "url": absolute,
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        hits = snippets(js)
        if hits:
            script_audits.append({
                "url": absolute,
                "hits": hits,
            })

    inline = "\n".join(parser.inline_script_parts)
    print(json.dumps({
        "requested_url": URL,
        "form_count": len(parser.forms),
        "forms": parser.forms,
        "script_src_count": len(parser.script_srcs),
        "script_srcs": parser.script_srcs,
        "inline_search_hits": snippets(inline),
        "same_origin_script_search_hits": script_audits,
        "html_search_hits": snippets(body),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
