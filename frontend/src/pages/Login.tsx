import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogIn } from "lucide-react";
import { useAuth } from "../lib/auth";

const DEMO = [["Student (SoAI, Sem 5)", "student@bennett.demo", "/dashboard"], ["Administrator", "admin@bennett.demo", "/admin"]] as const;

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  async function go(e: string, p: string, to = "/dashboard") {
    setErr("");
    try { await login(e, p); nav(e.startsWith("admin") ? "/admin" : to); } catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
  }
  return (
    <div className="grid min-h-[calc(100vh-108px)] lg:grid-cols-2">
      <div className="hero-gradient relative hidden items-end p-10 text-white lg:flex">
        <img src="/brand/photos/atrium.jpg" alt="" className="absolute inset-0 h-full w-full object-cover opacity-45" />
        <div className="absolute inset-0 bg-gradient-to-t from-bu-navy via-bu-navy/50 to-transparent" />
        <div className="relative">
          <img src="/brand/crest.png" alt="" className="h-14 w-14" />
          <h2 className="mt-4 font-serif text-3xl font-bold tracking-wider">BENNETT UNIVERSITY</h2>
          <p className="mt-2 max-w-sm text-white/80">Sign in to get answers that apply to your school, programme and semester.</p>
        </div>
      </div>
      <div className="grid place-items-center p-6">
        <form onSubmit={e => { e.preventDefault(); go(email, pw); }} className="card w-full max-w-md p-8">
          <h1 className="text-2xl font-bold">Sign in to BENNETT ONE</h1>
          <p className="mt-1 text-sm text-slate-500">Prospective students can use everything without an account.</p>
          <label className="label mt-6">Email</label><input className="input" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@bennett.edu.in" />
          <label className="label mt-4">Password</label><input className="input" type="password" value={pw} onChange={e => setPw(e.target.value)} />
          {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
          <button className="btn-primary mt-6 w-full"><LogIn size={16} /> Sign in</button>
          <div className="mt-6 border-t border-slate-100 pt-4">
            <div className="label">Demo accounts</div>
            <div className="grid gap-2">{DEMO.map(([l, e, to]) => <button type="button" key={e} onClick={() => go(e, "bennett123", to)} className="btn-ghost justify-between text-left"><span>{l}</span><span className="text-xs text-slate-400">{e}</span></button>)}</div>
          </div>
        </form>
      </div>
    </div>
  );
}
