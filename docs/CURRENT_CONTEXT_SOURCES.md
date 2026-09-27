# Current Context Sources

## Purpose

These sources enrich the latest-first POC while segment-level traffic speed is
still an access dependency. They are **not substitutes for road-segment speed**.

## Longdo Traffic Index

Official Longdo Traffic documentation describes a 0-10 congestion index for
Bangkok and vicinity, recalculated every five minutes. A documented JSON/JSONP
endpoint is available:

`https://traffic.longdo.com/api/json/traffic/index?callback=...`

The POC stores:

- index value;
- source Unix timestamp;
- retrieval timestamp;
- source age;
- freshness class.

Use it as **city/metropolitan context** only.

The official download page also publishes 2026 historical Traffic Index data
at:

`https://traffic.longdo.com/api/raw/trafficindex/2026`

The first smoke run audits the real CSV schema before baseline logic is added.

## iTIC / Longdo Traffic Cameras

The iTIC Traffic Data Feeds page publishes:

- a camera metadata feed;
- JPEG/MJPEG camera endpoints.

Phase 0 first fetches the public JSON camera metadata and filters camera
locations to the pilot bbox. Camera images are intended for:

- human/visual incident validation;
- flood/road-condition context;
- later optional computer-vision experiments.

Camera data are **not** converted into vehicle speed in Phase 0.

## Segment speed remains separate

The preferred quantitative current-speed interface remains a provider adapter
that returns, at minimum:

- road/segment;
- direction;
- speed;
- source timestamp;
- source quality/freshness.

The existing Longdo Map `traffic/speed` adapter satisfies this interface when
a valid API key is supplied. The official REST documentation states that the
response includes road, direction, speed in m/s, source
(real-time/predicted), and nearest road coordinates.

## Attribution

Always retain provider/source metadata:

- Longdo Traffic / iTIC Foundation for traffic context and cameras;
- OpenStreetMap contributors for road geometry.
