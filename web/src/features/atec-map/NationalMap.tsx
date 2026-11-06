import L from "leaflet";
import { useEffect, useMemo, useState } from "react";
import { GeoJSON, MapContainer, Marker, TileLayer, Tooltip } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import { api } from "../../lib/api";
import type { Site } from "../../lib/types";
import { BaseLayers, TOPO_URL } from "./BaseLayers";
import { type FC, sitePinIcon, useFunctionLabels } from "./shared";

const VIEWS = {
  CONUS: L.latLngBounds([24.0, -125.5], [49.8, -66.0]),
  Alaska: L.latLngBounds([54.0, -168.0], [71.5, -129.0]),
  Hawaii: L.latLngBounds([18.7, -160.6], [22.4, -154.6]),
};
type View = keyof typeof VIEWS;
const INSETS: { view: View; center: [number, number]; zoom: number }[] = [
  { view: "Alaska", center: [63.2, -150], zoom: 2 },
  { view: "Hawaii", center: [20.7, -157.4], zoom: 5 },
];
const boundaryStyle = { color: "#ffbe2e", weight: 2, fillColor: "#ffbe2e", fillOpacity: 0.25 };

export function AtecMap() {
  const nav = useNavigate();
  const label = useFunctionLabels();
  const [sites, setSites] = useState<Site[]>([]);
  const [boundaries, setBoundaries] = useState<FC | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [map, setMap] = useState<L.Map | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Site[]>("/sites").then(setSites).catch((e) => setErr(String(e)));
    api<FC>("/geo/installations").then(setBoundaries).catch(() => setBoundaries(null));
  }, []);

  const byCode = useMemo(() => Object.fromEntries(sites.map((s) => [s.code, s])), [sites]);
  const boundsFor = (code: string) => {
    const f = boundaries?.features.find((b) => b.properties?.code === code);
    return f ? L.geoJSON(f).getBounds() : null;
  };
  const focus = (s: Site) => {
    setSelected(s.code);
    const b = boundsFor(s.code);
    if (b) map?.flyToBounds(b.pad(0.6), { maxZoom: 9, duration: 1.2 });
    else map?.flyTo([s.lat, s.lon], 8, { duration: 1.2 });
  };
  const open = (s: Site) => (s.has_detail ? nav(`/atec/sites/${s.code}`) : focus(s));
  const jump = (v: View) => { map?.flyToBounds(VIEWS[v], { duration: 1 }); };

  const pins = (sel: string | null, onClick: (s: Site) => void, tooltips = true) =>
    sites.map((s) => (
      <Marker key={s.code} position={[s.lat, s.lon]} icon={sitePinIcon(s.code, s.has_detail, sel === s.code)}
        zIndexOffset={s.has_detail ? 1000 : 0} eventHandlers={{ click: () => onClick(s) }}>
        {tooltips && <Tooltip direction="top"><b>{s.name}</b><br />{s.parent}, {s.state}{s.has_detail && <><br /><i>Click to open site map</i></>}</Tooltip>}
      </Marker>
    ));

  const sel = selected ? byCode[selected] : null;
  return (
    <div className="map-layout">
      <div className="mapwrap">
        <MapContainer bounds={VIEWS.CONUS} className="map" ref={setMap} worldCopyJump>
          <BaseLayers initial="topo" />
          {boundaries && (
            <GeoJSON data={boundaries} style={() => boundaryStyle}
              onEachFeature={(f, layer) => layer.on("click", () => { const s = byCode[f.properties?.code]; if (s) open(s); })} key={sites.length} />
          )}
          {pins(selected, open)}
        </MapContainer>
        <div className="view-buttons" role="group" aria-label="Jump to region">
          {(Object.keys(VIEWS) as View[]).map((v) => <button key={v} onClick={() => jump(v)}>{v}</button>)}
        </div>
        <div className="insets">
          {INSETS.map((i) => (
            <div key={i.view} className="inset" title={`Jump to ${i.view}`}>
              <div className="inset-title">{i.view}</div>
              <MapContainer center={i.center} zoom={i.zoom} className="map" zoomControl={false} dragging={false}
                scrollWheelZoom={false} doubleClickZoom={false} touchZoom={false} keyboard={false} attributionControl={false}>
                <TileLayer url={TOPO_URL} />
                {pins(selected, (s) => { jump(i.view); focus(s); }, false)}
              </MapContainer>
              <button className="inset-hit" aria-label={`Jump to ${i.view}`} onClick={() => jump(i.view)} />
            </div>
          ))}
        </div>
      </div>
      <aside className="map-panel">
        <h2>ATEC test centers</h2>
        <p className="hint">U.S. Army Test and Evaluation Command sites. Boundaries: U.S. Census Bureau TIGER/Line 2024 military installations.</p>
        {err && <p className="error">{err}</p>}
        <ul className="site-list">
          {sites.map((s) => (
            <li key={s.code} className={selected === s.code ? "active" : ""}>
              <button className="site-row" onClick={() => focus(s)}>
                <span className={`site-code${s.has_detail ? " detail" : ""}`}>{s.code}</span>
                <span><b>{s.name}</b><br /><span className="hint">{s.parent}, {s.state}</span></span>
              </button>
              {selected === s.code && (
                <div className="site-detail">
                  <p>{s.summary}</p>
                  <div className="tags">{s.test_functions.map((f) => <span key={f} className="tag">{label(f)}</span>)}</div>
                  {s.has_detail
                    ? <button className="primary" onClick={() => nav(`/atec/sites/${s.code}`)}>Open {s.code} site map</button>
                    : <p className="hint">Detailed range map not yet available for this site.</p>}
                </div>
              )}
            </li>
          ))}
        </ul>
        {sel && !boundsFor(sel.code) && <p className="hint">No TIGER installation boundary for {sel.name}; marker shows site location.</p>}
      </aside>
    </div>
  );
}
