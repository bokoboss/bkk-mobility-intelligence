# Flood / Rain Intelligence v0.1

## Purpose

This layer turns recent reported rain and flood events into a road-oriented
resilience view for the Expanded V1 network.

It intentionally separates **reported-event intelligence** from measured
hydrometeorological sensors.

## Current analytical outputs

- flood episodes in latest 7 days, prior 7 days, and latest 30 days;
- flood recurrence by road;
- recurring flood hotspots: two or more flood episodes on the same confirmed
  road within a 300 m grouping radius;
- descriptive rain→flood association: nearest reported rain within the prior
  6 hours and 5 km, preferring the same confirmed road;
- map modes for Flood 7D and Flood 30D.

Rain→flood association is **not causal attribution**.

## Hydrometeorological sources

### TMD NWP

The TMD NWP download page is machine-readable and its JavaScript calls:

`/api/download-files?init_time=<YYYYMMDDHH>`

v0.1 fetches dataset metadata and looks for the highest-priority
`prec1hr` / Domain 2 / CSV candidate. Forecast grid values are not yet used
as observed rainfall.

### BMA Drainage and Sewerage Department

Official public sources are available for rainfall and road-flood monitoring,
but automated requests from the GitHub runner returned connection reset errors
during validation on 2026-09-27. Therefore v0.1 does **not** scrape or fabricate
BMA sensor values. The source remains explicitly marked as discovered but not
machine-ingested.

## Interpretation limits

- Longdo event reports are not complete sensor coverage.
- Counts are not exposure-normalized flood-risk rates.
- Event stop times are not treated as physical drainage recovery.
- A nearby preceding rain report is an association only.
