# BKK Mobility Intelligence

A proof-of-concept project for turning Bangkok mobility and disruption data into decision-useful transportation intelligence.

> **Current stage:** Phase 0 — Latest-First Data Feasibility Audit  
> The POC prioritizes live/current conditions and recent trends. Historical data are used primarily to establish normal baselines and context, not as the main product experience.

## POC question

Can we select one compact real Bangkok road network and reliably explain:

- how traffic performance changes by road, direction and time of day,
- where recurring congestion occurs,
- what disruptions/incidents occur on or near each road,
- how conditions differ during disruption periods,
- whether disruption on one road is associated with changes on nearby alternatives,
- and what additional survey data would still be required for a professional traffic study?

## Initial data source

### iTIC traffic incidents

The initial live incident feed is:

- `https://event.longdo.com/feed/json`

**Primary attribution:** Intelligent Traffic Information Center Foundation (**iTIC Foundation**), via the iTIC / Longdo Traffic event feed.

Official references:

- iTIC Foundation — Open Data Sharing: https://iticfoundation.org/en/open-data-sharing/
- iTIC Open Data Archives: https://itic.longdo.com/data/
- iTIC / Longdo Traffic Data Feeds: https://traffic.longdo.com/feed/
- Live event feed: https://event.longdo.com/feed/json

The official Traffic Data Feeds page describes the Events RSS/JSON feed as the latest incidents and events collected at iTIC via `events.longdo.com`.

### Licensing note

The iTIC Open Data Archives explicitly list **Historical Traffic Incidents**, **Historical Traffic Information Status**, and **Historical Raw Vehicle & Mobile Probe Data** under **CC-BY 4.0**. The live event feed is treated separately until its applicable terms are verified; this project does not assume that the archive license automatically applies to every live endpoint.

## Latest-first principle

The product should answer **what is happening now, what changed recently, and how abnormal it is**. Data priority is:

1. live / near-real-time feeds;
2. current-year (2026) and recent 7/30/90-day records;
3. older historical archives only for baselines, seasonality and validation.

Every ingested source should preserve `retrieved_at`, source timestamp(s) when available, and an explicit freshness status. The UI must never present stale data as current.

See `docs/LATEST_FIRST_STRATEGY.md`.

## Architecture decision — DB-free federated open data

The current architecture deliberately avoids an application database.

Upstream public/open providers remain the source of truth. The project fetches
live/latest data on demand or during the dashboard build, normalizes it to stable
project contracts, and persists only compact derived artifacts that are
expensive to recompute.

Large historical probe archives are processed in manual GitHub Actions batch
jobs. Raw archives are discarded after each job; only monthly aggregate
profiles and the compact road/time baseline are persisted as GitHub Release
assets.

This keeps the system low-ops and replaceable: the Release-asset store can later
move to S3/R2 without changing frontend or analytical contracts.

See:

- `docs/FEDERATED_ARCHITECTURE.md`
- `config/federated_sources.json`

## Phase 0

Before building the application, the project will audit candidate datasets for:

- spatial coverage,
- temporal coverage and resolution,
- schema and coordinate system,
- missing/duplicate records,
- directionality and road matching,
- historical depth,
- access method and file size,
- licensing / attribution requirements,
- analytical usefulness for the selected Bangkok pilot network.

See:
- `docs/POC_SCOPE.md`
- `docs/DATA_SOURCES.md`
- `docs/TEST_AREA.md`

## Planned progression

1. **P0 — Data Feasibility Audit**
2. **P1 — Analytics Prototype**
3. **P2 — Mobility Intelligence Explorer**
4. **P3 — User / stakeholder validation**
5. **P4 — Production hardening; introduce a managed backend/database only when concrete requirements justify persistent operational state**

## Scope discipline

This is not intended to become another generic traffic map. The target is an analytical engine that converts mobility, incident, weather/flood, road-network, traffic-volume and safety data into road-segment and small-network transportation intelligence.

## Data attribution

When iTIC-derived data is displayed, exported, analysed or cited, the project will preserve source attribution to:

**Intelligent Traffic Information Center Foundation (iTIC Foundation)**

Additional source-specific attribution and licensing requirements will be recorded in `docs/DATA_SOURCES.md`.
