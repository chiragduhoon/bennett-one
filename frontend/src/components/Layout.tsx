import { useState } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { GraduationCap, LogIn, LogOut, Menu, ShieldCheck, Sparkles, X } from "lucide-react";
import { useAuth } from "../lib/auth";

// Navigation depends on who is using the platform: admission tools for applicants,
// academic tools for enrolled students, knowledge management for administrators.
const NAV_BY_ROLE: Record<string, { to: string; label: string }[]> = {
  prospective: [
    { to: "/programmes", label: "Programmes" },
    { to: "/eligibility", label: "Check Eligibility" },
    { to: "/fees", label: "Fees & Scholarships" },
    { to: "/policies", label: "Policies" },
  ],
  student: [
    { to: "/dashboard", label: "My Dashboard" },
    { to: "/academics", label: "Academic Rules" },
    { to: "/calendar", label: "Calendar & Exams" },
    { to: "/fees", label: "Fees & Scholarships" },
  ],
  faculty: [
    { to: "/academics", label: "Academic Rules" },
    { to: "/calendar", label: "Calendar & Exams" },
    { to: "/policies", label: "Policies" },
  ],
  admin: [
    { to: "/admin", label: "Admin Console" },
    { to: "/policies", label: "Document Library" },
    { to: "/programmes", label: "Programmes" },
  ],
};

export default function Layout() {
  const { me, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const links = NAV_BY_ROLE[me.role] || NAV_BY_ROLE.prospective;
  return (
    <div className="flex min-h-screen flex-col">
      <div className="bg-bu-navy text-[12px] text-white/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-1.5">
          <span className="flex items-center gap-1.5"><ShieldCheck size={13} className="text-bu-cyan" /> Answers grounded in official Bennett University documents</span>
          <a href="https://www.bennett.edu.in" target="_blank" rel="noreferrer" className="hidden hover:text-white sm:block">bennett.edu.in ↗</a>
        </div>
      </div>
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3">
          <Link to="/" className="flex shrink-0 items-center gap-3">
            <img src="/brand/logo-naac.png" alt="Bennett University — NAAC A+" className="h-9 w-auto" />
            <span className="hidden h-8 w-px bg-slate-200 md:block" />
            <span className="hidden font-display text-[15px] font-bold tracking-wide text-bu-navy md:block">
              BENNETT <span className="text-bu-red">ONE</span>
            </span>
          </Link>
          <nav className="ml-auto hidden items-center gap-1 lg:flex">
            {links.map(l => (
              <NavLink key={l.to} to={l.to} className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? "bg-bu-blue/10 text-bu-blue" : "text-slate-600 hover:text-bu-blue"}`}>
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2 lg:ml-2">
            <button onClick={() => nav("/chat")} className="btn-primary hidden whitespace-nowrap sm:inline-flex"><Sparkles size={16} /> Ask Bennett ONE</button>
            {me.role === "prospective" ? (
              <Link to="/login" className="btn-ghost"><LogIn size={16} /> <span className="hidden sm:inline">Sign in</span></Link>
            ) : (
              <div className="flex items-center gap-2">
                <div className="hidden whitespace-nowrap text-right leading-tight xl:block">
                  <div className="text-sm font-semibold">{me.name}</div>
                  <div className="text-[11px] text-slate-500">{me.role === "student" ? `${me.school} · Sem ${me.semester}` : me.role}</div>
                </div>
                <button onClick={() => { logout(); nav("/"); }} className="btn-ghost px-2.5" title="Sign out"><LogOut size={16} /></button>
              </div>
            )}
            <button className="btn-ghost px-2.5 lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">{open ? <X size={18} /> : <Menu size={18} />}</button>
          </div>
        </div>
        {open && (
          <nav className="border-t border-slate-100 px-4 py-2 lg:hidden">
            {[...links, { to: "/chat", label: "Ask Bennett ONE" }].map(l => (
              <NavLink key={l.to} to={l.to} onClick={() => setOpen(false)} className="block rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">{l.label}</NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="mt-16 bg-bu-navy text-white/70">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 md:grid-cols-4">
          <div className="md:col-span-2">
            <div className="flex items-center gap-3">
              <img src="/brand/crest.png" alt="" className="h-10 w-10" />
              <div>
                <div className="font-serif text-lg font-bold tracking-wider text-white">BENNETT UNIVERSITY</div>
                <div className="text-xs tracking-widest text-white/60">THE TIMES GROUP</div>
              </div>
            </div>
            <p className="mt-4 max-w-md text-sm">Preparing India to move with the times. BENNETT ONE brings admissions, academics and university policies into one intelligent, source-cited assistant.</p>
          </div>
          <div>
            <div className="mb-3 text-sm font-semibold text-white">Official links</div>
            <ul className="space-y-1.5 text-sm">
              <li><a className="hover:text-white" href="https://www.bennett.edu.in/admission/" target="_blank" rel="noreferrer">Admissions</a></li>
              <li><a className="hover:text-white" href="https://www.bennett.edu.in/admission/fee-structure/" target="_blank" rel="noreferrer">Fee structure</a></li>
              <li><a className="hover:text-white" href="https://www.bennett.edu.in/notices-registrar-office/" target="_blank" rel="noreferrer">Registrar notices</a></li>
              <li><a className="hover:text-white" href="https://student.bennetterp.camu.in" target="_blank" rel="noreferrer">Student ERP</a></li>
            </ul>
          </div>
          <div>
            <div className="mb-3 text-sm font-semibold text-white">About this project</div>
            <p className="flex items-start gap-2 text-sm"><GraduationCap size={16} className="mt-0.5 shrink-0 text-bu-cyan" /> A student project (SoAI, B.Tech AI). Not an official University service — always confirm decisions with the relevant office.</p>
          </div>
        </div>
        <div className="border-t border-white/10 py-4 text-center text-xs text-white/50">Plot No. 8-11, Tech Zone II, Greater Noida 201310 · Established under U.P. Act No. 24 of 2016</div>
      </footer>
    </div>
  );
}
