import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BadgeCheck, Calculator, Plus, Trash2 } from "lucide-react";
import { api, type RuleResult, STATUS_META } from "../lib/api";
import { RuleCard } from "./Chat";

type Crit = { programme: string; school_id: string | null; rules: CritRules };
type CritRules = { min_percentage?: number; score_basis?: string; compulsory_subjects?: string[]; selection_components?: string[]; [key: string]: unknown };
type EligibilityRequest = { programme: string; board: string; ib_credits?: number | null; graduation_pct?: number | null; marks?: Record<string, number> };
const SUBJECTS = ["Physics", "Chemistry", "Mathematics", "Biology", "English", "Computer Science", "Economics", "Accountancy", "Business Studies", "Informatics Practices", "Music", "Painting", "Physical Education", "Other"];

export default function Eligibility() {
  const [params] = useSearchParams();
  const [crit, setCrit] = useState<Crit[]>([]);
  const [programme, setProgramme] = useState(params.get("programme") || "");
  const [board, setBoard] = useState("CBSE");
  const [marks, setMarks] = useState<{ s: string; m: string }[]>([{ s: "Physics", m: "" }, { s: "Chemistry", m: "" }, { s: "Mathematics", m: "" }, { s: "English", m: "" }]);
  const [ib, setIb] = useState("");
  const [grad, setGrad] = useState("");
  const [res, setRes] = useState<(RuleResult & { eligibility_text: string; selection_text: string }) | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api.get<Crit[]>("/criteria")
      .then(c => { setCrit(c); if (!programme && c.length) setProgramme(c.find(x => x.programme.includes("Artificial"))?.programme || c[0].programme); })
      .catch(() => setErr("Couldn't load the programme list — the BENNETT ONE server is not reachable right now. Please try again in a minute."));
  }, []); // eslint-disable-line
  const sel = crit.find(c => c.programme === programme);
  const isGrad = sel?.rules?.score_basis === "graduation_aggregate";

  async function check() {
    setErr(""); setRes(null);
    const bad = marks.filter(x => x.m !== "" && (Number(x.m) < 0 || Number(x.m) > 100)).map(x => x.s);
    if (bad.length) { setErr(`Marks must be between 0 and 100 (check ${bad.join(", ")}).`); return; }
    try {
      const body: EligibilityRequest = { programme, board };
      if (board === "IB") body.ib_credits = Number(ib) || null;
      else if (isGrad) body.graduation_pct = Number(grad) || null;
      else body.marks = Object.fromEntries(marks.filter(x => x.m !== "").map(x => [x.s, Number(x.m)]));
      setRes(await api.post("/eligibility", body));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="text-xs font-semibold uppercase tracking-widest text-bu-red">Admissions</div>
      <h1 className="text-3xl font-bold">Check your eligibility</h1>
      <p className="mt-1 text-sm text-slate-500">Your marks are checked by a rule engine against the official 2026-27 eligibility criteria — the same answer every time, with every check shown.</p>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="card p-6">
          <label className="label">Programme</label>
          <select className="input" value={programme} onChange={e => { setProgramme(e.target.value); setRes(null); }}>
            {crit.map(c => <option key={c.programme} value={c.programme}>{c.programme}{c.school_id ? ` (${c.school_id})` : ""}</option>)}
          </select>
          {sel && <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {sel.rules.min_percentage && <span className="chip bg-bu-mist">Min {sel.rules.min_percentage}%</span>}
            {sel.rules.score_basis === "class12_best_of_3" && <span className="chip bg-bu-mist">Class XII Best of 3</span>}
            {sel.rules.compulsory_subjects?.map((s: string) => <span key={s} className="chip bg-bu-red/10 text-bu-red">{s} compulsory</span>)}
            {sel.rules.selection_components?.map((s: string) => <span key={s} className="chip bg-sky-50 text-sky-700">{s}</span>)}
          </div>}
          {!isGrad && <>
            <label className="label mt-5">Board</label>
            <div className="flex gap-2">{["CBSE", "ICSE", "State", "IB"].map(b => <button key={b} onClick={() => setBoard(b)} className={`chip px-3 py-1.5 ring-1 ${board === b ? "bg-bu-blue text-white ring-bu-blue" : "bg-white ring-slate-200"}`}>{b}</button>)}</div>
          </>}
          {board === "IB" && !isGrad ? (
            <><label className="label mt-5">IB total credits</label><input className="input" type="number" value={ib} onChange={e => setIb(e.target.value)} placeholder="e.g. 30" /></>
          ) : isGrad ? (
            <><label className="label mt-5">Graduation aggregate %</label><input className="input" type="number" value={grad} onChange={e => setGrad(e.target.value)} placeholder="e.g. 68" /></>
          ) : (
            <>
              <label className="label mt-5">Class XII marks (%)</label>
              <div className="space-y-2">
                {marks.map((r, i) => (
                  <div key={i} className="flex gap-2">
                    <select className="input" value={r.s} onChange={e => setMarks(m => m.map((x, j) => j === i ? { ...x, s: e.target.value } : x))}>{SUBJECTS.map(s => <option key={s}>{s}</option>)}</select>
                    <input className={`input w-28 ${r.m !== "" && (Number(r.m) < 0 || Number(r.m) > 100) ? "border-red-400 ring-4 ring-red-100" : ""}`} type="number" min={0} max={100} step="0.01" placeholder="%" value={r.m} onChange={e => setMarks(m => m.map((x, j) => j === i ? { ...x, m: e.target.value } : x))} />
                    <button className="btn-ghost px-2.5" onClick={() => setMarks(m => m.filter((_, j) => j !== i))} aria-label="remove"><Trash2 size={15} /></button>
                  </div>
                ))}
              </div>
              <button className="btn-ghost mt-2 text-xs" onClick={() => setMarks(m => [...m, { s: "Other", m: "" }])}><Plus size={14} /> Add subject</button>
            </>
          )}
          <button className="btn-primary mt-6 w-full" onClick={check}><Calculator size={16} /> Check eligibility</button>
          {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
        </div>
        <div>
          {!res ? (
            <div className="card grid h-full min-h-[300px] place-items-center p-8 text-center text-sm text-slate-500">
              <div><img src="/brand/crest.png" alt="" className="mx-auto mb-3 h-12 w-12 opacity-80" />Enter your marks to see a transparent, check-by-check assessment.</div>
            </div>
          ) : (
            <div className="card p-6">
              <div className="flex items-center gap-2"><img src="/brand/crest.png" alt="" className="h-7 w-7" /><div className="text-sm font-semibold">BENNETT ONE · Eligibility assessment</div></div>
              <div className={`chip mt-4 px-3 py-1.5 text-sm ring-1 ${STATUS_META[res.status]?.tone}`}><BadgeCheck size={16} /> {STATUS_META[res.status]?.label}</div>
              <h3 className="mt-3 text-xl font-semibold">{programme}</h3>
              {res.computed?.best_of_3 != null && <p className="mt-1 text-sm text-slate-600">Your Best-of-3 score: <b className="text-bu-navy">{res.computed.best_of_3}%</b> ({res.computed.subjects_used?.join(", ")})</p>}
              <RuleCard rr={res} />
              <details className="mt-4 text-sm text-slate-600"><summary className="cursor-pointer font-semibold text-bu-navy">Official criteria text</summary><p className="mt-2">{res.eligibility_text}</p>{res.selection_text && <p className="mt-2">{res.selection_text}</p>}</details>
              <p className="mt-4 text-xs text-slate-400">This is preliminary guidance, not an admission offer.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
