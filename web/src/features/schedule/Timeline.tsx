import type { Layer, ScheduleEventDetail } from "./model";
import { hhmm } from "./model";

const DAY = 86400000;
const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const mondayOf = (d: Date) => { const m = new Date(d.getFullYear(), d.getMonth(), d.getDate()); m.setDate(m.getDate() - ((m.getDay() + 6) % 7)); return m; };

interface Props {
  weekStart: Date; setWeekStart: (d: Date) => void; ranges: Layer[]; events: ScheduleEventDetail[];
  selectedId?: number; onSelect: (e: ScheduleEventDetail) => void; onTemplate: (e: ScheduleEventDetail) => void;
}

export default function Timeline({ weekStart, setWeekStart, ranges, events, selectedId, onSelect, onTemplate }: Props) {
  const days = Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * DAY));
  const onDay = (e: ScheduleEventDetail, d: Date) => new Date(e.start) < new Date(d.getTime() + DAY) && new Date(e.end) > d;
  const week = events.filter((e) => days.some((d) => onDay(e, d)));
  return (
    <div className="card">
      <div className="sched-head">
        <h1>YTC range schedule</h1>
        <div className="sched-weeknav">
          <button className="secondary" onClick={() => setWeekStart(new Date(weekStart.getTime() - 7 * DAY))}>&larr; Prev</button>
          <strong>Week of {weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}</strong>
          <button className="secondary" onClick={() => setWeekStart(new Date(weekStart.getTime() + 7 * DAY))}>Next &rarr;</button>
        </div>
      </div>
      <table className="sched-grid">
        <thead>
          <tr><th>Range complex</th>{days.map((d) => <th key={iso(d)}>{d.toLocaleDateString(undefined, { weekday: "short", month: "numeric", day: "numeric" })}</th>)}</tr>
        </thead>
        <tbody>
          {ranges.map((r) => (
            <tr key={String(r.id)}>
              <th>{r.properties.name}</th>
              {days.map((d) => (
                <td key={iso(d)}>
                  {week.filter((e) => e.range_complex_id === r.id && onDay(e, d)).map((e) => (
                    <button key={e.id} className={`sched-chip${e.sdz ? " live" : ""}${e.id === selectedId ? " sel" : ""}`} onClick={() => onSelect(e)}
                      title={`${e.title}\n${e.start} - ${e.end}`}>
                      <b>{hhmm(e.start)}-{hhmm(e.end)}</b> {e.title}
                      {e.closures.length > 0 && <span className="sched-road">{e.closures.length} road seg closed</span>}
                    </button>
                  ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {week.length > 0 && (
        <details className="sched-list">
          <summary>{week.length} event(s) this week</summary>
          <table>
            <thead><tr><th>#</th><th>Event</th><th>Range</th><th>Window</th><th>Weapon</th><th>Road closed (with / without gates)</th><th /></tr></thead>
            <tbody>
              {week.map((e) => (
                <tr key={e.id}>
                  <td>{e.id}</td><td>{e.title}</td><td>{ranges.find((r) => r.id === e.range_complex_id)?.properties.name}</td>
                  <td>{e.start.replace("T", " ").slice(0, 16)} - {hhmm(e.end)}</td><td>{e.weapon_class}</td>
                  <td>{e.closed_km_with_gates.toFixed(2)} / {e.closed_km_without_gates.toFixed(2)} km</td>
                  <td><button className="link sched-link" onClick={() => onTemplate(e)}>Use as template</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}
