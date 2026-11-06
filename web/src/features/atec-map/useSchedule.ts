import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { RoadClosure, ScheduleEvent } from "../../lib/types";
import { toIso, toMs } from "./shared";

const HOUR = 3600_000;
const DAY = 24 * HOUR;

export type ScheduleStatus = "loading" | "ok" | "unavailable";

/** Schedule overlay data from WS4 (/api/schedule/*). Any failure degrades to "unavailable". */
export function useSchedule(site: string) {
  const [events, setEvents] = useState<ScheduleEvent[]>([]);
  const [status, setStatus] = useState<ScheduleStatus>("loading");
  const [at, setAt] = useState<string>(() => toIso(Math.floor(Date.now() / HOUR) * HOUR));
  const [closures, setClosures] = useState<RoadClosure[]>([]);

  useEffect(() => {
    api<ScheduleEvent[]>(`/schedule/events?site=${site}`)
      .then((evs) => {
        const list = Array.isArray(evs) ? [...evs].sort((a, b) => toMs(a.start) - toMs(b.start)) : [];
        setEvents(list);
        setStatus("ok");
        const first = list.find((e) => e.weapon_class !== "none") ?? list[0];
        if (first) setAt(toIso(toMs(first.start) + HOUR));
      })
      .catch(() => setStatus("unavailable"));
  }, [site]);

  useEffect(() => {
    if (status !== "ok") return;
    const t = setTimeout(() => {
      api<RoadClosure[]>(`/schedule/closures?at=${encodeURIComponent(at)}`)
        .then((c) => setClosures(Array.isArray(c) ? c : []))
        .catch(() => { setClosures([]); setStatus("unavailable"); });
    }, 200);
    return () => clearTimeout(t);
  }, [at, status]);

  const window = useMemo(() => {
    const now = toMs(at);
    if (!events.length) return { min: now - DAY, max: now + 6 * DAY };
    const min = Math.floor(Math.min(...events.map((e) => toMs(e.start))) / DAY) * DAY;
    const max = Math.ceil(Math.max(...events.map((e) => toMs(e.end))) / DAY) * DAY;
    return { min: Math.min(min, now), max: Math.max(max, now) };
  }, [events, at]);

  const active = useMemo(() => events.filter((e) => toMs(e.start) <= toMs(at) && toMs(at) < toMs(e.end)), [events, at]);

  return { status, events, active, closures, at, setAt, window };
}
