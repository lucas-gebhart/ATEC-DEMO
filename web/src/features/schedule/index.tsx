// WS4 owns this folder: range schedule (timeline), proposed-event check, closures panel.
import { useCallback, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { ProposedEvent, ScheduleCheck, Taxonomy } from "../../lib/types";
import type { Equipment, Layer, MapFocus, Person, ScheduleEventDetail } from "./model";
import { focusOf, km } from "./model";
import ProposeForm from "./ProposeForm";
import ScheduleMap from "./ScheduleMap";
import Timeline, { mondayOf } from "./Timeline";
import "./schedule.css";

const SITE = "YTC";
const DEFAULT_FORM: ProposedEvent = {
  site_code: SITE, range_complex_id: "rc-kofa", title: "155mm fuze lot acceptance", start: "2026-12-15T07:00", end: "2026-12-15T15:00",
  weapon_class: "155mm_howitzer", firing_point_id: "fp-k1", target_area_id: "ta-k-north", equipment_ids: [], personnel_ids: [],
};

export default function Schedule() {
  const { user } = useAuth();
  const [layers, setLayers] = useState<Layer[]>([]);
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [personnel, setPersonnel] = useState<Person[]>([]);
  const [events, setEvents] = useState<ScheduleEventDetail[]>([]);
  const [weekStart, setWeekStart] = useState<Date | null>(null);
  const [form, setForm] = useState<ProposedEvent>(DEFAULT_FORM);
  const [selected, setSelected] = useState<ScheduleEventDetail | null>(null);
  const [focus, setFocus] = useState<MapFocus | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [err, setErr] = useState("");

  const loadEvents = useCallback(() => api<ScheduleEventDetail[]>(`/schedule/events?site=${SITE}`).then((evs) => {
    setEvents(evs);
    setWeekStart((w) => w ?? mondayOf(new Date((evs.find((e) => new Date(e.end) >= new Date()) ?? evs[0])?.start ?? Date.now())));
  }), []);

  useEffect(() => {
    Promise.all([
      api<GeoJSON.FeatureCollection>(`/geo/sites/${SITE}/layers`).then((fc) => setLayers(fc.features as Layer[])),
      api<Taxonomy>("/taxonomy").then(setTaxonomy),
      api<Equipment[]>(`/sites/${SITE}/equipment`).then(setEquipment),
      api<Person[]>(`/sites/${SITE}/personnel`).then(setPersonnel),
      loadEvents(),
    ]).catch((e) => setErr(String(e)));
  }, [loadEvents]);

  const select = (e: ScheduleEventDetail) => { setSelected(e); setFocus(focusOf(`event-${e.id}`, e, e)); };
  const template = (e: ScheduleEventDetail) => {
    setForm({ site_code: e.site_code, range_complex_id: e.range_complex_id, title: `${e.title} (re-shoot)`, start: e.start, end: e.end,
      weapon_class: e.weapon_class, firing_point_id: e.firing_point_id ?? undefined, target_area_id: e.target_area_id ?? undefined,
      equipment_ids: e.equipment_ids, personnel_ids: e.personnel_ids });
    setFormKey((k) => k + 1);
    setFocus(null);
  };
  const onChecked = (c: ScheduleCheck | null) => { setSelected(null); setFocus(c ? focusOf("proposed", form, c) : null); };
  const canSchedule = user?.role === "g3" || user?.role === "range_scheduler";
  const ranges = layers.filter((f) => f.properties.kind === "range_complex");

  if (err) return <div className="card error">{err}</div>;
  return (
    <div className="sched">
      {weekStart && <Timeline weekStart={weekStart} setWeekStart={setWeekStart} ranges={ranges} events={events}
        selectedId={selected?.id} onSelect={select} onTemplate={template} />}
      <div className="sched-cols">
        <ProposeForm key={formKey} form={form} setForm={setForm} layers={layers} weapons={taxonomy?.weapon_classes ?? []} equipment={equipment}
          personnel={personnel} canSchedule={canSchedule} onChecked={onChecked}
          onScheduled={(ev) => { loadEvents(); select(ev); setWeekStart(mondayOf(new Date(ev.start))); }} />
        <div className="card sched-mapcard">
          <h2>Surface danger zone &amp; roads</h2>
          <p className="hint">
            {selected ? <>Event #{selected.id}: <b>{selected.title}</b> - {selected.closures.length
              ? <>closes {km(selected.closed_km_with_gates)} with gates ({km(selected.closed_km_without_gates)} without)</> : "no road closures"}
              {" "}<button className="link sched-link" onClick={() => template(selected)}>Use as template</button></>
              : focus ? "Proposed event (from Check)." : "Run Check on a proposed event, or click an event in the schedule."}
          </p>
          <div className="sched-legend">
            <span><i style={{ background: "#ff7a00" }} />SDZ</span><span><i style={{ background: "#e52207" }} />Closed segment</span>
            <span><i style={{ background: "#00e03a" }} />Open segment</span><span><i className="dot" />Gate</span>
          </div>
          <ScheduleMap layers={layers} focus={focus} />
        </div>
      </div>
    </div>
  );
}
