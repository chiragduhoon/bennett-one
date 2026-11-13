import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Clock, Search } from "lucide-react";
import { api, SCHOOLS } from "../lib/api";

// Real photos from students; schools without one simply show no banner.
const SCHOOL_PHOTOS: Record<string, { img: string; pos: string; tag: string; caption: string }> = {
  SoAI: { img: "soai-hackathon.jpg", pos: "50% 45%", tag: "School of Artificial Intelligence", caption: "Hackathons, labs and a community building with AI" },
  SCSET: { img: "lecture-hall.jpg", pos: "50% 50%", tag: "School of Computer Science Engineering & Technology", caption: "Learning by building, in labs and lecture halls" },
  SEAS: { img: "classroom.jpg", pos: "50% 50%", tag: "School of Engineering & Applied Sciences", caption: "Engineering fundamentals, applied" },
};

type P = { id: string; name: string; school_id: string | null; level: string; duration: string | null; credits: string | null; summary: string };

export default function Programmes() {
  const [params, setParams] = useSearchParams();
  const school = params.get("school") || "";
  const [level, setLevel] = useState("");
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<P[] | null>(null);
  useEffect(() => { api.get<P[]>("/programmes").then(setRows).catch(() => setRows([])); }, []);
  const list = useMemo(() => (rows || []).filter(p =>
    (!school || p.school_id === school) && (!level || p.level === level) && (!q || p.name.toLowerCase().includes(q.toLowerCase()))
    && p.summary), [rows, school, level, q]);
  const s = school ? SCHOOLS[school] : null;
  const banner = school ? SCHOOL_PHOTOS[school] : null;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {banner && (
        <div className="relative mb-6 h-56 overflow-hidden rounded-3xl shadow-card">
          <img src={`/brand/photos/${banner.img}`} alt="" className="h-full w-full object-cover" style={{ objectPosition: banner.pos }} />
          <div className="absolute inset-0 bg-gradient-to-r from-bu-navy/90 via-bu-navy/40 to-transparent" />
          <div className="absolute bottom-5 left-6 text-white">
            <div className="text-xs font-semibold uppercase tracking-widest text-bu-cyan">{banner.tag}</div>
            <div className="mt-1 max-w-md text-lg font-semibold">{banner.caption}</div>
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-5">
        {s && <img src={`/brand/schools/${school}.webp`} alt="" className="h-16 w-16 object-contain" />}
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Discover Bennett</div>
          <h1 className="text-3xl font-bold">{s ? s.name : "Programmes"}</h1>
          <p className="text-sm text-slate-500">Official programme information from bennett.edu.in, with eligibility and AY 2026-27 fees.</p>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap gap-2">
        <button onClick={() => setParams({})} className={`chip ring-1 ${!school ? "bg-bu-blue text-white ring-bu-blue" : "bg-white ring-slate-200"}`}>All schools</button>
        {Object.entries(SCHOOLS).map(([c, x]) => (
          <button key={c} onClick={() => setParams({ school: c })} className={`chip ring-1 ${school === c ? "bg-bu-blue text-white ring-bu-blue" : "bg-white ring-slate-200 hover:ring-bu-blue/40"}`}>
            <img src={`/brand/schools/${c}.webp`} alt="" className="h-4 w-4" /> {x.short}
          </button>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <div className="relative min-w-[240px] flex-1"><Search size={16} className="absolute left-3 top-3 text-slate-400" /><input className="input pl-9" placeholder="Search programmes (e.g. MBA, B.Tech AI)" value={q} onChange={e => setQ(e.target.value)} /></div>
        <select className="input w-auto" value={level} onChange={e => setLevel(e.target.value)}>
          <option value="">All levels</option><option value="UG">Undergraduate</option><option value="PG">Postgraduate</option><option value="PhD">Doctoral</option><option value="Diploma">Diploma / Certificate</option>
        </select>
      </div>
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows === null && Array.from({ length: 6 }).map((_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}
        {list.map(p => (
          <Link key={p.id} to={`/programmes/${p.id}`} className="card group flex flex-col p-5 transition hover:-translate-y-0.5 hover:shadow-lg">
            <div className="flex items-center gap-2">
              {p.school_id && <img src={`/brand/schools/${p.school_id}.webp`} alt="" className="h-7 w-7 object-contain" />}
              <span className="chip bg-bu-mist text-slate-600">{p.level}</span>
              {p.duration && <span className="chip bg-bu-mist text-slate-600"><Clock size={12} /> {p.duration}</span>}
            </div>
            <h3 className="mt-3 font-semibold leading-snug group-hover:text-bu-blue">{p.name}</h3>
            <p className="mt-1 line-clamp-3 text-sm text-slate-600">{p.summary}</p>
            <span className="mt-auto pt-3 text-sm font-semibold text-bu-blue">View details →</span>
          </Link>
        ))}
        {rows && list.length === 0 && <p className="text-sm text-slate-500">No programmes match.</p>}
      </div>
    </div>
  );
}
