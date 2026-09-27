# Flood / Rain Intelligence v0.2

## Purpose

v0.2 extends the reported-event layer with **forecast rainfall exposure** and a
transparent **relative road watch profile**. It does not claim flood probability
or hydraulic depth.

## Inputs

### Longdo / iTIC reported events

Used for:
- flood episodes in 7D / prior 7D / 30D;
- recurring flood hotspots;
- reported-rain→flood association.

These are reported observations and are not a complete sensor census.

### TMD NWP Domain 2

The TMD download API exposes a Domain-2 (Thailand ~3 km) 24-hour accumulated
precipitation CSV:

`p24h.d02.<init>.csv`

The pipeline caches the CSV by model initialization cycle, streams it, retains
only grid cells around Expanded V1, and selects the **first forecast-valid time
strictly later than model initialization**. Road exposure is summarized from the
nearest retained 3-km grid cells touched by each OSM road.

TMD values are **forecast model output, not observed rainfall**.

### HII station registry

Station metadata is loaded from:

`https://tiservice.hii.or.th/opendata/data_catalog/hourly_rain/0all_stn_metadata.csv`

At validation time the study bbox contained:
- one rain station: `HII001`;
- three water-level stations: `BKK001`, `BKK008`, `BKK021`.

The current-month static archive for `202609` contained no CSV files during
validation, therefore the dashboard does not display invented or stale current
rainfall values.

The HII rainfall catalog states Creative Commons Attribution Non-Commercial;
reuse terms should be checked before commercial deployment.

## Relative Road Watch

For each study road:

- recurrence percentile = percentile rank of 30-day reported flood episodes;
- forecast precipitation percentile = percentile rank of TMD next-24h road
  maximum accumulation;
- relative watch index =
  `0.70 * recurrence percentile + 0.30 * forecast percentile`.

Classes:
- HIGH_RELATIVE_WATCH: index >= 75;
- ELEVATED_RELATIVE_WATCH: index >= 50;
- LOWER_RELATIVE_WATCH: index < 50.

This is **only a relative prioritization within the current study network**.
It is not:
- probability of flooding;
- flood depth;
- drainage-capacity assessment;
- a design return-period calculation;
- a replacement for BMA/HII measured sensors or hydraulic modelling.

## Map modes

- Flood 7D;
- Flood 30D;
- Flood Watch.

Flood Watch overlays:
- 30-day flood context;
- recurring hotspots;
- TMD 3-km next-24h forecast grid;
- road watch layer based on the relative index.

## Remaining gaps

1. Obtain a stable current measured-rain API/stream for HII or BMA.
2. Add current road-surface flood/water-depth observations when a validated
   machine-readable contract is available.
3. Add historical TMD/observed rainfall for event-by-event calibration rather
   than using only the current forecast.
4. Add terrain/drainage/canal context before calling the output a flood-risk
   model.
