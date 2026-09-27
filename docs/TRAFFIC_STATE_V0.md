# Traffic State v0.1

## Objective

Add a provider-neutral traffic-speed evidence layer to the Bangkok-wide
Mobility Intelligence pipeline without overstating what the available sources
can prove.

## Why this layer exists

The current public Free-Longdo traffic-status endpoint redirects to an iTIC
endpoint that returned HTTP 401 in the Bangkok-wide validation run on
2026-09-27. The repository also contains a Longdo Map traffic-speed adapter, but
that interface requires an authorized API key.

The pipeline therefore needs to distinguish:

- provider access blocked;
- provider reachable but no usable samples;
- partial sampled speed evidence;
- road-specific historical baseline available;
- abnormality actually evaluated.

These states must never collapse into a single boolean such as
`speed_available`.

## Contract

Output:

`data/processed/current_speed/traffic_state.json`

Schema:

`bkk-mobility-traffic-state-v0.1`

Key fields include:

- `access_state`
- `summary.road_count`
- `summary.sampled_road_count`
- `summary.sampling_coverage_ratio`
- `summary.usable_observation_count`
- `roads.<road_id>.median_speed_kmh`
- `roads.<road_id>.movement_class`
- `roads.<road_id>.baseline_state`
- `roads.<road_id>.abnormality_state`

## Descriptive movement bands

The current prototype uses simple absolute bands only to make sampled speeds
readable:

| Class | Sampled speed |
|---|---:|
| STOP_AND_GO | <= 10 km/h |
| SLOW | > 10 to 20 km/h |
| MOVING | > 20 to 35 km/h |
| FREE_FLOW_LIKE | > 35 km/h |

These are **not Level of Service thresholds** and must not be used to claim
that a road is unusually congested.

## Abnormality rule

A road may only be labelled abnormal after the project has a defensible
road-and-time-specific reference distribution, for example:

- same road and direction;
- comparable weekday/weekend class;
- comparable 15- or 30-minute time bin;
- sufficient historical sample size;
- documented seasonal / event exclusions.

Until then every road has:

- `baseline_state = NOT_BUILT`
- `abnormality_state = NOT_EVALUATED`

## Dashboard behavior

Road cards consume the traffic-state object embedded in
`latest_status.json`. When samples exist they show the sampled median speed
and descriptive movement band. When none exist they say that no usable traffic
speed sample is available.

This keeps the UI operational while the provider-access dependency is unresolved.

## Next engineering gate

After a lawful current-speed source is available:

1. increase sampling coverage deliberately, with quota/rate controls;
2. validate provider road names and directions against OSM geometry;
3. quantify spatial coverage by district and network tier;
4. build historical road/time baselines;
5. only then add current-vs-normal anomaly colouring to the map.
