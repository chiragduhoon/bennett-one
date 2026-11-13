import { useEffect, useState } from "react";
import { ExternalLink, FileText, X } from "lucide-react";
import { api, type Citation } from "../lib/api";

type ChunkInfo = { id: number; text: string; page: number | null; section: string | null; version_id: number; is_pdf: boolean;
  url: string; title: string; version: string; is_current: boolean };

/** Side panel: the exact passage that was cited, plus the original PDF opened at the cited page. */
export default function SourceDrawer({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const [c, setC] = useState<ChunkInfo | null>(null);
  const [showPdf, setShowPdf] = useState(false);
  useEffect(() => {
    setC(null); setShowPdf(false);
    if (citation?.chunk_id) api.get<ChunkInfo>(`/chunks/${citation.chunk_id}`).then(setC).catch(() => {});
  }, [citation]);
  if (!citation) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-bu-navy/30 backdrop-blur-[2px]" onClick={onClose}>
      <aside onClick={e => e.stopPropagation()} className="flex h-full w-full max-w-2xl flex-col bg-white shadow-2xl">
        <div className="flex items-start gap-3 border-b border-slate-100 p-5">
          <div className="rounded-xl bg-bu-red/10 p-2 text-bu-red"><FileText size={20} /></div>
          <div className="min-w-0 flex-1">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source {citation.tag}</div>
            <h3 className="truncate font-semibold">{citation.title}</h3>
            <div className="mt-1 flex flex-wrap gap-1.5 text-xs">
              {citation.page && <span className="chip bg-slate-100 text-slate-600">Page {citation.page}</span>}
              {citation.academic_year && <span className="chip bg-slate-100 text-slate-600">AY {citation.academic_year}</span>}
              <span className="chip bg-slate-100 text-slate-600">{citation.school_id && citation.school_id !== "ALL" ? `Applies to ${citation.school_id}` : "University-wide"}</span>
              {c && <span className={`chip ${c.is_current ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{c.is_current ? "Current version" : "Superseded"}</span>}
            </div>
          </div>
          <button onClick={onClose} className="btn-ghost px-2"><X size={18} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {citation.section && <div className="mb-2 text-sm font-semibold text-bu-blue">{citation.section}</div>}
          <blockquote className="whitespace-pre-wrap rounded-xl border-l-4 border-bu-red bg-bu-mist/60 p-4 text-sm leading-relaxed text-slate-700">{c?.text || "Loading passage…"}</blockquote>
          <div className="mt-4 flex flex-wrap gap-2">
            {c?.is_pdf && <button className="btn-blue" onClick={() => setShowPdf(s => !s)}>{showPdf ? "Hide" : "View"} original PDF{citation.page ? ` at page ${citation.page}` : ""}</button>}
            <a className="btn-ghost" href={citation.url} target="_blank" rel="noreferrer">Open on bennett.edu.in <ExternalLink size={14} /></a>
          </div>
          {showPdf && c && <iframe title="source pdf" src={`/api/versions/${c.version_id}/file#page=${citation.page || 1}`} className="mt-4 h-[70vh] w-full rounded-xl border border-slate-200" />}
        </div>
      </aside>
    </div>
  );
}
