import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, ArrowUp, BadgeCheck, CheckCircle2, CircleDashed, ExternalLink, FileText, Loader2, RotateCcw, XCircle } from "lucide-react";
import { type ChatResult, type Citation, STATUS_META, streamChat } from "../lib/api";
import { useAuth } from "../lib/auth";
import SourceDrawer from "../components/SourceDrawer";

type Msg = { role: "user" | "assistant"; content: string; result?: ChatResult; steps?: string[]; pending?: boolean; error?: string; draft?: string };

const STUDENT_PROMPTS = ["Am I eligible to sit the end-sem in all my courses?", "Write a leave application for 3 days due to illness",
  "What happens if I am caught using unfair means in an exam?", "When does the even semester start this year?"];
const PROSPECT_PROMPTS = ["Am I eligible for B.Tech CSE with Physics 78, Chemistry 70, Maths 85?", "What is the B.Tech AI fee for 2026-27?",
  "Which scholarships can I get with 92% in Class 12?", "What documents do I need for admission?"];

export default function Chat() {
  const { me } = useAuth();
  const [params, setParams] = useSearchParams();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [session, setSession] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<Citation | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // Scroll only the message list. scrollIntoView() also scrolled the window down to the footer,
  // hiding the conversation while an answer streamed.
  useEffect(() => { const el = listRef.current; if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [msgs]);
  useEffect(() => {
    const q = params.get("q");
    if (q && !started.current) { started.current = true; setParams({}); send(q); }
  }, []); // eslint-disable-line

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setBusy(true);
    setInput("");
    setMsgs(m => [...m, { role: "user", content: text }, { role: "assistant", content: "", steps: [], pending: true }]);
    const update = (fn: (a: Msg) => Msg) => setMsgs(m => [...m.slice(0, -1), fn(m[m.length - 1])]);
    try {
      const res = await streamChat(text, session, {
        session: setSession,
        step: s => update(a => ({ ...a, steps: [...(a.steps || []), s] })),
        token: t => update(a => ({ ...a, draft: (a.draft || "") + t })),
      });
      update(a => ({ ...a, pending: false, content: res.answer, result: res }));
    } catch (e) {
      update(a => ({ ...a, pending: false, error: (e instanceof Error && e.message) || "Something went wrong" }));
    } finally { setBusy(false); }
  }

  const prompts = me.role === "student" ? STUDENT_PROMPTS : PROSPECT_PROMPTS;

  return (
    <div className="mx-auto flex h-[calc(100vh-108px)] max-w-4xl flex-col px-4">
      <div className="flex items-center justify-between py-4">
        <div className="flex items-center gap-3">
          <img src="/brand/crest.png" alt="" className="h-9 w-9" />
          <div>
            <h1 className="text-lg font-semibold leading-tight">Ask Bennett ONE</h1>
            <p className="text-xs text-slate-500">{me.role === "student" ? `Answering for ${me.school} · ${me.programme} · Semester ${me.semester}` : "Answering as a prospective student · sign in for personalised answers"}</p>
          </div>
        </div>
        {msgs.length > 0 && <button className="btn-ghost text-xs" onClick={() => { setMsgs([]); setSession(null); }}><RotateCcw size={14} /> New chat</button>}
      </div>

      <div ref={listRef} className="flex-1 space-y-5 overflow-y-auto pb-4">
        {msgs.length === 0 && (
          <div className="card mt-6 p-8 text-center">
            <img src="/brand/crest.png" alt="" className="mx-auto h-14 w-14" />
            <h2 className="mt-3 text-xl font-semibold">How can I help you today?</h2>
            <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">I answer from official Bennett University documents and show the source for every fact.</p>
            <div className="mt-6 grid gap-2 sm:grid-cols-2">
              {prompts.map(p => <button key={p} onClick={() => send(p)} className="rounded-xl border border-slate-200 bg-bu-mist/60 px-4 py-3 text-left text-sm hover:border-bu-blue/40 hover:bg-white">{p}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={i} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-md bg-bu-blue px-4 py-2.5 text-[15px] text-white">{m.content}</div></div>
        ) : (
          <AssistantMessage key={i} m={m} onCite={setDrawer} />
        ))}
      </div>

      <form onSubmit={e => { e.preventDefault(); send(input); }} className="sticky bottom-0 mb-4 flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-card">
        <textarea value={input} onChange={e => setInput(e.target.value)} rows={1} placeholder="Ask about admissions, fees, attendance, exams, policies…"
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
          className="max-h-40 min-h-[44px] flex-1 resize-none bg-transparent px-3 py-2.5 text-[15px] outline-none" />
        <button disabled={busy || !input.trim()} className="btn-primary h-11 w-11 p-0" aria-label="Send">{busy ? <Loader2 className="animate-spin" size={18} /> : <ArrowUp size={18} />}</button>
      </form>
      <SourceDrawer citation={drawer} onClose={() => setDrawer(null)} />
    </div>
  );
}

function AssistantMessage({ m, onCite }: { m: Msg; onCite: (c: Citation) => void }) {
  const r = m.result;
  const cites = r?.citations || [];
  const byTag: Record<string, Citation> = {};
  cites.forEach(c => { byTag[c.tag] ??= c; });
  // turn [S1] / [DATA] / [RULE] into markdown links we can intercept; drop tags with no source
  const md = (m.content || "").replace(/\[(S\d+|DATA|RULE)\]/g, (_, t) => byTag[t] ? `[${t === "DATA" ? "official data" : t === "RULE" ? "rule" : t}](#cite-${t})` : "");
  const status = r?.status ? STATUS_META[r.status] : null;
  return (
    <div className="flex gap-3">
      <img src="/brand/crest.png" alt="" className="mt-1 h-8 w-8 shrink-0" />
      <div className="min-w-0 flex-1">
        {m.pending && (
          <div className="card space-y-2 p-4">
            {(m.steps?.length ? m.steps : ["Starting…"]).map((s, i, arr) => (
              <div key={i} className="flex items-center gap-2 text-sm text-slate-600">
                {i === arr.length - 1 ? <Loader2 size={15} className="animate-spin text-bu-blue" /> : <CheckCircle2 size={15} className="text-emerald-500" />} {s}
              </div>
            ))}
            {m.draft ? (
              <div className="prose-bu border-t border-slate-100 pt-3 text-slate-500">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.draft.replace(/\[(S\d+|DATA|RULE)\]/g, "")}</ReactMarkdown>
                <div className="mt-1 text-[11px] text-slate-400">Draft — checking every claim against the sources…</div>
              </div>
            ) : (<><div className="skeleton h-3 w-3/4 rounded" /><div className="skeleton h-3 w-1/2 rounded" /></>)}
          </div>
        )}
        {m.error && <div className="card flex items-center gap-2 p-4 text-sm text-red-700"><AlertTriangle size={16} /> {m.error}. Is the backend and SSH tunnel running?</div>}
        {!m.pending && r && (
          <div className="card p-5">
            {status && (
              <div className={`chip mb-3 ring-1 ${status.tone}`}><BadgeCheck size={14} /> {status.label}{r.rule_result?.programme ? ` · ${r.rule_result.programme}` : ""}</div>
            )}
            <div className="prose-bu">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
                a: ({ href, children }) => href?.startsWith("#cite-")
                  ? <button onClick={() => { const c = byTag[href.slice(6)]; if (c.chunk_id) onCite(c); else window.open(c.url, "_blank"); }} className="mx-0.5 inline-flex -translate-y-0.5 items-center rounded-md bg-bu-blue/10 px-1.5 text-[11px] font-semibold text-bu-blue hover:bg-bu-blue hover:text-white">{children}</button>
                  : <a href={href} target="_blank" rel="noreferrer" className="text-bu-blue underline">{children}</a>,
              }}>{md}</ReactMarkdown>
            </div>
            {r.rule_result && r.rule_result.checks?.length > 0 && <RuleCard rr={r.rule_result} />}
            {cites.length > 0 && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Sources used</div>
                <div className="flex flex-wrap gap-2">
                  {cites.map((c, i) => (
                    <button key={i} onClick={() => c.chunk_id ? onCite(c) : window.open(c.url, "_blank")} className="chip max-w-full bg-slate-50 text-slate-700 ring-1 ring-slate-200 hover:ring-bu-blue/40">
                      <FileText size={13} className="shrink-0 text-bu-red" />
                      <span className="truncate">{c.tag !== "DATA" && <b className="mr-1">{c.tag}</b>}{c.title}{c.page ? ` · p.${c.page}` : ""}{c.academic_year ? ` · ${c.academic_year}` : ""}</span>
                      {!c.chunk_id && <ExternalLink size={12} />}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {r.warnings?.map(w => <div key={w} className="mt-3 flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800"><AlertTriangle size={14} /> {w}</div>)}
            <p className="mt-3 text-[11px] text-slate-400">Guidance from official documents — final decisions rest with Bennett University.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export function RuleCard({ rr }: { rr: NonNullable<ChatResult["rule_result"]> }) {
  return (
    <div className="mt-4 rounded-xl border border-slate-200 bg-bu-mist/50 p-4">
      <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">What was checked</div>
      <ul className="space-y-1.5">
        {rr.checks.map((c, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            {c.passed === true ? <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-600" /> : c.passed === false ? <XCircle size={16} className="mt-0.5 shrink-0 text-red-600" /> : <CircleDashed size={16} className="mt-0.5 shrink-0 text-sky-600" />}
            <span><b className="font-semibold">{c.name}</b> — {c.detail}</span>
          </li>
        ))}
      </ul>
      {rr.missing?.length > 0 && <div className="mt-2 text-sm text-amber-700">Missing: {rr.missing.join(", ")}</div>}
      {rr.computed?.note && <div className="mt-2 text-xs text-slate-500">ℹ {rr.computed.note}</div>}
      {rr.sources?.length > 0 && <div className="mt-2 text-xs text-slate-500">Rule source: {rr.sources.map(s => <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="text-bu-blue underline">{s.title}</a>)}</div>}
    </div>
  );
}
