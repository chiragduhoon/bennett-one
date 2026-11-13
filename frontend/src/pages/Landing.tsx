import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, BookOpenCheck, Calculator, FileSearch, Layers, type LucideIcon, Scale, Search, ShieldCheck, Sparkles, UserRoundCheck } from "lucide-react";
import { api, SCHOOLS } from "../lib/api";

const EXAMPLES = [
  "Am I eligible for B.Tech CSE with 82% in PCM?",
  "What is the minimum attendance to sit the end-semester exam?",
  "What is the total tuition fee for BBA for 2026-27?",
  "How do merit scholarships work and how are they renewed?",
  "Compare B.Tech AI and B.Sc AI",
  "What is the refund policy if I withdraw admission?",
];

type Stats = { programmes: number; documents: number; chunks: number; criteria: number; fee_structures: number };
type SchoolRow = { id: string; name: string; programme_count: number };

export default function Landing() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [schools, setSchools] = useState<SchoolRow[]>([]);
  useEffect(() => { const t = setInterval(() => setI(x => (x + 1) % EXAMPLES.length), 3200); return () => clearInterval(t); }, []);
  useEffect(() => { api.get<Stats>("/stats").then(setStats).catch(() => {}); api.get<SchoolRow[]>("/schools").then(setSchools).catch(() => {}); }, []);
  const ask = (text: string) => nav(`/chat?q=${encodeURIComponent(text)}`);

  return (
    <div>
      {/* HERO */}
      <section className="hero-gradient relative overflow-hidden text-white">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 py-14 lg:grid-cols-[1.15fr_1fr] lg:py-20">
          <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .5 }}>
            <span className="chip bg-white/10 text-white ring-1 ring-white/20"><Sparkles size={13} className="text-bu-cyan" /> BENNETT ONE · University Intelligence Platform</span>
            <h1 className="mt-5 text-4xl font-bold leading-tight sm:text-5xl">
              Everything about Bennett.<br /><span className="text-bu-cyan">One intelligent place.</span>
            </h1>
            <p className="mt-4 max-w-xl text-lg text-white/80">Admissions, eligibility, fees, scholarships, attendance, exams and every university policy — answered from official documents, with the page it came from.</p>
            <form onSubmit={e => { e.preventDefault(); if (q.trim()) ask(q.trim()); }} className="mt-8 flex max-w-2xl items-center gap-2 rounded-2xl bg-white p-2 shadow-2xl shadow-black/20">
              <Search className="ml-2 shrink-0 text-slate-400" size={20} />
              <input value={q} onChange={e => setQ(e.target.value)} placeholder={EXAMPLES[i]}
                className="min-w-0 flex-1 bg-transparent px-1 py-2.5 text-[15px] text-bu-navy outline-none placeholder:text-slate-400" aria-label="Ask a question" />
              <button className="btn-primary shrink-0">Ask <ArrowRight size={16} /></button>
            </form>
            <div className="mt-4 flex flex-wrap gap-2">
              {EXAMPLES.slice(0, 4).map(e => (
                <button key={e} onClick={() => ask(e)} className="chip bg-white/10 text-white/90 ring-1 ring-white/15 hover:bg-white/20">{e}</button>
              ))}
            </div>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: .97 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: .6, delay: .1 }} className="relative hidden lg:block">
            <div className="ml-auto grid w-[480px] grid-cols-[1.25fr_1fr] gap-3">
              <div className="h-[420px] overflow-hidden rounded-3xl shadow-2xl ring-1 ring-white/20">
                <img src="/brand/photos/main-building.jpg" alt="Bennett University main academic building" className="h-full w-full object-cover object-[50%_60%]" />
              </div>
              <div className="grid gap-3">
                <div className="overflow-hidden rounded-3xl shadow-xl ring-1 ring-white/20">
                  <img src="/brand/photos/atrium.jpg" alt="Academic block atrium" className="h-[204px] w-full object-cover object-[50%_40%]" />
                </div>
                <div className="overflow-hidden rounded-3xl shadow-xl ring-1 ring-white/20">
                  <img src="/brand/photos/hostels.jpg" alt="Hostel blocks" className="h-[204px] w-full object-cover object-[50%_70%]" />
                </div>
              </div>
            </div>
            <div className="absolute -bottom-6 left-6 card flex items-center gap-3 p-3 pr-5 text-bu-navy">
              <img src="/brand/crest.png" alt="" className="h-10 w-10" />
              <div><div className="text-xs text-slate-500">Accredited</div><div className="font-semibold">NAAC Grade A+</div></div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* STATS */}
      <section className="relative z-10 mx-auto -mt-8 max-w-7xl px-4">
        <div className="card grid grid-cols-2 divide-slate-100 sm:grid-cols-4 sm:divide-x">
          {[
            ["9", "Schools"],
            [stats ? String(stats.programmes) : "…", "Programmes indexed"],
            [stats ? String(stats.documents) : "…", "Official documents"],
            [stats ? stats.chunks.toLocaleString("en-IN") : "…", "Searchable passages"],
          ].map(([n, l]) => (
            <div key={l} className="px-6 py-5 text-center">
              <div className="font-display text-3xl font-bold text-bu-blue">{n}</div>
              <div className="mt-1 text-xs font-medium uppercase tracking-wide text-slate-500">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ENTRY POINTS */}
      <section className="mx-auto mt-14 max-w-7xl px-4">
        <div className="grid gap-5 md:grid-cols-2">
          <Link to="/programmes" className="card group overflow-hidden p-6 transition hover:-translate-y-0.5 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-bu-blue/10 p-3 text-bu-blue"><BookOpenCheck /></div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Discover Bennett</div>
                <h3 className="mt-1 text-xl font-semibold">I'm exploring admission</h3>
                <p className="mt-1 text-sm text-slate-600">Find programmes, check eligibility against the official criteria, see the 2026-27 fees and scholarships. No account needed.</p>
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-bu-blue">Explore programmes <ArrowRight size={15} className="transition group-hover:translate-x-1" /></span>
              </div>
            </div>
          </Link>
          <Link to="/login" className="card group overflow-hidden p-6 transition hover:-translate-y-0.5 hover:shadow-lg">
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-bu-red/10 p-3 text-bu-red"><UserRoundCheck /></div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Navigate Bennett</div>
                <h3 className="mt-1 text-xl font-semibold">I'm already a student</h3>
                <p className="mt-1 text-sm text-slate-600">Answers that apply to <em>your</em> school and semester: attendance, exam eligibility, academic rules, and ready-to-send applications.</p>
                <span className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-bu-blue">Sign in <ArrowRight size={15} className="transition group-hover:translate-x-1" /></span>
              </div>
            </div>
          </Link>
        </div>
      </section>

      {/* SCHOOLS */}
      <section className="mx-auto mt-16 max-w-7xl px-4">
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Explore schools</div>
            <h2 className="mt-1 text-3xl font-bold">Nine schools. One university.</h2>
          </div>
          <Link to="/programmes" className="hidden text-sm font-semibold text-bu-blue sm:block">All programmes →</Link>
        </div>
        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
          {Object.entries(SCHOOLS).map(([code, s]) => {
            const row = schools.find(x => x.id === code);
            return (
              <Link key={code} to={`/programmes?school=${code}`} className="card group flex flex-col items-center p-5 text-center transition hover:-translate-y-0.5 hover:shadow-lg">
                <div className="grid h-24 w-24 place-items-center rounded-full bg-bu-mist transition group-hover:scale-105">
                  <img src={`/brand/schools/${code}.webp`} alt="" className="h-16 w-16 object-contain" />
                </div>
                <div className="mt-3 text-sm font-semibold leading-snug">{s.name}</div>
                {row && <div className="mt-1 text-xs text-slate-500">{row.programme_count} programmes</div>}
              </Link>
            );
          })}
        </div>
      </section>

      {/* LIFE AT BENNETT */}
      <section className="mx-auto mt-16 max-w-7xl px-4">
        <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Life at Bennett</div>
        <h2 className="mt-1 text-3xl font-bold">A 68-acre campus in Greater Noida</h2>
        <div className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            ["block-b.jpg", "Academic blocks", "Where classes and labs happen", "50% 55%"],
            ["classroom.jpg", "Classrooms", "Interactive, tiered lecture rooms", "50% 50%"],
            ["library.jpg", "Study spaces", "Quiet zones and collaboration pods", "50% 70%"],
            ["student-hub.jpg", "Student life", "Events, clubs and hackathons", "50% 60%"],
            ["atrium.jpg", "Open atriums", "Light-filled spaces between classes", "50% 40%"],
            ["hostels.jpg", "On-campus hostels", "Residential blocks around green lawns", "50% 65%"],
            ["hostel-lane.jpg", "Hostel avenues", "Tree-lined walks between blocks", "50% 60%"],
            ["campus-evening.jpg", "Evenings on campus", "Greater Noida sunsets", "50% 55%"],
          ].map(([img, t, d, pos]) => (
            <figure key={img} className="group relative h-72 overflow-hidden rounded-2xl shadow-card">
              <img src={`/brand/photos/${img}`} alt={t} style={{ objectPosition: pos }} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />
              <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-bu-navy/90 via-bu-navy/40 to-transparent p-4 text-white">
                <div className="font-semibold">{t}</div><div className="text-xs text-white/80">{d}</div>
              </figcaption>
            </figure>
          ))}
        </div>
        <p className="mt-2 text-xs text-slate-400">Photos taken on campus by students.</p>
      </section>

      {/* HOW IT WORKS */}
      <section className="mx-auto mt-16 max-w-7xl px-4">
        <div className="card overflow-hidden">
          <div className="grid lg:grid-cols-[1fr_2fr]">
            <div className="bg-bu-navy p-8 text-white">
              <div className="text-xs font-semibold uppercase tracking-widest text-bu-cyan">Why trust the answers</div>
              <h2 className="mt-2 text-2xl font-bold">Not a chatbot that guesses.</h2>
              <p className="mt-3 text-sm text-white/75">BENNETT ONE reads Bennett's own rulebooks, notices and fee tables, applies the rules in code, and shows you the exact source page.</p>
            </div>
            <div className="grid gap-px bg-slate-100 sm:grid-cols-2">
              {([
                [FileSearch, "Official sources only", "Every answer is built from documents published by Bennett University — with document and page citations."],
                [Layers, "School-aware", "Rules differ by school and programme. Your answer only uses policies that apply to you, plus university-wide rules."],
                [Calculator, "Rules checked in code", "Eligibility, Best-of-3 marks and attendance thresholds are computed by a rule engine — never guessed by the AI."],
                [Scale, "Version & conflict aware", "Newer notifications supersede older rules (e.g. the 2022 attendance notification raised 70% → 75%) and conflicts are flagged."],
              ] as [LucideIcon, string, string][]).map(([Icon, t, d]) => (
                <div key={t} className="bg-white p-6">
                  <Icon className="text-bu-red" size={22} />
                  <div className="mt-3 font-semibold">{t}</div>
                  <p className="mt-1 text-sm text-slate-600">{d}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
        <p className="mt-4 flex items-center justify-center gap-2 text-center text-xs text-slate-500"><ShieldCheck size={14} /> Guidance only — admission offers, scholarships and exam eligibility are decided by the University.</p>
      </section>
    </div>
  );
}
