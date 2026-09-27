# First Live Source Smoke — 2026-09-27

## Run identity

- GitHub Actions run: `36299964884`
- Run timestamp: 2026-09-27 06:23 UTC (13:23 ICT)
- Pilot area: Ram Inthra / Prasert-Manukitch / Pradit Manutham / Nuan Chan
- Artifact: `current-source-smoke` (3-day retention)

## Result

**Pipeline status: PARTIAL**

### Latest iTIC / Longdo event JSON — PASS

A live request to `https://event.longdo.com/feed/json` succeeded.

Observed in the smoke run:

- HTTP `200`
- retrieved at `2026-09-27T06:23:55Z`
- HTTP `Last-Modified`: `2026-09-27T06:22:01Z`
- payload size: `1,555,073` bytes
- total records: `745`
- unique event IDs: `745`
- invalid/missing coordinates: `0`
- records inside the broad Phase 0 extraction bbox: `41`
- latest event start: `2026-09-27 13:21 ICT`
- latest-event age at retrieval: approximately `0.05 h`

This is strong evidence that the incident source was current during the run.

The 41 bbox records were dominated by flood reports (38) plus three car-breakdown reports. They are **context candidates**, not 41 events on the four core roads.

A clearly relevant title-level match in the snapshot was:

- `2026-09-26 22:30` — `น้ำท่วม รามอินทรา 5 แยก 42`

### QA finding — description false positives

The initial matcher searched the whole event object. Some highway-event descriptions contain the responding-agency phrase `เจ้าหน้าที่หมวดทางหลวงรามอินทรา`, which falsely looks like a Ram Inthra Road match even when the event is on another highway.

The matcher is therefore split into:

- `TITLE_STRONG` — road alias in `title/title_en`;
- `DESCRIPTION_CONTEXT` — alias only in `description/description_en`;
- `UNMATCHED` — no text evidence.

Description-only evidence is never final road attribution. Geometry is still required.

A re-check of the first 41-record snapshot with this stricter logic yielded:

- `TITLE_STRONG`: 1
- `DESCRIPTION_CONTEXT`: 9
- `UNMATCHED`: 31

### Free-Longdo traffic status — BLOCKED

The request to `https://traffic.longdo.com/api/feed/free` returned:

- HTTP `401 Unauthorized`
- no usable traffic payload

Therefore current speed/status is **not yet solved** by the anonymous Free-Longdo endpoint.

## Phase 0 decision

Passed:

- live-event connectivity;
- JSON parsing;
- source/retrieval freshness metadata;
- broad study-area extraction;
- internet-enabled GitHub Actions smoke environment;
- ephemeral artifact capture without committing raw live data.

Still open:

- exact road/segment incident attribution;
- current road speed/status source;
- road geometry / segment inventory;
- current-vs-baseline comparison;
- cross-road impact analysis.

## Next action

1. Add exact road geometry / segment matching for the four-road pilot.
2. Keep iTIC Events JSON as the live incident source.
3. Qualify another current-speed source or an authenticated iTIC/Longdo route.
4. Do not build the dashboard until current speed/status is available or the POC is explicitly re-scoped as incident-first.
