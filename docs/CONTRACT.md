# Shared contract

Models: `api/app/schemas.py` (mirrored in `web/src/lib/types.ts`). Tables: `api/app/db.py`.
Reference data: `api/app/refdata.py`. Change these only by agreement; workstreams build on them.

## Personas / roles
`industry` (acme.industry, company UEI `ACME12345XYZ`), `g3` (g3.planner), `range_scheduler`
(ytc.scheduler), `atec_viewer` (atec.hq). Token = username, sent as `Authorization: Bearer <token>`.
Use `auth.require(...)` and `auth.ATEC_ROLES`. Industry users never see ATEC sites, maps or schedules.

## Request lifecycle
`submitted` → `planning` → `in_review` (recommendation draft exists) → `approved` / `rejected` → `scheduled`.

## Geo layers (`GET /api/geo/sites/YTC/layers`)
Feature `properties.kind`: `range_complex` (`range_type`, `test_functions`), `firing_point`
(`range_complex_id`), `target_area` (polygon), `gate` (`road`), `road_segment` (`road`, `gate_from`,
`gate_to`, `length_km`). Road segments between consecutive gates are the unit of closure.
`GET /api/geo/sites/YTC/roads` is the full public road network (display only).

## Workstreams (one child session / PR each; stay inside your files)
| WS | Scope | Backend | Frontend |
|----|-------|---------|----------|
| 1 | Industry sign-in, company profile (UEI/CAGE/NAICS/POC), test request form (Test Mission Area → Applicable Test Functions), my requests | `api/app/routers/industry.py` | `web/src/features/industry/` |
| 2 | Rules matcher, Devin-session planning (disabled w/o key), G3 queue, approve/edit/reject → schedule | `api/app/routers/planning.py`, `api/app/matcher.py`, `api/app/devin_client.py` | `web/src/features/g3/` |
| 3 | ATEC national map, YTC site map (imagery, boundaries, ranges, roads, gates, live closures, schedule overlay) | `api/app/routers/core.py` (geo read endpoints only) | `web/src/features/atec-map/` |
| 4 | Scheduling: SDZ geometry, road-segment closure, gate-aware partial closure, conflicts (SDZ overlap, roads, equipment, crews, range) | `api/app/routers/scheduling.py`, `api/app/sdz.py` | `web/src/features/schedule/` |

Cross-workstream Python calls (stubbed until implemented — code against the signature):
- WS1 → WS2: `planning.start_planning(request_id) -> recommendation_id`
- WS2 → WS4: `scheduling.check_event(ProposedEvent) -> ScheduleCheck`, `scheduling.create_event(...)`
- WS3 → WS4: `GET /api/schedule/closures?at=` and `GET /api/schedule/events` for map overlays
