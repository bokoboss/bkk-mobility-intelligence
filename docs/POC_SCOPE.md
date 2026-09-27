# POC Scope

## Objective

Validate whether open and publicly accessible Bangkok mobility datasets can be combined into a corridor-level analytical product that explains traffic performance, disruption patterns, and data gaps.

## Phase 0 — Data Feasibility Audit

The first phase will not build the full application. It will establish whether the data is sufficient and defensible.

### Core questions

1. Can a real Bangkok corridor be represented consistently across all datasets?
2. Can incident/event records be spatially matched to the corridor?
3. Can traffic performance be measured over time with adequate temporal resolution?
4. Can disruption periods be compared with normal baseline conditions?
5. Are the licensing and attribution requirements compatible with a POC?
6. What important engineering data remain unavailable and would still require field surveys?

## Candidate POC outputs

- Corridor map
- Incident timeline
- Event type distribution
- Typical daily traffic profile
- Weekday/weekend comparison
- Recurring vs non-recurring congestion indicators
- Disruption duration and recovery indicators
- Data-gap / survey recommendation summary

## Explicitly out of scope for Phase 0

- Production deployment
- User authentication
- Real-time operational control
- Route guidance
- Traffic signal optimization
- Full Bangkok-wide coverage
- Large-scale AI assistant features

## POC success criteria

Phase 0 is successful if one corridor can be analyzed with enough data quality to generate repeatable, engineering-useful findings while clearly documenting uncertainty and missing data.

## Next decision gate

After Phase 0, decide whether to proceed to:

- P1 Analytics Prototype only,
- P2 Web Explorer,
- or stop / revise the concept if data quality is insufficient.
