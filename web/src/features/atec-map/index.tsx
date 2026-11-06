// WS3 owns this folder: ATEC national map and site (YTC) detail map.
import { useEffect, useState } from "react";
import { GeoJSON, LayersControl, MapContainer, Marker, Popup } from "react-leaflet";
import { Link, useParams } from "react-router-dom";
import { api } from "../../lib/api";
import type { Site } from "../../lib/types";
import { BaseLayers } from "./BaseLayers";

export function AtecMap() {
  const [sites, setSites] = useState<Site[]>([]);
  useEffect(() => { api<Site[]>("/sites").then(setSites); }, []);
  return (
    <div className="mapwrap">
      <MapContainer center={[38, -105]} zoom={4} className="map">
        <BaseLayers />
        {sites.map((s) => (
          <Marker key={s.code} position={[s.lat, s.lon]}>
            <Popup><b>{s.name}</b><br />{s.summary}<br />{s.has_detail && <Link to={`/atec/sites/${s.code}`}>Open site map</Link>}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}

export function SiteMap() {
  const { code = "YTC" } = useParams();
  const [layers, setLayers] = useState<GeoJSON.FeatureCollection | null>(null);
  const [roads, setRoads] = useState<GeoJSON.FeatureCollection | null>(null);
  useEffect(() => {
    api<GeoJSON.FeatureCollection>(`/geo/sites/${code}/layers`).then(setLayers);
    api<GeoJSON.FeatureCollection>(`/geo/sites/${code}/roads`).then(setRoads);
  }, [code]);
  return (
    <div className="mapwrap">
      <MapContainer center={[33.05, -114.2]} zoom={10} className="map">
        <BaseLayers />
        <LayersControl position="topright">
          {roads && <LayersControl.Overlay checked name="Roads (TIGER)"><GeoJSON data={roads} style={{ color: "#f2c14e", weight: 2 }} /></LayersControl.Overlay>}
          {layers && <LayersControl.Overlay checked name="Range layers"><GeoJSON data={layers} style={{ color: "#4ea1f2", weight: 2 }} /></LayersControl.Overlay>}
        </LayersControl>
      </MapContainer>
    </div>
  );
}

