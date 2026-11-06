import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, LayerGroup, LayersControl, MapContainer, Marker, Pane, Polygon, Polyline, Tooltip, useMapEvents } from "react-leaflet";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import type { Site } from "../../lib/types";
import { BaseLayers } from "./BaseLayers";
import {
  type Equipment, type FC, type Feature, type Person, type RoadSummary, FIRING_POINT_SVG, RANGE_STYLES, fmtTime,
  firingPointIcon, gateIcon, gateSvg, rangeColor, roadLabel, toIso, toMs, useFunctionLabels,
} from "./shared";
import { useSchedule } from "./useSchedule";

const WORLD: [number, number][] = [[-89, -179.9], [89, -179.9], [89, 179.9], [-89, 179.9]];
const latlngs = (line: GeoJSON.Position[]) => line.map(([x, y]) => [y, x] as [number, number]);
const centroid = (f: Feature) => L.geoJSON(f).getBounds().getCenter();

/** Outer rings of the boundary as holes in a world polygon: dims everything outside the installation. */
function outsideMask(boundary: Feature): [number, number][][] {
  const g = boundary.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  return [WORLD, ...polys.map((p) => latlngs(p[0]))];
}

export function SiteMap() {
  const { code = "YTC" } = useParams();
  const label = useFunctionLabels();
  const [site, setSite] = useState<Site | null>(null);
  const [boundary, setBoundary] = useState<Feature | null>(null);
  const [layers, setLayers] = useState<FC | null>(null);
  const [roads, setRoads] = useState<FC | null>(null);
  const [roadSummary, setRoadSummary] = useState<RoadSummary[]>([]);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const sched = useSchedule(code);

  useEffect(() => {
    api<Site>(`/sites/${code}`).then(setSite).catch(() => setSite(null));
    api<FC>(`/geo/installations?code=${code}`).then((fc) => setBoundary((fc.features[0] as Feature) ?? null));
    api<FC>(`/geo/sites/${code}/layers`).then(setLayers);
    api<FC>(`/geo/sites/${code}/roads`).then(setRoads);
    api<RoadSummary[]>(`/geo/sites/${code}/roads/summary`).then(setRoadSummary).catch(() => setRoadSummary([]));
    api<Equipment[]>(`/sites/${code}/equipment`).then(setEquipment).catch(() => setEquipment([]));
    api<Person[]>(`/sites/${code}/personnel`).then(setPeople).catch(() => setPeople([]));
  }, [code]);

  useEffect(() => {
    if (map && boundary) map.fitBounds(L.geoJSON(boundary).getBounds(), { padding: [10, 10] });
  }, [map, boundary]);

  const feats = (layers?.features ?? []) as Feature[];
  const byKind = (k: string) => feats.filter((f) => f.properties.kind === k);
  const byId = useMemo(() => Object.fromEntries(feats.map((f) => [f.id as string, f])), [layers]);
  const complexes = byKind("range_complex");
  const segments = byKind("road_segment");

  const closedSegs = useMemo(() => new Map(sched.closures.map((c) => [c.segment_id, c])), [sched.closures]);
  const closedGates = useMemo(() => {
    const s = new Set<string>();
    for (const c of sched.closures) { if (c.gate_from) s.add(c.gate_from); if (c.gate_to) s.add(c.gate_to); }
    return s;
  }, [sched.closures]);
  const activeRanges = new Set(sched.active.map((e) => e.range_complex_id));

  const closureByRoad = useMemo(() => {
    const roadsClosed = [...new Set(sched.closures.map((c) => c.road))];
    return roadsClosed.map((road) => {
      const segs = segments.filter((s) => s.properties.road === road);
      const closed = sched.closures.filter((c) => c.road === road)
        .reduce((km, c) => km + (byId[c.segment_id]?.properties.length_km ?? c.length_km), 0);
      const full = roadSummary.find((r) => r.road === road)?.length_km
        ?? segs.reduce((km, s) => km + s.properties.length_km, 0);
      return { road, closed, full, gates: [...closedGates].filter((g) => byId[g]?.properties.road === road).length };
    });
  }, [sched.closures, segments, roadSummary, closedGates, byId]);

  const roadLabels = useMemo(() => {
    const groups: Record<string, { len: number; f: GeoJSON.Feature }> = {};
    for (const f of roads?.features ?? []) {
      const name = f.properties?.name as string;
      if (!name || f.geometry.type !== "LineString") continue;
      const len = L.geoJSON(f).getBounds().getNorthEast().distanceTo(L.geoJSON(f).getBounds().getSouthWest());
      if (!groups[name] || groups[name].len < len) groups[name] = { len, f };
    }
    return Object.entries(groups).filter(([, g]) => g.len > 2500).map(([name, g]) => {
      const coords = (g.f.geometry as GeoJSON.LineString).coordinates;
      const [x, y] = coords[Math.floor(coords.length / 2)];
      return { name, at: [y, x] as [number, number], major: g.f.properties?.mtfcc === "S1200" };
    });
  }, [roads]);

  const sel = selected ? byId[selected] : null;
  const selFuncs: string[] = sel?.properties.test_functions ?? [];
  const selEquipment = equipment.filter((e) => e.range_complex_id === selected);
  const selPeople = people
    .map((p) => ({ p, match: p.qualifications.filter((q) => selFuncs.includes(q)) }))
    .filter((x) => x.match.length > 0);

  const select = (id: string) => {
    setSelected(id);
    const f = byId[id];
    if (f && map) map.flyToBounds(L.geoJSON(f).getBounds().pad(0.4), { maxZoom: 13, duration: 0.8 });
  };

  return (
    <div className="map-layout">
      <div className="mapwrap">
        <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
          <defs>
            <pattern id="hatch-red" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)">
              <rect width="8" height="8" fill="rgba(224,32,27,0.18)" />
              <line x1="0" y1="0" x2="0" y2="8" stroke="#e0201b" strokeWidth="3" />
            </pattern>
            <pattern id="hatch-impact" patternUnits="userSpaceOnUse" width="14" height="14" patternTransform="rotate(-45)">
              <line x1="0" y1="0" x2="0" y2="14" stroke="rgba(224,32,27,0.55)" strokeWidth="1.5" />
            </pattern>
          </defs>
        </svg>
        <MapContainer center={[33.05, -114.2]} zoom={10} className="map" ref={setMap}>
          <BaseLayers initial="satellite" />
          <ZoomClass />
          <LayersControl position="topright">
            <LayersControl.Overlay checked name="Installation boundary (TIGER 2024)">
              <Pane name="boundary" style={{ zIndex: 380 }}><LayerGroup>{boundary && <MaskAndOutline boundary={boundary} />}</LayerGroup></Pane>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Range complexes">
              <Pane name="ranges" style={{ zIndex: 400 }}><LayerGroup>
                {complexes.map((f) => {
                  const t = f.properties.range_type as string;
                  const on = selected === f.id, live = activeRanges.has(f.id as string);
                  return (
                    <GeoJSON key={`${f.id}-${on}-${live}`} data={f}
                      style={{
                        color: rangeColor(t), weight: on || live ? 4 : 2,
                        dashArray: t === "impact_area" ? "8 6" : undefined,
                        fillColor: t === "impact_area" ? "url(#hatch-impact)" : rangeColor(t),
                        fillOpacity: t === "impact_area" ? 1 : on ? 0.3 : 0.14,
                        className: live ? "rc-live" : undefined,
                      }}
                      eventHandlers={{ click: () => select(f.id as string) }}
                      onEachFeature={(_, layer) => {
                        const b = L.geoJSON(f).getBounds(), small = b.getNorthEast().distanceTo(b.getSouthWest()) < 14000;
                        layer.bindTooltip(f.properties.name, { permanent: true, direction: "center", className: `rc-label rc-${t}${small ? " rc-small" : ""}` });
                      }} />
                  );
                })}
              </LayerGroup></Pane>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Target / impact areas">
              <Pane name="targets" style={{ zIndex: 410 }}><LayerGroup>
                {byKind("target_area").map((f) => (
                  <GeoJSON key={f.id as string} data={f}
                    style={{ color: "#e0201b", weight: 2, fillColor: "url(#hatch-red)", fillOpacity: 1 }}
                    onEachFeature={(_, layer) => layer.bindTooltip(`<b>${f.properties.name}</b><br/>Target / impact area`, { sticky: true })} />
                ))}
              </LayerGroup></Pane>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Public roads (TIGER 2024)">
              <Pane name="roads" style={{ zIndex: 420 }}><LayerGroup>
                {roads && <GeoJSON data={roads} style={(f) => f?.properties?.name === "US Hwy 95"
                  ? { color: "#1b1b1b", weight: 7, opacity: 0.7 }
                  : { color: "#f4f1e8", weight: f?.properties?.mtfcc === "S1200" ? 3 : 1.6, opacity: 0.85 }} />}
              </LayerGroup></Pane>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Road labels">
              <LayerGroup>
                {roadLabels.map((r) => (
                  <Marker key={r.name} position={r.at} interactive={false}
                    icon={L.divIcon({ className: `road-label${r.name === "US Hwy 95" ? " us95" : ""}`, html: `<span>${roadLabel(r.name)}</span>`, iconSize: [0, 0] })} />
                ))}
              </LayerGroup>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Gated road segments">
              <Pane name="segments" style={{ zIndex: 440 }}><LayerGroup>
                {segments.map((f) => {
                  const p = f.properties, closure = closedSegs.get(f.id as string);
                  const us95 = p.road === "US Hwy 95";
                  const color = sched.status !== "ok" ? (us95 ? "#ffbe2e" : "#ffe396") : closure ? "#ff2a1f" : "#2fe05a";
                  return (
                    <LayerGroup key={`${f.id}-${!!closure}-${sched.status}`}>
                    {us95 && <Polyline positions={latlngs((f.geometry as GeoJSON.LineString).coordinates)} interactive={false} pathOptions={{ color: "#fff", weight: 9, opacity: 0.9 }} />}
                    <Polyline positions={latlngs((f.geometry as GeoJSON.LineString).coordinates)}
                      pathOptions={{ color, weight: us95 ? 5 : 3.5, dashArray: closure ? "10 7" : undefined, lineCap: closure ? "butt" : "round" }}>
                      <Tooltip sticky>
                        <b>{roadLabel(p.name)}</b> · {p.length_km} km<br />
                        {p.gate_from ? byId[p.gate_from]?.properties.name : "Installation edge"} → {p.gate_to ? byId[p.gate_to]?.properties.name : "Installation edge"}
                        {closure && <><br /><b className="error">CLOSED</b> {fmtTime(closure.start)}–{fmtTime(closure.end)}<br />{closure.reason}</>}
                      </Tooltip>
                    </Polyline>
                    </LayerGroup>
                  );
                })}
              </LayerGroup></Pane>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Gates">
              <LayerGroup>
                {byKind("gate").map((f) => {
                  const [x, y] = (f.geometry as GeoJSON.Point).coordinates, closed = closedGates.has(f.id as string);
                  return (
                    <Marker key={`${f.id}-${closed}`} position={[y, x]} icon={gateIcon(closed)} zIndexOffset={500}>
                      <Tooltip direction="top">{f.properties.name} · {closed ? "CLOSED" : "Open"}</Tooltip>
                    </Marker>
                  );
                })}
              </LayerGroup>
            </LayersControl.Overlay>
            <LayersControl.Overlay checked name="Firing points">
              <LayerGroup>
                {byKind("firing_point").map((f) => {
                  const [x, y] = (f.geometry as GeoJSON.Point).coordinates;
                  return (
                    <Marker key={f.id as string} position={[y, x]} icon={firingPointIcon} zIndexOffset={600}
                      eventHandlers={{ click: () => select(f.properties.range_complex_id) }}>
                      <Tooltip direction="right" offset={[10, 0]}>{f.properties.name}</Tooltip>
                    </Marker>
                  );
                })}
                {sched.active.filter((e) => e.firing_point_id && e.target_area_id && byId[e.firing_point_id] && byId[e.target_area_id]).map((e) => {
                  const [x, y] = (byId[e.firing_point_id!].geometry as GeoJSON.Point).coordinates;
                  return (
                    <Polyline key={`gtl-${e.id}`} positions={[[y, x], centroid(byId[e.target_area_id!])]}
                      pathOptions={{ color: "#ff7a1a", weight: 2.5, dashArray: "2 8", className: "gtl" }}>
                      <Tooltip sticky>Gun-target line · {e.title}</Tooltip>
                    </Polyline>
                  );
                })}
              </LayerGroup>
            </LayersControl.Overlay>
          </LayersControl>
        </MapContainer>
        <Legend />
      </div>
      <aside className="map-panel">
        <div className="crumbs"><Link to="/atec/map">ATEC map</Link> / {code}</div>
        <h2>{site?.name ?? code}</h2>
        {site && <p className="hint">{site.parent}, {site.state} · {site.summary}</p>}

        <SchedulePanel sched={sched} closureByRoad={closureByRoad} rangeName={(id) => byId[id]?.properties.name ?? id} />

        {sel ? (
          <section className="panel-section">
            <button className="link back" onClick={() => setSelected(null)}>← All range complexes</button>
            <h3><span className="swatch" style={{ background: rangeColor(sel.properties.range_type) }} />{sel.properties.name}</h3>
            <p className="hint">{RANGE_STYLES[sel.properties.range_type]?.label}</p>
            <h4>Test functions</h4>
            <div className="tags">{selFuncs.map((f) => <span key={f} className="tag">{label(f)}</span>)}</div>
            <h4>Equipment on this range ({selEquipment.length})</h4>
            {selEquipment.length ? (
              <ul className="plain">{selEquipment.map((e) => <li key={e.id}><b>{e.name}</b> <span className="hint">· {e.category.replace(/_/g, " ")}</span></li>)}</ul>
            ) : <p className="hint">No equipment assigned to this range complex.</p>}
            <h4>Qualified personnel ({selPeople.length})</h4>
            {selPeople.length ? (
              <ul className="plain">{selPeople.map(({ p, match }) => (
                <li key={p.id}><b>{p.name}</b> <span className="hint">· {p.role}</span><br /><span className="hint">{match.map(label).join(", ")}</span></li>
              ))}</ul>
            ) : <p className="hint">No personnel qualified for these functions.</p>}
          </section>
        ) : (
          <section className="panel-section">
            <h3>Range complexes</h3>
            <ul className="rc-list">
              {complexes.map((f) => (
                <li key={f.id as string}>
                  <button onClick={() => select(f.id as string)}>
                    <span className="swatch" style={{ background: rangeColor(f.properties.range_type) }} />
                    <span>{f.properties.name}{activeRanges.has(f.id as string) && <span className="tag live">ACTIVE</span>}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
        <p className="hint sources">Boundary and roads: U.S. Census Bureau TIGER/Line 2024. Airfield footprint: OpenStreetMap contributors. Imagery: Esri, Maxar, Earthstar Geographics.</p>
      </aside>
    </div>
  );
}

/** Tags the map container so CSS can declutter small-range labels at overview zoom. */
function ZoomClass() {
  const map = useMapEvents({ zoomend: () => apply() });
  const apply = () => { map.getContainer().classList.toggle("z-low", map.getZoom() < 11); };
  useEffect(apply, [map]);
  return null;
}

function MaskAndOutline({ boundary }: { boundary: Feature }) {
  const mask = useMemo(() => outsideMask(boundary), [boundary]);
  return (
    <>
      <PolygonMask positions={mask} />
      <GeoJSON data={boundary} interactive={false} style={{ color: "#ffbe2e", weight: 3, fill: false, dashArray: "1 0" }} />
    </>
  );
}

function PolygonMask({ positions }: { positions: [number, number][][] }) {
  return <Polygon positions={positions} interactive={false} pathOptions={{ stroke: false, fillColor: "#0b1a2e", fillOpacity: 0.5 }} />;
}

interface SchedProps {
  sched: ReturnType<typeof useSchedule>;
  closureByRoad: { road: string; closed: number; full: number; gates: number }[];
  rangeName: (id: string) => string;
}

function SchedulePanel({ sched, closureByRoad, rangeName }: SchedProps) {
  const t = toMs(sched.at);
  const step = 30 * 60_000;
  return (
    <section className="panel-section schedule-box">
      <h3>Range schedule overlay</h3>
      {sched.status === "unavailable" ? (
        <p className="unavailable">Schedule service unavailable. Range, road and gate layers remain current.</p>
      ) : (
        <>
          <label htmlFor="at">Date / time (local range time)</label>
          <input id="at" type="datetime-local" value={sched.at.slice(0, 16)} onChange={(e) => e.target.value && sched.setAt(`${e.target.value}:00`)} />
          <input type="range" aria-label="Schedule time" min={sched.window.min} max={sched.window.max} step={step} value={Math.round(t / step) * step}
            onChange={(e) => sched.setAt(toIso(Number(e.target.value)))} />
          <div className="slider-scale hint"><span>{fmtTime(toIso(sched.window.min))}</span><span>{fmtTime(toIso(sched.window.max))}</span></div>
          <h4>Active events ({sched.active.length})</h4>
          {sched.active.length ? (
            <ul className="plain">{sched.active.map((e) => (
              <li key={e.id}><b>{e.title}</b><br /><span className="hint">{rangeName(e.range_complex_id)} · {fmtTime(e.start)}–{fmtTime(e.end)}{e.weapon_class !== "none" && ` · ${e.weapon_class.replace(/_/g, " ")}`}</span></li>
            ))}</ul>
          ) : <p className="hint">No events at this time.</p>}
          <h4>Road closures</h4>
          {closureByRoad.length ? closureByRoad.map((r) => (
            <div key={r.road} className="closure-stat">
              <b>{roadLabel(r.road)}:</b> {r.closed.toFixed(1)} km closed (gated) vs {r.full.toFixed(1)} km without gates
              <div className="bar"><div style={{ width: `${Math.min(100, (100 * r.closed) / (r.full || 1))}%` }} /></div>
              <span className="hint">{r.gates} gate{r.gates === 1 ? "" : "s"} closed · {(r.full - r.closed).toFixed(1)} km stays open</span>
            </div>
          )) : <p className="hint">All gated roads open.</p>}
        </>
      )}
    </section>
  );
}

function Legend() {
  const [open, setOpen] = useState(true);
  return (
    <div className="legend">
      <button className="legend-toggle" onClick={() => setOpen(!open)}>{open ? "Legend ▾" : "Legend ▸"}</button>
      {open && (
        <ul>
          {Object.entries(RANGE_STYLES).filter(([k]) => k !== "impact_area").map(([k, v]) => (
            <li key={k}><span className="swatch" style={{ background: v.color }} />{v.label}</li>
          ))}
          <li><span className="swatch hatch-impact" />Impact area (range complex)</li>
          <li><span className="swatch hatch" />Target / impact area</li>
          <li><span className="icon" dangerouslySetInnerHTML={{ __html: FIRING_POINT_SVG }} />Firing point</li>
          <li><span className="icon" dangerouslySetInnerHTML={{ __html: gateSvg(false) }} />Gate (open)</li>
          <li><span className="icon" dangerouslySetInnerHTML={{ __html: gateSvg(true) }} />Gate (closed)</li>
          <li><span className="line us95" />US-95 gated segment</li>
          <li><span className="line open" />Road segment open</li>
          <li><span className="line closed" />Road segment closed</li>
          <li><span className="line road" />Public road (TIGER 2024)</li>
          <li><span className="line boundary" />Installation boundary</li>
        </ul>
      )}
    </div>
  );
}
