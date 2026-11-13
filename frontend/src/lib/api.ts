// Thin API client. All calls go to /api (proxied to FastAPI by Vite).
export type User = { id: number; name: string; role: string; email: string };

const TOKEN_KEY = "bennett_one_token";
export const auth = {
  get token() { try { return localStorage.getItem(TOKEN_KEY); } catch { return null; } },
  set(token: string | null) {
    try { if (token) localStorage.setItem(TOKEN_KEY, token); else localStorage.removeItem(TOKEN_KEY); } catch { /* private mode */ }
  },
};

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  const r = await fetch(`/api${path}`, { ...init, headers });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
}

export const api = {
  get: <T,>(p: string) => req<T>(p),
  post: <T,>(p: string, body: unknown) => req<T>(p, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body) }),
};

export type Citation = { tag: string; chunk_id?: number; title: string; page?: number | null; section?: string | null;
  url: string; school_id?: string; academic_year?: string; version?: string };
/** Numbers the rule engine computed (Best-of-3, thresholds...). Known keys are typed; the rest stay opaque. */
export type Computed = { note?: string; threshold_pct?: number; best_of_3?: number | null; subjects_used?: string[]; [key: string]: unknown };
export type Check = { name: string; passed: boolean | null; detail: string };
export type RuleResult = { status: string; checks: Check[]; missing: string[]; computed: Computed;
  sources: { title: string; url: string; quote?: string; page?: number }[]; programme?: string };
export type ChatResult = { answer: string; citations: Citation[]; status: string | null; rule_result: RuleResult | null;
  warnings: string[]; intent: string; facts?: Record<string, unknown> };

/** Streams the agent: onStep for progress ("Searching official Bennett documents"), then the final result. */
export async function streamChat(message: string, sessionId: string | null,
  on: { step?: (s: string) => void; sources?: (c: Citation[]) => void; session?: (id: string) => void; token?: (t: string) => void }): Promise<ChatResult> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  const r = await fetch("/api/chat/stream", { method: "POST", headers, body: JSON.stringify({ message, session_id: sessionId }) });
  if (!r.ok || !r.body) throw new Error("Chat service unavailable");
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "", final: ChatResult | null = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const events = buf.split(/\r?\n\r?\n/);
    buf = events.pop() || "";
    for (const ev of events) {
      const type = /event: (.*)/.exec(ev)?.[1]?.trim();
      const data = ev.split(/\r?\n/).filter(l => l.startsWith("data:")).map(l => l.slice(5).trimStart()).join("\n");
      if (!type || !data) continue;
      const parsed = JSON.parse(data);
      if (type === "token") on.token?.(parsed);
      else if (type === "step") on.step?.(parsed);
      else if (type === "sources") on.sources?.(parsed);
      else if (type === "session") on.session?.(parsed.session_id);
      else if (type === "final") final = parsed;
      else if (type === "error") throw new Error(parsed);
    }
  }
  if (!final) throw new Error("No answer received");
  return final;
}

export const SCHOOLS: Record<string, { name: string; short: string; accent: string }> = {
  SoAI: { name: "School of Artificial Intelligence", short: "Artificial Intelligence", accent: "#d81830" },
  SCSET: { name: "School of Computer Science Engineering & Technology", short: "Computer Science", accent: "#005098" },
  SEAS: { name: "School of Engineering & Applied Sciences", short: "Engineering", accent: "#08a0e0" },
  SOM: { name: "School of Management", short: "Management", accent: "#a01830" },
  SOL: { name: "School of Law", short: "Law", accent: "#b91c1c" },
  TSOM: { name: "Times School of Media", short: "Media", accent: "#c2410c" },
  SLA: { name: "School of Liberal Arts", short: "Liberal Arts", accent: "#003a70" },
  SOD: { name: "School of Design", short: "Design", accent: "#1d4ed8" },
  SGP: { name: "School of Global Pathways", short: "Global Pathways", accent: "#0369a1" },
};

export const STATUS_META: Record<string, { label: string; tone: string }> = {
  MEETS_CHECKED_CRITERIA: { label: "Meets checked criteria", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  DOES_NOT_MEET_CRITERIA: { label: "Does not meet criteria", tone: "bg-red-50 text-red-700 ring-red-200" },
  INSUFFICIENT_INFORMATION: { label: "More information needed", tone: "bg-amber-50 text-amber-700 ring-amber-200" },
  NEEDS_VERIFICATION: { label: "Needs verification", tone: "bg-sky-50 text-sky-700 ring-sky-200" },
  URGENT_SUPPORT: { label: "Urgent help — official contacts", tone: "bg-red-600 text-white ring-red-600" },
};

export const inr = (n?: number | null) => n == null ? "—" : "₹" + n.toLocaleString("en-IN");
