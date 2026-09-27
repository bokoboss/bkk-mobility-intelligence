# Traffic Coverage v0.2

## Purpose

Traffic Coverage v0.2 separates **sampling intent** from **actual traffic
observations** across the Bangkok-wide road network.

The system must never imply that a road or district has live speed data simply
because it was selected for probing.

## Planned Coverage

A deterministic daily sampling plan selects probe points under an **internal
request budget**. This is a project-side safety cap, not a statement about any
provider quota.

Default configuration:

- request budget: 30 probes/run;
- Strategic target share: 70%;
- one point per road per run;
- UTC-day deterministic rotation.

The selector spreads probes across districts before adding depth and rotates the
chosen roads so the same corridors are not permanently favored.

## Observed Coverage

Observed Coverage counts only usable speed observations returned by the
provider adapter.

It reports:

- distinct roads with observations;
- districts with observations;
- Strategic vs Urban road-count coverage;
- per-district planned and observed road-count ratios.

A district observation is credited only when the probe point is physically
inside that district.

## Coverage unit and limitation

Coverage is **road-count / road-district probe coverage**. It is not lane-km,
directional, or full-road-length coverage.

## Outputs

- `data/processed/current_speed/traffic_sampling_plan.json`
- `data/processed/current_speed/traffic_coverage.json`

Schemas:

- `bkk-mobility-traffic-sampling-plan-v0.2`
- `bkk-mobility-traffic-coverage-v0.2`

## Dashboard

Coverage mode shows:

- observed road: green;
- planned but no usable observation: amber;
- not planned this run: neutral;
- selected road: normal selection highlight.

The dashboard separately reports request budget, planned roads/districts,
observed roads/districts, tier coverage, and district coverage gaps.

## Next gate

After provider access and terms are confirmed:

1. validate the internal request cap against real provider limits;
2. collect repeated rotated samples;
3. quantify directional and temporal coverage;
4. build road/time baselines;
5. then add current-vs-normal anomaly classification.
