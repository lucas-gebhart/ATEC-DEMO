# ATEC Test Planning & Range Scheduling Demo

Industry submits a test need → planning (rules matcher today, Devin session when enabled) drafts a
recommendation → ATEC G3 reviews and approves → YTC range schedule applies danger-zone road closures,
with gates limiting how much of a road closes.

- **API:** FastAPI + SQLite (`api/`), port 8000
- **Web:** React + Vite + Leaflet (`web/`), port 5173 (proxies `/api`)
- **Data:** `data/seed/` (taxonomy, sites, YTC equipment/people, personas, schedule), `data/geo/` (maps)

## Run
```bash
./dev.sh            # or run api and web separately, see dev.sh
cd api && .venv/bin/pytest
cd web && npm run typecheck
```
Sign in with any persona, password `demo`: `acme.industry`, `g3.planner`, `ytc.scheduler`, `atec.hq`.

## Devin planning sessions
Off by default. Set `DEVIN_PLANNING_ENABLED=true`, `DEVIN_API_KEY` (service user, `cog_...`) and
`DEVIN_ORG_ID` to have each submitted request start a Devin session (`api/app/devin_client.py`) that
returns a `RecommendationPayload` as structured output. Without them the rules matcher is used.

## Map data
- Installation boundaries: U.S. Census Bureau TIGER/Line 2024 military installations.
- Roads (US-95, Castle Dome Mine Rd, Cibola Rd, ...): TIGER/Line 2024 roads, Yuma and La Paz counties.
- Imagery: Esri World Imagery; Esri Topo and OpenStreetMap as alternates.
- Range complexes, firing points, impact areas and gates: `scripts/build_ytc_layers.py` places them on
  the real boundary and roads (regenerate with `python3 scripts/build_ytc_layers.py`).

See [docs/CONTRACT.md](docs/CONTRACT.md) for the data model, API and workstream ownership.
