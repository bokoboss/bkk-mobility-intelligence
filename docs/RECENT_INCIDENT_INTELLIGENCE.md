# Recent Incident Intelligence — 7D / 30D

## Source

The documented current-year Longdo event-history download is streamed from:

`https://event.longdo.com/feed/2026`

The annual CSV is **not** committed or persisted in full. The ingestion step
streams rows, keeps only events whose start timestamp is within the last 30 days,
then applies the Expanded V1 study-area bbox before spatial matching.

## Time semantics

- anchor: the retrieval time of the live current-event feed;
- 7D: event episodes whose first start is in the latest 7-day window;
- prior 7D: immediately preceding 7-day window;
- 30D: event episodes whose first start is in the latest 30-day window.

These are reported-event episodes, not exposure-normalized rates.

## Episode deduplication

Historical rows often contain update records such as
`คืบหน้าอุบัติเหตุ...`. The history engine:

1. canonicalizes common update prefixes;
2. requires the same confirmed road, event type and canonical title/location
   or route segment;
3. groups overlapping or near-continuous records into one episode;
4. starts a new episode when the prior episode has ended and the next record is
   separated by more than six hours.

## Dashboard

The map now supports:

- Now;
- 7 Days;
- 30 Days.

Historical modes use the same confirmed-road matching rules as Now and are
visually separated from current incidents. The history panel shows:

- 7-day incident episodes;
- comparison with the prior 7 days;
- 30-day incident episodes;
- top roads;
- top event types.

## Interpretation caution

A rise in reported incidents does not by itself mean the road became less safe
or more congested. Reporting intensity, event mix and exposure are not yet
normalized.
