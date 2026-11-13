"""BENNETT ONE API (FastAPI).   Run:  uv run uvicorn app.main:app --reload --port 8000
Interactive docs at http://localhost:8000/docs
"""
from __future__ import annotations

import asyncio
import json
import queue
import threading
import uuid
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import run as run_agent
from app.auth.security import create_token, decode_token, verify_password
from app.config import get_settings
from app.db.models import (AdmissionCriteria, AuditLog, ChatMessage, Chunk, Conflict, Document, DocumentVersion,
                           FeeStructure, Programme, School, User)
from app.db.session import get_db
from app.rules import engine as R

app = FastAPI(title="BENNETT ONE API", version="0.1.0",
              description="University intelligence platform for Bennett University — grounded, cited answers.")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)


@app.on_event("startup")
def keep_models_warm():
    """Ollama unloads idle models after ~5 min, so the next question pays a 2-4 s reload. Ping both models
    every 4 minutes with keep_alive=30m (only ~10 GB on the GPU while the app is running)."""
    import httpx

    s = get_settings()

    def loop():
        import time as _t
        while True:
            for base, model, path, body in (
                (s.llm_base_url, s.llm_model, "/api/generate", {"prompt": "", "keep_alive": "30m"}),
                (s.embed_base_url or s.llm_base_url, s.embed_model, "/api/embed", {"input": "warm", "keep_alive": "30m"}),
            ):
                try:
                    httpx.post(base.removesuffix("/v1") + path, json={"model": model, **body}, timeout=60)
                except Exception:
                    pass  # tunnel down / GPU busy: try again next round
            _t.sleep(240)

    threading.Thread(target=loop, daemon=True).start()


# ------------------------------------------------------------------------------------------ auth
def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User | None:
    if not cred:
        return None
    payload = decode_token(cred.credentials)
    return db.get(User, int(payload["sub"])) if payload else None


def require_admin(user: User | None = Depends(current_user)) -> User:
    if not user or user.role != "admin":
        raise HTTPException(403, "Admin only")
    return user


def full_profile(user: User | None) -> dict:
    """Account profile + (for the demo student) private ERP-derived details like attendance."""
    if not user:
        return {"role": "prospective"}
    prof = {"role": user.role, "name": user.name, **(user.profile or {})}
    if user.role == "student":
        p = Path(get_settings().private_dir) / "erp" / "demo_student_profile.yaml"
        if p.exists():
            erp = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            prof.update({"attendance": erp.get("attendance"), "current_courses": erp.get("current_courses"),
                         "progress": erp.get("progress")})
    return prof


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter_by(email=body.email.lower().strip()).one_or_none()
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "Invalid email or password")
    db.add(AuditLog(user_id=u.id, action="login"))
    db.commit()
    return {"token": create_token(u.id, u.role), "user": {"id": u.id, "name": u.name, "role": u.role, "email": u.email}}


@app.get("/api/me")
def me(user: User | None = Depends(current_user)):
    if not user:
        return {"role": "prospective"}
    return {"id": user.id, "email": user.email, **full_profile(user)}


# ------------------------------------------------------------------------------------------ chat
class ChatIn(BaseModel):
    message: str
    session_id: str | None = None


def _history(db: Session, sid: str) -> list[dict]:
    rows = db.query(ChatMessage).filter_by(session_id=sid).order_by(ChatMessage.id.desc()).limit(8).all()
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def _memory(db: Session, sid: str) -> dict:
    """What the user already told us in THIS chat (marks, programme, scores...), saved with the last answer."""
    row = (db.query(ChatMessage).filter_by(session_id=sid, role="assistant")
           .order_by(ChatMessage.id.desc()).first())
    return ((row.meta or {}).get("memory") or {}) if row else {}


@app.post("/api/chat")
def chat_once(body: ChatIn, user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    """Non-streaming chat (useful for tests / evaluation)."""
    sid = body.session_id or uuid.uuid4().hex
    result = run_agent(body.message, full_profile(user), _history(db, sid), memory=_memory(db, sid))
    _save(db, sid, user, body.message, result)
    return {"session_id": sid, **result}


@app.post("/api/chat/stream")
async def chat_stream(body: ChatIn, user: User | None = Depends(current_user), db: Session = Depends(get_db)):
    """Server-Sent Events: `step` (agent progress), `sources`, then `final` (answer + citations + rule result)."""
    sid = body.session_id or uuid.uuid4().hex
    profile, history, memory = full_profile(user), _history(db, sid), _memory(db, sid)
    q: queue.Queue = queue.Queue()

    def worker():
        try:
            res = run_agent(body.message, profile, history, emit=lambda k, d: q.put((k, d)), memory=memory)
            q.put(("final", res))
        except Exception as e:  # surface errors to the UI instead of hanging
            q.put(("error", str(e)))
        q.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def events():
        yield {"event": "session", "data": json.dumps({"session_id": sid})}
        while True:
            item = await asyncio.get_event_loop().run_in_executor(None, q.get)
            if item is None:
                break
            kind, data = item
            if kind == "final":
                _save(db, sid, user, body.message, data)
            yield {"event": kind, "data": json.dumps(data, default=str, ensure_ascii=False)}

    return EventSourceResponse(events())


def _save(db: Session, sid: str, user: User | None, question: str, result: dict):
    uid = user.id if user else None
    db.add(ChatMessage(session_id=sid, user_id=uid, role="user", content=question))
    db.add(ChatMessage(session_id=sid, user_id=uid, role="assistant", content=result.get("answer", ""),
                       meta={k: result.get(k) for k in ("citations", "status", "intent", "warnings", "memory")}))
    db.commit()


# ------------------------------------------------------------------------------------------ catalogue
@app.get("/api/schools")
def schools(db: Session = Depends(get_db)):
    counts = dict(db.query(Programme.school_id, func.count()).group_by(Programme.school_id).all())
    return [{"id": s.id, "name": s.name, "programme_count": counts.get(s.id, 0)} for s in db.query(School).order_by(School.name)]


@app.get("/api/programmes")
def programmes(school: str | None = None, level: str | None = None, q: str | None = None, db: Session = Depends(get_db)):
    qs = db.query(Programme)
    if school:
        qs = qs.filter(Programme.school_id == school)
    if level:
        qs = qs.filter(Programme.level == level)
    if q:
        qs = qs.filter(Programme.name.ilike(f"%{q}%"))
    return [{"id": p.id, "name": p.name, "school_id": p.school_id, "level": p.level, "duration": p.duration,
             "credits": p.credits, "summary": (p.summary or "")[:300], "url": p.url}
            for p in qs.order_by(Programme.name).all()]


@app.get("/api/programmes/{pid}")
def programme(pid: str, db: Session = Depends(get_db)):
    p = db.get(Programme, pid)
    if not p:
        raise HTTPException(404)
    from app.agents.graph import _best_match
    crit = db.query(AdmissionCriteria).all()
    fees = db.query(FeeStructure).all()
    c_name, cs = _best_match(p.name, [c.programme_name for c in crit])
    f_name, fs = _best_match(p.name, [f.programme_name for f in fees])
    c = next((x for x in crit if x.programme_name == c_name), None) if cs >= 0.75 else None
    f = next((x for x in fees if x.programme_name == f_name), None) if fs >= 0.75 else None
    return {"id": p.id, "name": p.name, "school_id": p.school_id, "level": p.level, "duration": p.duration,
            "credits": p.credits, "specialisations": p.specialisations, "summary": p.summary, "url": p.url,
            "criteria": c and {"eligibility": c.eligibility_text, "selection": c.selection_text, "nri": c.nri_text,
                               "rules": c.rules, "source_url": c.source_url, "programme_name": c.programme_name},
            "fees": f and {"academic_year": f.academic_year, "tuition_by_year": f.tuition_by_year,
                           "total_tuition": f.total_tuition, "tables": f.tables, "other_charges": f.other_charges,
                           "notes": f.notes, "source_url": f.source_url, "programme_name": f.programme_name}}


@app.get("/api/criteria")
def criteria(db: Session = Depends(get_db)):
    return [{"programme": c.programme_name, "programme_id": c.programme_id, "school_id": c.school_id, "rules": c.rules}
            for c in db.query(AdmissionCriteria).order_by(AdmissionCriteria.programme_name)]


class EligibilityIn(BaseModel):
    programme: str
    marks: dict[str, float] = {}
    board: str | None = None
    ib_credits: int | None = None
    graduation_pct: float | None = None


@app.post("/api/eligibility")
def eligibility(body: EligibilityIn, db: Session = Depends(get_db)):
    c = db.query(AdmissionCriteria).filter_by(programme_name=body.programme).one_or_none()
    if not c:
        raise HTTPException(404, "Unknown programme")
    r = R.check_admission(body.model_dump(), c.rules, {"title": "Eligibility and Selection Criteria", "url": c.source_url})
    return {"programme": c.programme_name, "school_id": c.school_id, "eligibility_text": c.eligibility_text,
            "selection_text": c.selection_text, **r.to_dict()}


class AttendanceIn(BaseModel):
    courses: dict[str, float]
    school_id: str | None = None


@app.post("/api/attendance/check")
def attendance(body: AttendanceIn):
    return R.check_attendance(body.courses, body.school_id).to_dict()


# ------------------------------------------------------------------------------------------ documents / sources
@app.get("/api/documents")
def documents(category: str | None = None, school: str | None = None, db: Session = Depends(get_db)):
    qs = db.query(Document)
    if category:
        qs = qs.filter(Document.category == category)
    if school:
        qs = qs.filter((Document.school_id == school) | (Document.school_id.is_(None)))
    out = []
    for d in qs.order_by(Document.category, Document.title).all():
        vs = sorted(d.versions, key=lambda v: v.id)
        if not vs:
            continue  # e.g. scanned PDFs waiting for OCR
        out.append({"id": d.id, "title": d.title, "family": d.family, "category": d.category, "school_id": d.school_id,
                    "status": d.status, "versions": [{"id": v.id, "label": v.version_label, "is_current": v.is_current,
                                                       "url": v.source_url, "pages": v.pages} for v in vs]})
    return out


@app.get("/api/versions/{vid}/file")
def version_file(vid: int, db: Session = Depends(get_db)):
    """Serve the original PDF so the UI can open it at the cited page (#page=N)."""
    v = db.get(DocumentVersion, vid)
    if not v or not v.file_path.lower().endswith(".pdf"):
        raise HTTPException(404)
    return FileResponse(v.file_path, media_type="application/pdf")


@app.get("/api/chunks/{cid}")
def chunk(cid: int, db: Session = Depends(get_db)):
    c = db.get(Chunk, cid)
    if not c:
        raise HTTPException(404)
    v = db.get(DocumentVersion, c.version_id)
    return {"id": c.id, "text": c.text, "page": c.page, "section": c.section, "version_id": v.id,
            "is_pdf": v.file_path.lower().endswith(".pdf"), "url": v.source_url, "title": v.document.title,
            "version": v.version_label, "is_current": v.is_current}


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    return {"schools": db.query(School).count(), "programmes": db.query(Programme).count(),
            "documents": db.query(Document).count(), "versions": db.query(DocumentVersion).count(),
            "chunks": db.query(Chunk).count(), "criteria": db.query(AdmissionCriteria).count(),
            "fee_structures": db.query(FeeStructure).count()}


# ------------------------------------------------------------------------------------------ admin
@app.get("/api/admin/versions/{family_id}/diff")
def diff(family_id: int, a: int, b: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    import difflib

    def full(vid):
        return "\n".join(c.text for c in db.query(Chunk).filter_by(version_id=vid).order_by(Chunk.id))
    lines = difflib.unified_diff(full(a).splitlines(), full(b).splitlines(), lineterm="", n=1)
    return {"diff": list(lines)[:2000]}


@app.post("/api/admin/upload")
async def upload(file: UploadFile = File(...), title: str = Form(...), category: str = Form("general"),
                 school_id: str | None = Form(None), academic_year: str | None = Form(None),
                 admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Uploads go in as PENDING: a document never becomes authoritative just because it was uploaded."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "PDF only")
    data = await file.read()
    if not data.startswith(b"%PDF") or len(data) > 30_000_000:
        raise HTTPException(400, "Invalid or too large PDF")
    dest = Path(get_settings().raw_dir) / "uploads" / f"{uuid.uuid4().hex}_{Path(file.filename).name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    d = Document(family=title.lower(), title=title, category=category, school_id=school_id or None, status="pending")
    db.add(d)
    db.flush()
    db.add(DocumentVersion(document_id=d.id, version_label=academic_year or "upload", academic_year=academic_year,
                           is_current=False, source_url="uploaded", file_path=str(dest)))
    db.add(AuditLog(user_id=admin.id, action="upload", detail={"document_id": d.id, "title": title}))
    db.commit()
    return {"document_id": d.id, "status": "pending"}


@app.post("/api/admin/documents/{doc_id}/{decision}")
def decide(doc_id: int, decision: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if decision not in ("approve", "reject"):
        raise HTTPException(400)
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404)
    d.status = "approved" if decision == "approve" else "rejected"
    db.add(AuditLog(user_id=admin.id, action=f"document_{decision}", detail={"document_id": doc_id}))
    db.commit()
    return {"id": d.id, "status": d.status, "note": "Approved uploads are indexed by the ingestion job."}


@app.get("/api/admin/conflicts")
def conflicts(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    known = R.superseded_rules()
    stored = [{"id": c.id, "topic": c.topic, "explanation": c.explanation, "status": c.status} for c in db.query(Conflict)]
    return {"policy_conflicts": known, "flagged": stored}


@app.get("/api/admin/audit")
def audit(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"at": a.created_at, "user_id": a.user_id, "action": a.action, "detail": a.detail}
            for a in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200)]


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"ok": True}
