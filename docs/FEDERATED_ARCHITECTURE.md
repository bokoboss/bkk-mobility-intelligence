# Federated Open Data Architecture

## Decision

BKK Mobility Intelligence adopts a **DB-free federated architecture** for the
current product stage.

The application does not maintain its own copy of every upstream transport,
weather, flood or road dataset. Public/open providers remain the source of
truth. The project persists only compact derived artifacts when recomputation is
expensive.

This is a deliberate architecture decision, not a temporary omission.

## Runtime model

```text
                         iTIC / Longdo
                         BMA Open Data
Web / Pages <- build <-  TMD / HII
        ^                OpenStreetMap
        |                     |
        +--- normalized source adapters
                      |
              compact derived artifacts
                      |
              GitHub Release assets
```

There is no application database in this stage.

## Data classes

### Live / latest data

Examples:

- current incidents;
- Traffic Index;
- current segment speed when authorized;
- weather / rainfall forecast;
- current hydro context.

Policy:

- fetch from the provider;
- normalize to project contracts;
- use short-lived build/runtime cache only;
- do not mirror a long-term raw copy merely for convenience.

### Static / slowly changing public geometry

Example: OpenStreetMap Bangkok road network.

Policy:

- fetch from the public source;
- validate;
- cache the derived geometry;
- render a compact static network artifact.

### Large historical archives

Example: iTIC / Longdo historical probe archives.

Policy:

- download only inside a manual cloud batch job;
- stream/process the archive;
- keep no raw archive after the job;
- publish only compact aggregate profiles;
- assemble those profiles into a compact road/time baseline.

GitHub Release assets are the initial persistent artifact store. They can later
be replaced by S3/R2 without changing the analytical contracts.

## Why no database now

The present product does not yet require:

- user accounts;
- user-authored data;
- arbitrary historical SQL queries;
- sub-second multi-user API queries;
- persistent alerts/preferences;
- a proprietary time-series archive.

Adding PostgreSQL/PostGIS now would create operational state without solving a
current product requirement.

## When a database becomes justified

Reconsider a managed database when one or more of these become real
requirements:

- continuous 5-minute observations retained for months/years;
- custom corridor/time-range queries;
- account-specific watchlists or alerts;
- OD/trajectory analysis over stored observations;
- API service for many external consumers;
- low-latency joins that cannot be served from compact artifacts;
- write-heavy operational workflows.

The future database, if introduced, is an implementation detail behind the
existing normalized contracts. The frontend should not depend on database
semantics.

## Historical baseline cloud flow

```text
PROBE-YYYYMM.tar.bz2
       |
       | manual GitHub Actions batch
       v
Bangkok polygon filter
       |
OSM road map matching + ambiguity rejection
       |
per-vehicle / road / 30-min daily aggregation
       |
probe-profile-YYYYMM.tar.gz
       |
       | GitHub Release asset
       v
monthly compact profiles
       |
       | manual assemble workflow
       v
road_time_baseline_v0_3.json
       |
       | GitHub Release asset
       v
Current Source Smoke / dashboard snapshot
```

Normal CI never downloads the multi-GB source archive.

## Failure semantics

A provider timeout, authorization error, missing release asset or expired source
must be surfaced as a data-state condition. It must not be converted into
traffic = 0, incidents = 0, or "normal" conditions.

## Machine-readable contract

See `config/federated_sources.json`.
