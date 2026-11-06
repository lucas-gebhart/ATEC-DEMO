// WS2: G3 review queue and recommendation detail (approve / edit / reject).
import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import { api } from "../../lib/api";
import Detail from "./Detail";
import Queue from "./Queue";
import { useRefData } from "./refdata";
import "./g3.css";

function EngineBanner() {
  const [devin, setDevin] = useState<boolean | null>(null);
  useEffect(() => { api<{ devin_planning_enabled: boolean }>("/health").then((h) => setDevin(h.devin_planning_enabled)); }, []);
  if (devin === null) return null;
  return (
    <div className={`g3-banner ${devin ? "on" : ""}`}>
      {devin ? "Planning engine: Devin session (rules matcher fallback)"
        : "Planning engine: Rules matcher (Devin session planning disabled - no service key)"}
    </div>
  );
}

export default function G3() {
  const ref = useRefData();
  return (
    <>
      <EngineBanner />
      {!ref ? <p className="hint">Loading...</p> : (
        <Routes>
          <Route index element={<Queue refs={ref} />} />
          <Route path="requests/:id" element={<Detail refs={ref} />} />
        </Routes>
      )}
    </>
  );
}
