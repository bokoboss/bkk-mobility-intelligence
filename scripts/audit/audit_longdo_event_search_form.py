#!/usr/bin/env python3
"""Inspect the public Longdo event-search HTML form contract.

Prints form actions, methods, field names/types and select option values only.
It does not submit searches or retain page content.
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import urllib.request

URL = "https://traffic.longdo.com/en/event"
USER_AGENT = "bkk-mobility-intelligence-search-audit/0.1"


class FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[dict] = []
        self.current: dict | None = None
        self.current_select: dict | None = None

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]) -> None:
        attrs = {k: v for k, v in attrs_list}
        if tag == "form":
            self.current = {
                "action": attrs.get("action"),
                "method": (attrs.get("method") or "get").lower(),
                "id": attrs.get("id"),
                "class": attrs.get("class"),
                "fields": [],
            }
            self.forms.append(self.current)
        elif self.current is not None and tag in {"input", "button"}:
            name = attrs.get("name")
            if name or tag == "button":
                self.current["fields"].append({
                    "tag": tag,
                    "name": name,
                    "type": attrs.get("type"),
                    "value": attrs.get("value"),
                    "id": attrs.get("id"),
                })
        elif self.current is not None and tag == "select":
            self.current_select = {
                "tag": "select",
                "name": attrs.get("name"),
                "id": attrs.get("id"),
                "options": [],
            }
            self.current["fields"].append(self.current_select)
        elif self.current_select is not None and tag == "option":
            self.current_select["options"].append({
                "value": attrs.get("value"),
                "selected": "selected" in attrs,
            })

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self.current_select = None
        elif tag == "form":
            self.current = None
            self.current_select = None


def main() -> int:
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        final_url = resp.geturl()
        status = getattr(resp, "status", None)

    parser = FormParser()
    parser.feed(body)

    script_hints = []
    for token in (
        "event/form/page",
        "ajax",
        "datepicker",
        "reported",
        "date_from",
        "date_to",
    ):
        if token.casefold() in body.casefold():
            script_hints.append(token)

    print(json.dumps({
        "requested_url": URL,
        "final_url": final_url,
        "http_status": status,
        "form_count": len(parser.forms),
        "forms": parser.forms,
        "script_hints_found": script_hints,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
