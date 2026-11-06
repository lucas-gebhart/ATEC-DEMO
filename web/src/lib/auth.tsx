import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, post, setToken } from "./api";
import type { Persona, Role } from "./types";

interface AuthCtx { user: Persona | null; ready: boolean; login: (u: string, p: string) => Promise<Persona>; logout: () => void }
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
export const useAuth = () => useContext(Ctx);
export const ATEC_ROLES: Role[] = ["g3", "range_scheduler", "atec_viewer"];

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Persona | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!getToken()) return setReady(true);
    api<Persona>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
  }, []);
  const login = async (username: string, password: string) => {
    const r = await post<{ token: string; user: Persona }>("/auth/login", { username, password });
    setToken(r.token);
    setUser(r.user);
    return r.user;
  };
  const logout = () => { setToken(null); setUser(null); };
  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>;
}
