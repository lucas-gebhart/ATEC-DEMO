import { LayersControl, TileLayer } from "react-leaflet";

export type BaseName = "satellite" | "topo" | "streets";

export function BaseLayers({ initial = "satellite" }: { initial?: BaseName }) {
  return (
    <LayersControl position="topleft">
      <LayersControl.BaseLayer checked={initial === "satellite"} name="Satellite (Esri World Imagery)">
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution="Esri, Maxar, Earthstar Geographics" maxZoom={19} />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer checked={initial === "topo"} name="Topographic (Esri)">
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}" attribution="Esri" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer checked={initial === "streets"} name="Streets (OpenStreetMap)">
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
      </LayersControl.BaseLayer>
    </LayersControl>
  );
}

export const TOPO_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}";
