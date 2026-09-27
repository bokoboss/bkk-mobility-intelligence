# Phase 0 — Data Feasibility Audit

**Status:** Active  
**Audit date:** 2026-09-27  
**POC:** BKK Mobility Intelligence

## Executive finding

The POC is technically feasible enough to proceed to a controlled data experiment.

The strongest foundation is the iTIC ecosystem: the iTIC Traffic Data Hub states that its nationwide GPS probe data include position, speed and heading from more than 160,000 probes, 24/7, and that probe data can be used to calculate Link Speed and Travel Time Index (TTI). The iTIC Open Data Archive also publishes historical traffic incidents, traffic status and raw probe data under CC BY 4.0.

The main Phase 0 constraint is **data volume and source heterogeneity**, not lack of data. Raw probe archives are roughly 0.8–2.7 GB per month in the visible archive, while historical event archives can exceed 1 GB per year. The POC should therefore use study-area-first spatial extraction, road/segment map matching, and offline preprocessing rather than sending raw national data to the web client.

## Recommended test design

Use two tracks, with **Track A now primary**:

### Track A — latest/current operations (PRIMARY)

- Live incidents: `https://event.longdo.com/feed/json`
- Free traffic status: iTIC / Longdo `Free-Longdo` mobile-probe feed
- Current-year / recent archives: use 2026 records where live endpoints are insufficient for recent trend analysis
- Goal: current road/network status, latest incidents, 24 h / 7 d recent trend, freshness monitoring and current-vs-normal comparison
- Rule: store retrieval time and source time separately; never label a stale/unknown-age response as live

### Track B — reproducible historical baseline

Use historical data where incident and probe archives are explicitly covered by the published iTIC archive license.

- Pilot network: Ram Inthra Road, Prasert-Manukitch Road, Pradit Manutham Road and Nuan Chan Road
- Initial analysis window: one selected week, expanded only if coverage is adequate
- Core sources: iTIC historical incidents + iTIC raw probe
- Goal: prove study-area extraction, road/segment matching, directional speed profiles, event matching, disruption comparison, and at least one cross-road impact test

## Verified source matrix

| Source | What is verified | Access / scale | License / terms status | POC status |
|---|---|---|---|---|
| iTIC live incident JSON | Latest incidents/events collected at iTIC; JSON feed exists; sample fields include IDs, text, coordinates, type, start/stop, contributor, icon, severity | Live JSON | Live-endpoint terms still to verify separately | **Yellow — technically usable** |
| iTIC historical incidents | Nationwide archived incident records | Visible annual archives: 2017 ~1.8 GB, 2018 ~1.6 GB, 2019 ~1.8 GB, 2020 ~1.5 GB, 2021 ~1.0 GB, 2022 ~342 MB, 2023 incomplete ~143 MB | CC BY 4.0 | **Green** |
| iTIC raw vehicle/mobile probe | Vehicle/mobile GPS observations; fields documented as VehicleID, gpsvalid, lat, lon, timestamp, speed, heading, taxi for-hire light, engine status | Monthly `.tar.bz2`; visible archive 2017–2025; ~0.8–2.7 GB/month | CC BY 4.0 | **Green — core performance source** |
| iTIC traffic status archive | Archived traffic-condition feeds across Thailand road network | Archive announced; direct index still needs retrieval validation | CC BY 4.0 | **Yellow/Green — license clear, access to validate** |
| iTIC Free-Longdo status feed | Free traffic status based on mobile probes from Longdo/iTIC applications | Live feed redirects to iTIC live service | Live access/terms to validate | **Yellow** |
| BMA water level | Water level / quantity every 5 minutes, 3-year history at Bangkok measurement points | API/data resource | Public dataset; exact resource terms to record during ingestion | **Green candidate** |
| BMA construction / road restoration | Project name, progress, expected completion, expected road-surface restoration | CSV; catalog says real-time update frequency, resource metadata last updated 2025-03-31 | Dataset page does not specify a license | **Yellow — useful context, licensing/recency check needed** |
| MOT TRAMS road accidents | Event-level road accidents on highways, rural highways and expressways; yearly resources | CSV/XLSX; catalog updated 2026-06-12 | Open Data Common; public | **Green candidate, but network coverage is not all Bangkok streets** |
| MOPH RTIDC | Injury/death integration and rolling 180-day risk analysis | Public analytical pages; detailed event export/API not yet validated | Usage path to validate | **Yellow — validation/context source** |
| TMD weather observations | Daily / 3-hourly surface-weather observations and rainfall datasets/API documentation | Public datasets/API | Source-specific terms to record | **Green candidate for weather context** |
| OpenStreetMap | Road geometry / network context | Extract/API depending workflow | ODbL attribution and derivative-database obligations apply | **Green candidate** |

## iTIC live event schema observations

The current JSON feed exposes records with fields observed in the public feed such as:

- `eid`
- `title`, `title_en`
- `description`, `description_en`
- `latitude`, `longitude`
- `type`
- `start`, `stop`
- `contributor`
- `icon`
- `showlevel`
- `severity`
- optional `images`

The iTIC/Longdo event API documentation specifies WGS84 latitude/longitude and local date-time strings in `YYYY-MM-DD HH:MM:SS` format for event reporting. Feed observations show that some metadata such as severity may be blank, so normalization must treat missing values explicitly.

### Event archive structure

The historical sample archive shows repeated event snapshots at 30-minute intervals (for example, `...0700-event.xml.gz`, `...0730-event.xml.gz`, `...0800-event.xml.gz`). Therefore:

1. archive files are snapshots, not one-record-per-event transaction logs;
2. the ETL must deduplicate repeated events using event ID and relevant update/state fields;
3. the analysis must distinguish event duration from snapshot persistence.

This is a critical implementation detail.

## iTIC probe format observations

The historical archive README describes daily CSV probe files with nine fields:

`VehicleID,gpsvalid,lat,lon,timestamp,speed,heading,for_hire_light,engine_acc`

However, a separate current public iTIC probe-format page documents an eight-field variant:

`VehicleID,gpsvalid,lat,lon,timestamp,speed,passenger_lamp,engine_acc`

This is treated as a **schema/version discrepancy that must be detected from the file itself**, not as an error to silently resolve. Phase 0 tooling therefore accepts both known variants and records the detected schema on every extracted row.

Key points that are common or explicitly documented:

- timestamp is local GMT+7 in the archive documentation;
- speed is km/h;
- GPS validity is explicitly flagged;
- the nine-field variant includes heading in degrees `[0,360)` from north;
- inactive vehicles can have lower reporting frequency;
- taxi/passenger-lamp status can introduce fleet/sampling effects.

### Consequence for the POC

Do **not** calculate corridor speed as a naïve mean of every probe point inside a buffer. At minimum, processing must include:

- schema/version detection before analysis;
- `gpsvalid == 1` filtering;
- map/corridor matching;
- direction/heading screening **only when heading is actually present**;
- stationary/off-network outlier treatment;
- time binning;
- vehicle/probe sampling bias checks;
- adequate sample-count thresholds per time bin.

The first probe extractor is intentionally a streaming local-archive tool: it reads a monthly `.tar.bz2` sequentially, filters date/GPS validity/bounding box, and writes a much smaller canonical CSV for QA before GeoParquet/DuckDB are introduced.

## Supporting data observations

### BMA water levels

Bangkok's public dataset describes 5-minute water-level/quantity observations and 3 years of history. This resolution is potentially suitable for flood/disruption correlation, provided stations exist near the selected corridor and timestamps can be aligned.

### Construction context

BMA's construction dataset can explain planned disruptions, but the public catalog currently presents a tension between an advertised real-time update frequency and a resource update date of March 2025. Treat it as contextual data until freshness is validated.

### Crash data

TRAMS is useful for formal road-accident context and is licensed as Open Data Common, but it focuses on the Ministry of Transport road network (highways, rural highways and expressways). It should not be assumed to represent all local Bangkok street crashes.

RTIDC is valuable for cross-validation and injury severity context, but the public interface observed in this audit is an analytical portal; event-level programmatic access still needs validation.

## Data architecture consequence

Recommended Phase 0 flow:

```text
Remote archives / feeds
        |
        v
Source-specific ingest
        |
        v
Raw local cache (not Git)
        |
        v
Normalize + QA
        |
        v
Spatial pre-filter around study area
        |
        v
Parquet / GeoParquet
        |
        v
DuckDB analytical store
        |
        +--> speed profile
        +--> incident timeline
        +--> baseline vs disruption
        +--> data-gap report
```

Do not use raw XML/GZIP/TAR data directly from a browser application.

## Phase 0 decision gates

### Gate 1 — incident ETL

Pass when we can:

- ingest a historical sample;
- normalize IDs/timestamps/coordinates/types;
- remove snapshot duplicates correctly;
- extract events inside the study area and match them to a road/segment using geometry plus textual/context checks.

### Gate 2 — probe ETL

Pass when we can:

- extract only a chosen period from a monthly archive;
- spatially pre-filter observations to the four-road study area;
- produce reliable sample counts and directional speed distributions.

### Gate 3 — analytical signal

Pass when we can produce at least:

- hourly speed profile;
- weekday/weekend or baseline comparison;
- low-speed/congestion periods;
- event timeline;
- speed before/during/after at least several matched incidents;
- explicit uncertainty / sample-size indicators.

### Gate 4 — supporting context

Optional for first pass. Add water/rain/construction/safety only after the core incident + performance relationship works.

## Current risks

1. **Archive size:** must stream/extract selectively; no full national in-memory load.
2. **Probe representativeness:** probe fleet mix is not equivalent to total traffic population.
3. **Map matching:** raw lat/lon + heading must be matched to the intended carriageway/direction.
4. **Event completeness:** event feeds aggregate reports from multiple sources and should not be treated as a complete census of incidents.
5. **Time alignment:** all sources require explicit timezone and timestamp normalization.
6. **License differences:** live endpoints, historical archives and government datasets require separate provenance/terms records.
7. **Network coverage:** AADT/crash datasets may omit Bangkok local roads.

## Immediate next task

Build a **current-source bundle** for the Ram Inthra–Prasert-Manukitch–Pradit Manutham–Nuan Chan pilot network: live incident JSON + Free-Longdo traffic status + retrieval/freshness metadata. Then add the newest practical 2026/recent archive slices needed for 7/30-day context. Historical probe/incidents are deferred to baseline construction after the current pipeline works. The web UI remains intentionally deferred.

## Official references

- iTIC Traffic Data Hub / Open Data Sharing: https://iticfoundation.org/en/open-data-sharing/
- iTIC Open Data Archives: https://itic.longdo.com/opendata/
- iTIC / Longdo Traffic Data Feeds: https://traffic.longdo.com/feed/
- iTIC historical incidents: https://traffic.longdo.com/data/events/
- iTIC raw probe archive: https://traffic.longdo.com/opendata/probe-data/
- Live incident JSON: https://event.longdo.com/feed/json
- Longdo Traffic downloads: https://traffic.longdo.com/download
- BMA water levels: https://data.go.th/th/dataset/flood
- BMA construction projects: https://data.go.th/th/dataset/dpw011
- MOT/TRAMS accidents: https://data.go.th/dataset/gdpublish-roadaccident
- RTIDC: https://rti.moph.go.th/rtidc/public/index.php
