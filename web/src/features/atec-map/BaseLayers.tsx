import { LayersControl, TileLayer } from "react-leaflet";

export function BaseLayers() {
  return (
    <LayersControl position="topleft">
      <LayersControl.BaseLayer checked name="Satellite (Esri World Imagery)">
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" attribution="Esri, Maxar, Earthstar Geographics" maxZoom={19} />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Topographic (Esri)">
        <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}" attribution="Esri" />
      </LayersControl.BaseLayer>
      <LayersControl.BaseLayer name="Streets (OpenStreetMap)">
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
      </LayersControl.BaseLayer>
    </LayersControl>
  );
}
