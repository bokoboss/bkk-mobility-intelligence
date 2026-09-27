# Phase 0 Test Corridor — Rama IX Road

## Corridor

**Rama IX Road: Ratchadaphisek intersection to Srinagarindra interchange, Bangkok**

A public description of Rama IX Road identifies the road as beginning at the Rama IX intersection with Ratchadaphisek / Asok-Din Daeng and continuing east to the Srinagarindra interchange, with an overall length of about 9 km.

## Why this corridor

This is a deliberately demanding but manageable POC corridor:

- urban arterial with strong peak-period traffic variation;
- multiple major intersections and access points;
- expressway / motorway influence;
- suitable for directional probe-speed analysis;
- plausible exposure to incidents, roadworks and heavy rain/flood disruption;
- long enough to demonstrate corridor intelligence but short enough for selective extraction.

## Phase 0 analytical boundary

Use the road centerline as the primary geometry and begin with a configurable buffer:

- **250 m:** strict corridor event matching
- **500 m:** default contextual event matching
- **1,000 m:** sensitivity / network-context check

Events must not be attributed to Rama IX Road purely because they fall inside a large buffer. Final matching should consider road name, network proximity, heading/direction where available and event description.

## Initial temporal strategy

Use a short historical replay before attempting a full year:

1. one weekday week for probe-speed QA;
2. expand around incident dates with adequate observations;
3. only then expand to month/year profiles.

For licensing clarity, the first fully reproducible incident + probe replay should use data from the explicitly CC BY 4.0 historical archives. A more recent/live track can run separately once endpoint-specific terms are recorded.

## First outputs

1. corridor geometry and buffered study zones;
2. matched incident list with event categories;
3. probe sample coverage by 15-minute bin and direction;
4. hourly speed profile;
5. data-quality report;
6. selected incident windows with speed before / during / after;
7. recommendation whether the corridor is suitable for the P1 analytics prototype.

## Not yet assumed

- that every probe represents general traffic equally;
- that event feeds are complete;
- that all nearby incidents affect the corridor;
- that AADT is available on every segment;
- that live feed licensing matches historical archive licensing.

## Geometry status

Exact OpenStreetMap-derived centerline geometry is intentionally not committed yet. It will be generated in the spatial-extraction step with its OSM provenance and attribution recorded, rather than hand-drawing approximate coordinates.
