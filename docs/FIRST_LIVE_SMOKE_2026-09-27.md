# First Live Source Smoke — 2026-09-27

## Live validation runs

### Run 1 — initial source qualification

- GitHub Actions run: `36299964884`
- Time: 2026-09-27 06:23 UTC (13:23 ICT)
- Pipeline result: `PARTIAL`

The iTIC / Longdo event JSON returned HTTP 200 with 745 records,
all with coordinates. The broad pilot bbox contained 41 records. The
latest event start was 13:21 ICT, about 0.05 h before retrieval.

The Free-Longdo traffic-status request returned HTTP 401.

### Run 3 — hardened matcher / redirect diagnostics

- GitHub Actions run: `36300151445`
- Commit: `e946b64bd5d5e37d2b2fd0628220c5c292c05989`
- Workflow conclusion: `success`
- Time: 2026-09-27 06:27 UTC (13:27 ICT)

Events:

- HTTP 200
- payload 1,555,073 bytes
- broad study-area records: 41
- latest event start: 2026-09-27 13:21 ICT
- latest-event age at retrieval: 0.11 h
- format: JSON

The stricter text-evidence rule yielded:

- TITLE_STRONG: 1
- DESCRIPTION_CONTEXT: 9
- UNMATCHED: 31

The one title-strong core-road record was:

- 2026-09-26 22:30 — น้ำท่วม รามอินทรา 5 แยก 42

The description-only cases were largely false road-name signals caused by
responding-agency text such as หมวดทางหลวงรามอินทรา. They are now
context-only and cannot become road attribution without geometry.

Free-Longdo traffic status:

- requested URL: https://traffic.longdo.com/api/feed/free
- final URL: https://live.iticfoundation.org/feed/free
- HTTP 401 Unauthorized
- usable payload: none

This establishes that current speed is an access dependency, not a parser
failure.

## Current Phase 0 decision

Passed:

- live event connectivity and currentness;
- event parsing and freshness metadata;
- broad study-area extraction;
- title-vs-description QA;
- live GitHub Actions environment;
- ephemeral raw-data artifact capture.

Next gate:

1. fetch exact OSM geometry for the four core roads;
2. match events by distance to road geometry;
3. keep broad-bbox events as context only;
4. use a qualified keyed/alternative current-speed source;
5. build current-vs-baseline analytics only after current speed is qualified.
