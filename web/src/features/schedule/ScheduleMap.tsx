import { useEffect, useMemo } from "react";
import L from "leaflet";
import { CircleMarker, GeoJSON, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { Layer, MapFocus } from "./model";

function FitTo({ geom }: { geom?: GeoJSON.Geometry | null }) {
  const map = useMap();
  useEffect(() => {
    if (geom) map.fitBounds(L.geoJSON(geom).getBounds(), { padding: [20, 20] });
  }, [geom, map]);
  return null;
}

const pt = (f: Layer) => { const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates; return [lat, lon] as [number, number]; };

export default function ScheduleMap({ layers, focus }: { layers: Layer[]; focus: MapFocus | null }) {
  const closed = useMemo(() => new Set(focus?.closures.map((c) => c.segment_id)), [focus]);
  const of = (kind: string) => layers.filter((f) => f.properties.kind === kind);
  const fc = (features: Layer[]): GeoJSON.FeatureCollection => ({ type: "FeatureCollection", features });
  const segments = of("road_segment");
  const key = `${focus?.label}-${[...closed].join(",")}`;
  return (
    <MapContainer center={[33.08, -114.15]} zoom={10} className="sched-map">
      <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        attribution="Esri, Maxar, Earthstar Geographics" maxZoom={19} />
      <GeoJSON data={fc(of("range_complex"))} style={{ color: "#ffffff", weight: 1, fillOpacity: 0.05, dashArray: "4 4" }}
        onEachFeature={(f, l) => l.bindTooltip(f.properties.name)} />
      <GeoJSON data={fc(of("target_area"))} style={{ color: "#ffbe2e", weight: 1, fillOpacity: 0.15 }}
        onEachFeature={(f, l) => l.bindTooltip(f.properties.name)} />
      {focus?.sdz && <GeoJSON key={`sdz-${key}`} data={focus.sdz} style={{ color: "#ff7a00", weight: 2, fillOpacity: 0.25 }} />}
      <GeoJSON key={`roads-${key}`} data={fc(segments)}
        style={(f) => ({ color: closed.has(String(f?.id)) ? "#e52207" : "#00e03a", weight: closed.has(String(f?.id)) ? 6 : 4 })}
        onEachFeature={(f, l) => l.bindTooltip(`${f.properties.name}: ${closed.has(String(f.id)) ? "CLOSED" : "open"} (${f.properties.length_km} km)`)} />
      {of("gate").map((g) => (
        <CircleMarker key={String(g.id)} center={pt(g)} radius={5} pathOptions={{ color: "#112e51", fillColor: "#fff", fillOpacity: 1, weight: 2 }}>
          <Tooltip>{g.properties.name}</Tooltip>
        </CircleMarker>
      ))}
      {of("firing_point").map((f) => (
        <CircleMarker key={String(f.id)} center={pt(f)} radius={f.id === focus?.firing_point_id ? 8 : 5}
          pathOptions={{ color: "#fff", fillColor: f.id === focus?.firing_point_id ? "#e52207" : "#565c65", fillOpacity: 1, weight: 2 }}>
          <Tooltip>{f.properties.name}</Tooltip>
        </CircleMarker>
      ))}
      <FitTo geom={focus?.sdz} />
    </MapContainer>
  );
}
