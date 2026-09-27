# First Live Source Validation — 2026-09-27

## Validated run

- GitHub Actions run: `36300637185` (run #8)
- Commit: `a02762bb8261de6e169182cdc4c2222b6609d4ef`
- Time: 2026-09-27 06:37 UTC (13:37 ICT)
- Workflow conclusion: **success**
- Pilot area: Ram Inthra / Prasert-Manukitch / Pradit Manutham / Nuan Chan

## 1. Latest iTIC / Longdo events — PASS

The live source `https://event.longdo.com/feed/json` was successfully
retrieved and parsed.

Observed in the validated run:

- HTTP: `200`
- payload size: `1,525,575` bytes
- broad study-area records: `41`
- latest event start: `2026-09-27 13:27:05 ICT`
- latest-event age at retrieval: `0.17 h`
- format: JSON

The broad bbox count is **not** treated as the number of incidents on the
four core roads.

## 2. Exact OSM core-road geometry — PASS

The Overpass extraction now uses exact configured main-road names instead
of substring aliases, preventing `ซอยรามอินทรา...`, similarly named roads,
and side streets from contaminating the core network.

Exact OSM ways:

- Ram Inthra: `116`
- Pradit Manutham: `79`
- Prasert-Manukitch: `95`
- Nuan Chan: `12`
- Total: `302`
- Missing configured roads: none

OSM-derived outputs preserve OpenStreetMap attribution and ODbL metadata.

## 3. Core-road incident attribution — PASS

Road attribution now requires geometry plus road-identity evidence.

Supporting route identities used by the pilot:

- Highway 304 supports Ram Inthra identity within the configured pilot
  section.
- Highway 351 supports Prasert-Manukitch identity.

Matching result from 41 broad-area event records:

- `NETWORK_CONTEXT_ONLY`: 30
- `GEOMETRY_ONLY_CANDIDATE`: 1
- `GEOMETRY+ROUTE_CONFIRMED`: 10

Candidate road records inside the geometric threshold:

- Ram Inthra: 6
- Prasert-Manukitch: 5

Confirmed road records:

- Ram Inthra: **5**
- Prasert-Manukitch: **5**

One record located near Ram Inthra but titled `ถนนแจ้งวัฒนะ` remains a
geometry-only candidate and is **not** counted as a confirmed Ram Inthra
incident.

## 4. Duplicate/update clustering — PASS

The feed can contain multiple records representing the same physical
incident/location. Confirmed records are therefore clustered by:

`confirmed road + event type + normalized title + rounded coordinate`

Validated run result:

- confirmed source records: **10**
- distinct confirmed incident clusters: **7**
- Ram Inthra: **2 distinct incidents**
- Prasert-Manukitch: **5 distinct incidents**

These cluster counts are suitable for the Phase 0 incident-side KPI,
subject to the stated source-completeness limitation.

## 5. Current traffic speed/status — BLOCKED ON ACCESS

The documented Free-Longdo status endpoint:

`https://traffic.longdo.com/api/feed/free`

redirects to:

`https://live.iticfoundation.org/feed/free`

and returns:

- HTTP `401 Unauthorized`
- no usable anonymous payload

This has been reproduced across live smoke runs, so it is treated as an
access dependency rather than a parser defect.

An optional Longdo Map REST traffic-speed adapter is already implemented at:

`scripts/live/fetch_longdo_traffic_speed.py`

It uses the official `traffic/speed` service and is enabled automatically
when repository secret `LONGDO_MAP_API_KEY` is present. No API key is
stored in this repository.

## Phase 0 status

### Passed

- latest event connectivity and currentness
- live event JSON parsing
- source/retrieval freshness metadata
- exact four-road OSM geometry
- broad-area vs core-road separation
- geometry + route-identity incident confirmation
- duplicate/update clustering
- live GitHub Actions validation
- ephemeral raw-data artifact capture without committing raw live data

### Remaining dependency

**Current traffic speed/status** is the main missing input before building:

- road/segment current condition
- current-vs-normal comparison
- incident traffic impact
- cross-road spillover/diversion analysis
- the first real “Now” dashboard

## Next gate

Provide a qualified real-time speed source. The current implementation is
ready to use a Longdo Map API key through GitHub secret
`LONGDO_MAP_API_KEY`; alternative sources can be added behind the same
adapter boundary without changing the incident pipeline.
