import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink, FileText, History, Search, Sparkles } from "lucide-react";
import { api } from "../lib/api";

export type Doc = { id: number; title: string; family: string; category: string; school_id: string | null; status: string;
  versions: { id: number; label: string; is_current: boolean; url: string; pages: number | null }[] };

const CAT_LABEL: Record<string, string> = { academic_rules: "Academic rules", attendance: "Attendance", exam: "Examinations", calendar: "Academic calendar",
  fees: "Fees & refunds", scholarship: "Scholarships", hostel: "Hostel", conduct: "Conduct & discipline", admission: "Admissions", placement: "Placements & internships",
  forms: "Forms", student_life: "Student life", general: "General policies" };

type Props = { only?: string[]; title?: string; eyebrow?: string; asks?: string[]; photo?: string };

export default function Policies({ only, title, eyebrow, asks, photo }: Props) {
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  useEffect(() => { api.get<Doc[]>("/documents").then(setDocs).catch(() => setDocs([])); }, []);
  const pdfDocs = (docs || []).filter(d => !d.family.startsWith("web:") && (!only || only.includes(d.category)));
  const cats = useMemo(() => Array.from(new Set(pdfDocs.map(d => d.category))).sort(), [docs]); // eslint-disable-line
  const list = pdfDocs.filter(d => (!cat || d.category === cat) && (!q || d.title.toLowerCase().includes(q.toLowerCase())));
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {photo && (
        <div className="relative mb-6 h-48 overflow-hidden rounded-3xl shadow-card">
          <img src={`/brand/photos/${photo}`} alt="" className="h-full w-full object-cover object-[50%_60%]" />
          <div className="absolute inset-0 bg-gradient-to-r from-bu-navy/80 to-transparent" />
        </div>
      )}
      <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">{eyebrow || "Understand Bennett"}</div>
      <h1 className="text-3xl font-bold">{title || "Policy & document library"}</h1>
      <p className="mt-1 text-sm text-slate-500">Every official document BENNETT ONE answers from — with version history. Superseded versions are kept for reference but never used for answers.</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <div className="relative min-w-[240px] flex-1"><Search size={16} className="absolute left-3 top-3 text-slate-400" /><input className="input pl-9" placeholder="Search documents" value={q} onChange={e => setQ(e.target.value)} /></div>
        {!only && <select className="input w-auto" value={cat} onChange={e => setCat(e.target.value)}><option value="">All categories</option>{cats.map(c => <option key={c} value={c}>{CAT_LABEL[c] || c}</option>)}</select>}
      </div>
      {asks && asks.length > 0 && <div className="mt-5 flex flex-wrap gap-2">
        {asks.map((q, i) => (
          <Link key={q} to={`/chat?q=${encodeURIComponent(q)}`} className={i === 0 ? "btn-primary" : "btn-ghost"}>{i === 0 && <Sparkles size={16} />} {q}</Link>
        ))}
      </div>}
      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {docs === null && Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-24 rounded-2xl" />)}
        {list.map(d => {
          const cur = d.versions.find(v => v.is_current) || d.versions[d.versions.length - 1];
          return (
            <div key={d.id} className="card p-4">
              <div className="flex items-start gap-3">
                <div className="rounded-xl bg-bu-red/10 p-2 text-bu-red"><FileText size={18} /></div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold leading-snug">{d.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
                    <span className="chip bg-bu-mist text-slate-600">{CAT_LABEL[d.category] || d.category}</span>
                    <span className="chip bg-bu-mist text-slate-600">{d.school_id ? d.school_id : "University-wide"}</span>
                    {d.versions.length > 1 && <span className="chip bg-amber-50 text-amber-700"><History size={12} /> {d.versions.length} versions</span>}
                  </div>
                  {d.versions.length > 1 && <div className="mt-2 text-xs text-slate-500">Versions: {d.versions.map(v => <span key={v.id} className={v.is_current ? "font-semibold text-emerald-700" : "line-through"}>{v.label}{v.is_current ? " (current)" : ""} </span>)}</div>}
                </div>
                {cur && <a href={cur.url} target="_blank" rel="noreferrer" className="btn-ghost px-2.5" title="Open official file"><ExternalLink size={15} /></a>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
