import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { AlertTriangle, BookOpen, CalendarDays, FileSignature, GraduationCap, type LucideIcon, ShieldAlert, Sparkles } from "lucide-react";
import { api, type RuleResult } from "../lib/api";
import { useAuth } from "../lib/auth";

export default function Dashboard() {
  const { me, ready } = useAuth();
  const [att, setAtt] = useState<RuleResult | null>(null);
  const subj = me.attendance?.subject_wise_approx || {};
  useEffect(() => {
    if (Object.keys(subj).length) api.post<RuleResult>("/attendance/check", { courses: subj, school_id: me.school }).then(setAtt).catch(() => {});
  }, [me.school, JSON.stringify(subj)]); // eslint-disable-line
  if (!ready) return null;
  if (me.role === "prospective") return <Navigate to="/login" />;
  const threshold = att?.computed?.threshold_pct ?? 75;
  const low = Object.entries(subj).filter(([, v]) => v < threshold);
  const courseName = (code: string) => me.current_courses?.find(c => c.code === code)?.name || code;
  const hour = new Date().getHours();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="card relative flex flex-wrap items-center gap-5 overflow-hidden p-6 text-white">
        <img src="/brand/photos/library.jpg" alt="" className="absolute inset-0 h-full w-full object-cover object-[50%_65%]" />
        <div className="absolute inset-0 bg-gradient-to-r from-bu-navy via-bu-navy/85 to-bu-blue/40" />
        <div className="relative grid h-16 w-16 place-items-center rounded-2xl bg-white"><img src={`/brand/schools/${me.school}.webp`} alt="" className="h-12 w-12 object-contain" /></div>
        <div className="relative flex-1">
          <div className="text-sm text-white/70">Good {hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"},</div>
          <h1 className="text-2xl font-bold">{me.name}</h1>
          <div className="text-sm text-white/80">{me.programme} · {me.school} · Semester {me.semester} · {me.academic_year}</div>
        </div>
        <Link to="/chat" className="btn-primary relative"><Sparkles size={16} /> Ask Bennett ONE</Link>
      </div>

      {low.length > 0 && (
        <div className="mt-5 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <ShieldAlert className="mt-0.5 shrink-0" size={18} />
          <div><b>Attendance below {threshold}% in {low.length} course{low.length > 1 ? "s" : ""}:</b> {low.map(([c, v]) => `${courseName(c)} (${v}%)`).join(", ")}. You may not be eligible for the End Semester Examination.
            <Link to={`/chat?q=${encodeURIComponent("My attendance in " + courseName(low[0][0]) + " is " + low[0][1] + "%. Am I eligible for the end-sem exam and what can I do?")}`} className="ml-1 font-semibold underline">Ask what to do →</Link>
            {att?.sources?.[0] && <div className="mt-1 text-xs text-red-700/80">Rule: {att.sources[0].title}</div>}
          </div>
        </div>
      )}

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className="card p-6 lg:col-span-2">
          <div className="flex items-center justify-between"><h2 className="font-semibold">Attendance · Semester {me.semester}</h2><span className="text-sm text-slate-500">Overall {me.attendance?.overall_pct}%</span></div>
          <div className="mt-4 space-y-3">
            {Object.entries(subj).map(([code, v]) => (
              <div key={code}>
                <div className="flex justify-between text-sm"><span className="truncate">{courseName(code)} <span className="text-slate-400">{code}</span></span><b className={v < threshold ? "text-red-600" : "text-emerald-700"}>{v}%</b></div>
                <div className="relative mt-1 h-2.5 rounded-full bg-slate-100">
                  <div className={`h-2.5 rounded-full ${v < threshold ? "bg-bu-red" : "bg-emerald-500"}`} style={{ width: `${v}%` }} />
                  <div className="absolute -top-1 h-4.5 w-0.5 bg-bu-navy" style={{ left: `${threshold}%`, height: 18 }} title={`${threshold}% minimum`} />
                </div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">Black marker = {threshold}% minimum from the official attendance notification. Data from your ERP (demo snapshot).</p>
        </div>
        <div className="space-y-6">
          <div className="card p-6">
            <h2 className="font-semibold">Academic progress</h2>
            <div className="mt-3 flex items-end gap-2"><span className="font-display text-4xl font-bold text-bu-blue">{me.progress?.last_result?.cgpa}</span><span className="pb-1 text-sm text-slate-500">CGPA</span></div>
            <div className="mt-3 h-2.5 rounded-full bg-slate-100"><div className="h-2.5 rounded-full bg-bu-blue" style={{ width: `${me.progress?.progress_to_graduation_pct}%` }} /></div>
            <div className="mt-1 text-xs text-slate-500">{me.progress?.credits_earned} / {me.progress?.credits_required} credits · {me.progress?.progress_to_graduation_pct}% to graduation</div>
          </div>
          <div className="card p-6">
            <h2 className="font-semibold">Quick actions</h2>
            <div className="mt-3 grid gap-2">
              {([
                [AlertTriangle, "Am I eligible for end-sem in all courses?", "Am I eligible to sit the end-semester exam in all my courses based on my attendance?"],
                [FileSignature, "Write a leave application", "Write a leave application for 3 days due to illness"],
                [CalendarDays, "Academic calendar", "What are the key dates in the academic calendar for this semester?"],
                [BookOpen, "Unfair means (UFM) rules", "What are the rules and penalties for unfair means in examinations?"],
                [GraduationCap, "Scholarship renewal", "What are the conditions to renew my merit scholarship?"],
              ] as [LucideIcon, string, string][]).map(([Icon, t, q]) => (
                <Link key={t} to={`/chat?q=${encodeURIComponent(q)}`} className="flex items-center gap-3 rounded-xl border border-slate-100 px-3 py-2.5 text-sm hover:border-bu-blue/30 hover:bg-bu-mist">
                  <Icon size={16} className="text-bu-red" /> {t}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="card mt-6 p-6">
        <h2 className="font-semibold">Current courses</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {me.current_courses?.map(c => (
            <div key={c.code} className="rounded-xl border border-slate-100 p-3">
              <div className="text-xs text-slate-400">{c.code} · {c.credits} credits</div>
              <div className="mt-0.5 text-sm font-semibold">{c.name}</div>
              <div className="mt-1 text-xs text-slate-500">{c.category}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
