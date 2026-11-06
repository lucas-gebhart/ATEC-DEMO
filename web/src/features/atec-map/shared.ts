import L from "leaflet";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Taxonomy } from "../../lib/types";

export type FC = GeoJSON.FeatureCollection;
export type Feature = GeoJSON.Feature<GeoJSON.Geometry, Record<string, any>>;

export interface Equipment { id: string; site_code: string; name: string; category: string; supports_functions: string[]; range_complex_id?: string | null }
export interface Person { id: string; site_code: string; name: string; role: string; qualifications: string[] }
export interface RoadSummary { road: string; length_km: number; segments: string[]; gates: string[] }

export function useFunctionLabels() {
  const [labels, setLabels] = useState<Record<string, string>>({});
  useEffect(() => {
    api<Taxonomy>("/taxonomy")
      .then((t) => setLabels(Object.fromEntries(t.test_functions.map((f) => [f.code, f.label]))))
      .catch(() => setLabels({}));
  }, []);
  return (code: string) => labels[code] ?? code.replace(/_/g, " ");
}

export const roadLabel = (name: string) => name.replace(/^US Hwy /, "US-");

export const RANGE_STYLES: Record<string, { color: string; label: string }> = {
  artillery: { color: "#ff7a1a", label: "Artillery firing range" },
  impact_area: { color: "#e0201b", label: "Impact area" },
  aviation: { color: "#38b6ff", label: "Aviation / air-to-ground range" },
  airfield: { color: "#f5f5f5", label: "Army airfield" },
  mobility: { color: "#ffbe2e", label: "Mobility / automotive courses" },
  c_ied: { color: "#b07cff", label: "Counter-IED / survivability" },
  environmental: { color: "#29d3b5", label: "Environmental exposure" },
  airdrop: { color: "#7ddc3c", label: "Airdrop / drop zones" },
};
export const rangeColor = (t: string) => RANGE_STYLES[t]?.color ?? "#4ea1f2";

const svg = (body: string, size: number) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24">${body}</svg>`;

export const FIRING_POINT_SVG = svg('<path d="M12 2 L22 21 H2 Z" fill="#ff7a1a" stroke="#1b1b1b" stroke-width="2"/><circle cx="12" cy="15" r="2.6" fill="#1b1b1b"/>', 22);
export const gateSvg = (closed: boolean) =>
  svg(
    `<rect x="1" y="5" width="22" height="14" rx="3" fill="${closed ? "#b50909" : "#00a91c"}" stroke="#fff" stroke-width="1.5"/>` +
      '<rect x="4" y="8" width="2" height="8" fill="#fff"/><rect x="18" y="8" width="2" height="8" fill="#fff"/>' +
      (closed ? '<rect x="6" y="10.5" width="12" height="3" fill="#fff"/>' : '<path d="M6 12 L16 7" stroke="#fff" stroke-width="2.2"/>'),
    22,
  );

export const firingPointIcon = L.divIcon({ className: "map-icon", html: FIRING_POINT_SVG, iconSize: [22, 22], iconAnchor: [11, 13] });
export const gateIcon = (closed: boolean) => L.divIcon({ className: "map-icon", html: gateSvg(closed), iconSize: [22, 22], iconAnchor: [11, 11] });
export const sitePinIcon = (code: string, detail: boolean, selected: boolean) =>
  L.divIcon({
    className: "map-icon",
    html: `<div class="site-pin${detail ? " detail" : ""}${selected ? " selected" : ""}"><span>${code}</span></div>`,
    iconSize: [46, 46],
    iconAnchor: [23, 44],
    tooltipAnchor: [0, -40],
  });

/** Naive (zone-less) ISO strings as used by the seed schedule, handled as UTC so nothing shifts. */
export const toMs = (iso: string) => Date.parse(iso.length <= 19 ? `${iso}Z` : iso);
export const toIso = (ms: number) => new Date(ms).toISOString().slice(0, 19);
export const fmtTime = (iso: string) => {
  const d = new Date(toMs(iso));
  return `${d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })} ${d.toISOString().slice(11, 16)}`;
};
