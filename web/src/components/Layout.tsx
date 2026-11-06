import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ATEC_ROLES, useAuth } from "../lib/auth";

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const atec = user && ATEC_ROLES.includes(user.role);
  return (
    <div className="app">
      <div className="usa-banner-lite">An official demonstration environment - not a U.S. government system</div>
      <header className="topbar">
        <div className="brand"><span className="seal">ATEC</span> Test Planning &amp; Range Scheduling</div>
        <nav>
          {user?.role === "industry" && <><NavLink to="/industry" end>My requests</NavLink><NavLink to="/industry/new">New test request</NavLink><NavLink to="/industry/company">Company profile</NavLink></>}
          {user?.role === "g3" && <NavLink to="/g3">G3 review queue</NavLink>}
          {atec && <><NavLink to="/atec/map">ATEC map</NavLink><NavLink to="/atec/sites/YTC">YTC</NavLink><NavLink to="/atec/schedule">Range schedule</NavLink></>}
        </nav>
        {user && <div className="who">{user.display} <button className="link" onClick={() => { logout(); nav("/login"); }}>Sign out</button></div>}
      </header>
      <main><Outlet /></main>
    </div>
  );
}
