# POC Scope

## Objective

Validate whether open and publicly accessible Bangkok mobility datasets can be combined into a compact road-network analytical product that explains segment-level traffic performance, disruption patterns, cross-corridor effects, and data gaps.

## Phase 0 — Data Feasibility Audit

The first phase will not build the full application. It will establish whether the data is sufficient and defensible.

### Core questions

1. Can a compact Bangkok road network be represented consistently across all datasets?
2. Can incident/event records be matched to the correct road or road segment without relying on a broad buffer alone?
3. Can traffic performance be measured per road, direction and time period with adequate temporal resolution?
4. Can disruption periods be compared with normal baseline conditions?
5. Can an incident on one road be associated with measurable changes on nearby alternative roads?
6. Are the licensing and attribution requirements compatible with a POC?
7. What important engineering data remain unavailable and would still require field surveys?

## Candidate POC outputs

- Study-area network map
- Road / segment performance profiles
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

Phase 0 is successful if the selected four-road pilot network can be reduced to reliable road/segment-level observations and can generate repeatable, engineering-useful findings while clearly documenting uncertainty and missing data. Full coverage of every road is not required; the decision gate is whether the core network produces enough usable signal to justify P1.

## Next decision gate

After Phase 0, decide whether to proceed to:

- P1 Analytics Prototype only,
- P2 Web Explorer,
- or stop / revise the concept if data quality is insufficient.
