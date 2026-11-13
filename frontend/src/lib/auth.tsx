import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, auth } from "./api";

export type Me = { role: string; name?: string; email?: string; school?: string; programme?: string; semester?: number;
  academic_year?: string; attendance?: { overall_pct: number; subject_wise_approx?: Record<string, number> };
  current_courses?: { code: string; name: string; credits: number; category: string }[];
  progress?: { credits_earned: number; credits_required: number; progress_to_graduation_pct: number; last_result?: { cgpa: number; sgpa: number } } };

/** `ready` is false until the stored token has been checked, so pages don't redirect a logged-in user to /login on refresh. */
const Ctx = createContext<{ me: Me; ready: boolean; login: (e: string, p: string) => Promise<void>; logout: () => void; reload: () => Promise<void> }>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>({ role: "prospective" });
  const [ready, setReady] = useState(!auth.token);  // nothing to check without a stored token
  const reload = () => api.get<Me>("/me").then(setMe)
    .catch(() => { auth.set(null); setMe({ role: "prospective" }); })
    .finally(() => setReady(true));
  useEffect(() => { if (auth.token) reload(); }, []);
  const login = async (email: string, password: string) => {
    const r = await api.post<{ token: string }>("/auth/login", { email, password });
    auth.set(r.token);
    await reload();  // load the profile before the caller navigates to a role-protected page
  };
  const logout = () => { auth.set(null); setMe({ role: "prospective" }); };
  return <Ctx.Provider value={{ me, ready, login, logout, reload }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
