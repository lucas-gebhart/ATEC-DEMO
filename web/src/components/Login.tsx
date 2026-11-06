import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Persona } from "../lib/types";

export const homeFor = (p: Persona) => (p.role === "industry" ? "/industry" : p.role === "g3" ? "/g3" : "/atec/map");

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [username, setUsername] = useState("acme.industry");
  const [password, setPassword] = useState("demo");
  const [err, setErr] = useState("");
  useEffect(() => { api<Persona[]>("/auth/personas").then(setPersonas); }, []);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { nav(homeFor(await login(username, password))); } catch (x) { setErr(String(x)); }
  };
  return (
    <form className="card narrow" onSubmit={submit}>
      <h1>Sign in</h1>
      <label>Account<select value={username} onChange={(e) => setUsername(e.target.value)}>
        {personas.map((p) => <option key={p.username} value={p.username}>{p.display}</option>)}
      </select></label>
      <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      <p className="hint">Demo password for every account: <code>demo</code></p>
      {err && <p className="error">{err}</p>}
      <button className="primary" type="submit">Sign in</button>
    </form>
  );
}
