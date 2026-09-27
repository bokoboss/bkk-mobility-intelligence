# Recent Incident Intelligence — 7D / 30D

## Source

The primary recent-history source is the same public JSON endpoint used by
Longdo Traffic's **Search for Events** interface:

`https://traffic.longdo.com/event.json`

The site JavaScript submits `page`, Unix `from` / `to`, `ordered`,
`eventtype`, and `pagger` parameters. The POC requests up to 1,000 records
per page, paginates until the date-range result is exhausted, and persists only
records inside Expanded V1.

The annual `https://event.longdo.com/feed/2026` CSV remains useful as an
archive/fallback, but is not used for live 7D/30D metrics because its event
coverage was observed to lag the live search database.

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


## Freshness gate

The ingestion manifest compares the newest `createtime` returned by
`/event.json` with the live-feed retrieval anchor. 7D/30D analytics are built
only when the recent-search source is within three hours of the anchor.
Otherwise the pipeline fails closed instead of rendering misleading zero counts.
