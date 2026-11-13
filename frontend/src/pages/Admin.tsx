import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { CheckCircle2, FileUp, GitCompare, History, Scale, ScrollText, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Doc } from "./Policies";

type PolicySide = { scope: string; value_pct: number; source: { title: string; quote: string } };
type Conflicts = { policy_conflicts: { topic: string; older: PolicySide; newer: PolicySide; status: string }[]; flagged: unknown[] };
type AuditRow = { at: string; action: string; detail?: Record<string, unknown> | null };

export default function Admin() {
  const { me, ready } = useAuth();
  const [tab, setTab] = useState<"docs" | "conflicts" | "upload" | "audit">("docs");
  const [docs, setDocs] = useState<Doc[]>([]);
  const [conf, setConf] = useState<Conflicts | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [diff, setDiff] = useState<{ title: string; lines: string[] } | null>(null);
  const [msg, setMsg] = useState("");
  const load = () => { api.get<Doc[]>("/documents").then(setDocs); api.get<Conflicts>("/admin/conflicts").then(setConf); api.get<AuditRow[]>("/admin/audit").then(setAudit); };
  useEffect(() => { if (me.role === "admin") load(); }, [me.role]);
  if (!ready) return null;
  if (me.role !== "admin") return <Navigate to="/login" />;
  const versioned = docs.filter(d => d.versions.length > 1);
  const pending = docs.filter(d => d.status === "pending");

  async function showDiff(d: Doc) {
    const [a, b] = d.versions.slice(-2);
    const r = await api.get<{ diff: string[] }>(`/admin/versions/${d.id}/diff?a=${a.id}&b=${b.id}`);
    setDiff({ title: `${d.title}: ${a.label} → ${b.label}`, lines: r.diff });
  }
  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget; // React clears currentTarget after the first await
    const fd = new FormData(form);
    try { await api.post("/admin/upload", fd); setMsg("Uploaded as PENDING — approve it below to make it authoritative."); load(); form.reset(); }
    catch (err) { setMsg(err instanceof Error ? err.message : String(err)); }
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Administrator</div>
      <h1 className="text-3xl font-bold">Knowledge management</h1>
      <div className="mt-5 grid gap-4 sm:grid-cols-4">
        {[["Documents", docs.length], ["With version history", versioned.length], ["Resolved conflicts", conf?.policy_conflicts.length ?? 0], ["Pending review", pending.length]].map(([l, n]) => (
          <div key={l as string} className="card p-4"><div className="font-display text-2xl font-bold text-bu-blue">{n}</div><div className="text-xs text-slate-500">{l}</div></div>
        ))}
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        {([["docs", "Documents & versions", History], ["conflicts", "Policy conflicts", Scale], ["upload", "Upload", FileUp], ["audit", "Audit log", ScrollText]] as const).map(([k, l, I]) => (
          <button key={k} onClick={() => setTab(k)} className={`btn ${tab === k ? "bg-bu-blue text-white" : "bg-white ring-1 ring-slate-200"}`}><I size={15} /> {l}</button>
        ))}
      </div>

      {tab === "docs" && <div className="card mt-4 overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Document</th><th>Category</th><th>Scope</th><th>Versions</th><th>Status</th><th></th></tr></thead>
          <tbody>{docs.filter(d => !d.family.startsWith("web:")).map(d => (
            <tr key={d.id} className="border-t border-slate-100">
              <td className="px-4 py-2.5 font-medium">{d.title}</td><td>{d.category}</td><td>{d.school_id || "University"}</td>
              <td>{d.versions.map(v => <span key={v.id} className={`mr-1 chip ${v.is_current ? "bg-emerald-50 text-emerald-700" : "bg-slate-100 text-slate-500"}`}>{v.label}</span>)}</td>
              <td>{d.status === "pending" ? <span className="flex gap-1">
                <button className="btn-ghost px-2 py-1 text-xs" onClick={() => api.post(`/admin/documents/${d.id}/approve`, {}).then(load)}><CheckCircle2 size={14} /> Approve</button>
                <button className="btn-ghost px-2 py-1 text-xs" onClick={() => api.post(`/admin/documents/${d.id}/reject`, {}).then(load)}><XCircle size={14} /> Reject</button></span>
                : <span className="chip bg-emerald-50 text-emerald-700">{d.status}</span>}</td>
              <td className="pr-4">{d.versions.length > 1 && <button className="btn-ghost px-2 py-1 text-xs" onClick={() => showDiff(d)}><GitCompare size={14} /> Compare</button>}</td>
            </tr>))}</tbody>
        </table>
      </div>}

      {tab === "conflicts" && <div className="mt-4 space-y-4">
        {conf?.policy_conflicts.map((c, i) => (
          <div key={i} className="card p-5">
            <div className="flex items-center gap-2 text-sm font-semibold"><Scale size={16} className="text-bu-red" /> {c.topic.replace(/_/g, " ")} <span className="chip bg-emerald-50 text-emerald-700">resolved: newer + higher authority wins</span></div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm"><div className="text-xs font-semibold uppercase text-slate-500">Older · {c.older.scope}</div><div className="mt-1 font-semibold line-through decoration-red-400">{c.older.value_pct}% — {c.older.source.title}</div><p className="mt-1 text-slate-600">“{c.older.source.quote}”</p></div>
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-4 text-sm"><div className="text-xs font-semibold uppercase text-emerald-700">Current · {c.newer.scope}-wide</div><div className="mt-1 font-semibold">{c.newer.value_pct}% — {c.newer.source.title}</div><p className="mt-1 text-slate-600">“{c.newer.source.quote}”</p></div>
            </div>
          </div>
        ))}
      </div>}

      {tab === "upload" && <form onSubmit={upload} className="card mt-4 grid max-w-2xl gap-4 p-6">
        <div><label className="label">PDF file</label><input name="file" type="file" accept="application/pdf" required className="input" /></div>
        <div><label className="label">Title</label><input name="title" required className="input" placeholder="e.g. Revised attendance notification" /></div>
        <div className="grid gap-4 sm:grid-cols-3">
          <div><label className="label">Category</label><select name="category" className="input">{["attendance", "exam", "academic_rules", "calendar", "fees", "scholarship", "hostel", "conduct", "admission", "general"].map(c => <option key={c}>{c}</option>)}</select></div>
          <div><label className="label">School</label><select name="school_id" className="input"><option value="">University-wide</option>{["SoAI", "SCSET", "SEAS", "SOM", "SOL", "TSOM", "SLA", "SOD", "SGP"].map(s => <option key={s}>{s}</option>)}</select></div>
          <div><label className="label">Academic year</label><input name="academic_year" className="input" placeholder="2026-27" /></div>
        </div>
        <button className="btn-primary"><FileUp size={16} /> Upload for review</button>
        {msg && <p className="text-sm text-slate-600">{msg}</p>}
        <p className="text-xs text-slate-500">A document never becomes authoritative just because it was uploaded — it stays pending until approved.</p>
      </form>}

      {tab === "audit" && <div className="card mt-4 divide-y divide-slate-100">{audit.map((a, i) => <div key={i} className="flex gap-4 px-4 py-2.5 text-sm"><span className="w-44 text-slate-500">{new Date(a.at).toLocaleString()}</span><span className="font-medium">{a.action}</span><span className="text-slate-500">{JSON.stringify(a.detail || {})}</span></div>)}</div>}

      {diff && <div className="fixed inset-0 z-50 grid place-items-center bg-bu-navy/40 p-4" onClick={() => setDiff(null)}>
        <div className="card max-h-[85vh] w-full max-w-4xl overflow-y-auto p-5" onClick={e => e.stopPropagation()}>
          <h3 className="font-semibold">{diff.title}</h3>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap text-xs leading-relaxed">{diff.lines.map((l, i) => <div key={i} className={l.startsWith("+") ? "bg-emerald-50 text-emerald-800" : l.startsWith("-") ? "bg-red-50 text-red-800" : "text-slate-500"}>{l}</div>)}</pre>
        </div>
      </div>}
    </div>
  );
}
