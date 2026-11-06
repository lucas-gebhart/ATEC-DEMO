import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import "./lib/leafletIcons";
import Layout from "./components/Layout";
import Login, { homeFor } from "./components/Login";
import { ATEC_ROLES, AuthProvider, useAuth } from "./lib/auth";
import type { Role } from "./lib/types";
import IndustryHome from "./features/industry";
import G3Queue from "./features/g3";
import { AtecMap, SiteMap } from "./features/atec-map";
import Schedule from "./features/schedule";

function Guard({ roles, children }: { roles: Role[]; children: React.ReactElement }) {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" />;
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user)} />;
  return children;
}

function Home() {
  const { user, ready } = useAuth();
  if (!ready) return null;
  return <Navigate to={user ? homeFor(user) : "/login"} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/industry/*" element={<Guard roles={["industry"]}><IndustryHome /></Guard>} />
            <Route path="/g3/*" element={<Guard roles={["g3"]}><G3Queue /></Guard>} />
            <Route path="/atec/map" element={<Guard roles={ATEC_ROLES}><AtecMap /></Guard>} />
            <Route path="/atec/sites/:code" element={<Guard roles={ATEC_ROLES}><SiteMap /></Guard>} />
            <Route path="/atec/schedule" element={<Guard roles={ATEC_ROLES}><Schedule /></Guard>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  </React.StrictMode>,
);
