import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Award, Calculator, Clock, ExternalLink, Sparkles } from "lucide-react";
import { api, inr, SCHOOLS } from "../lib/api";

type Detail = { id: string; name: string; school_id: string | null; level: string; duration: string | null; credits: string | null;
  specialisations: string | null; summary: string | null; url: string;
  criteria: { eligibility: string; selection: string; nri: string | null; source_url: string; programme_name: string } | null;
  fees: { academic_year: string; tuition_by_year: Record<string, number> | null; total_tuition: number | null; tables: { title: string; rows: string[][] }[];
    other_charges: string[] | null; notes: string[] | null; source_url: string } | null };

export default function ProgrammeDetail() {
  const { id } = useParams();
  const [p, setP] = useState<Detail | null>(null);
  useEffect(() => { api.get<Detail>(`/programmes/${id}`).then(setP).catch(() => {}); }, [id]);
  if (!p) return <div className="mx-auto max-w-5xl px-4 py-10"><div className="skeleton h-64 rounded-2xl" /></div>;
  const s = p.school_id ? SCHOOLS[p.school_id] : null;
  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link to="/programmes" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-bu-blue"><ArrowLeft size={14} /> All programmes</Link>
      <div className="card mt-4 overflow-hidden">
        <div className="hero-gradient flex flex-wrap items-center gap-5 p-7 text-white">
          {p.school_id && <div className="grid h-20 w-20 place-items-center rounded-2xl bg-white"><img src={`/brand/schools/${p.school_id}.webp`} alt="" className="h-14 w-14 object-contain" /></div>}
          <div className="min-w-0 flex-1">
            {s && <div className="text-sm text-white/70">{s.name}</div>}
            <h1 className="text-3xl font-bold">{p.name}</h1>
            <div className="mt-2 flex flex-wrap gap-2 text-sm">
              <span className="chip bg-white/15 text-white">{p.level}</span>
              {p.duration && <span className="chip bg-white/15 text-white"><Clock size={13} /> {p.duration}</span>}
              {p.credits && <span className="chip bg-white/15 text-white">{p.credits} credits</span>}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link to={`/eligibility?programme=${encodeURIComponent(p.criteria?.programme_name || p.name)}`} className="btn bg-white text-bu-navy hover:bg-bu-cream"><Calculator size={16} /> Check my eligibility</Link>
            <Link to={`/chat?q=${encodeURIComponent("Tell me about " + p.name + " — eligibility, fees and scholarships")}`} className="btn-primary"><Sparkles size={16} /> Ask about this</Link>
          </div>
        </div>
        {p.summary && <p className="p-7 pb-0 text-slate-700">{p.summary}</p>}
        <div className="grid gap-6 p-7 lg:grid-cols-2">
          <section>
            <h2 className="text-lg font-semibold">Eligibility & selection</h2>
            {p.criteria ? (
              <div className="mt-3 space-y-3 text-sm text-slate-700">
                <p>{p.criteria.eligibility}</p>
                {p.criteria.selection && <p><b>Selection:</b> {p.criteria.selection}</p>}
                {p.criteria.nri && <p className="text-slate-500"><b>NRI / international:</b> {p.criteria.nri}</p>}
                <a href={p.criteria.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-bu-blue">Source: Eligibility and Selection Criteria <ExternalLink size={12} /></a>
              </div>
            ) : <p className="mt-3 text-sm text-slate-500">Criteria not available in structured form — ask Bennett ONE or see the official page.</p>}
          </section>
          <section>
            <h2 className="text-lg font-semibold">Fees {p.fees?.academic_year && <span className="text-sm font-normal text-slate-500">· AY {p.fees.academic_year}</span>}</h2>
            {p.fees ? (
              <div className="mt-3">
                {p.fees.tables.slice(0, 2).map((t, i) => (
                  <div key={i} className="mb-3 overflow-x-auto rounded-xl border border-slate-200">
                    <table className="w-full text-sm">
                      <tbody>{t.rows.map((r, j) => (
                        <tr key={j} className={j === 0 ? "bg-slate-50 font-semibold" : r[0]?.startsWith("Total") ? "bg-bu-blue/5 font-semibold" : ""}>
                          {r.map((c, k) => <td key={k} className="border-b border-slate-100 px-3 py-2">{c}</td>)}
                        </tr>))}</tbody>
                    </table>
                  </div>
                ))}
                {p.fees.total_tuition && <div className="flex items-center gap-2 rounded-xl bg-bu-cream px-3 py-2 text-sm"><Award size={16} className="text-bu-red" /> Total tuition: <b>{inr(p.fees.total_tuition)}</b></div>}
                {p.fees.other_charges && <ul className="mt-3 list-disc space-y-0.5 pl-5 text-xs text-slate-600">{p.fees.other_charges.slice(0, 7).map(o => <li key={o}>{o}</li>)}</ul>}
                <a href={p.fees.source_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-bu-blue">Source: Fee Structure AY 2026-27 <ExternalLink size={12} /></a>
              </div>
            ) : <p className="mt-3 text-sm text-slate-500">Fee table not matched for this programme.</p>}
          </section>
        </div>
        {p.url && <div className="border-t border-slate-100 px-7 py-4 text-sm"><a href={p.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-bu-blue">Official programme page <ExternalLink size={13} /></a></div>}
      </div>
    </div>
  );
}
