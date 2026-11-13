"""Create tables and load data/seed/*.yaml (scraped from bennett.edu.in) into PostgreSQL.

Run:  uv run python -m app.db.load_seed            (idempotent: clears & reloads seed tables)
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml
from app.auth.security import hash_password
from sqlalchemy import delete, text

from app.config import get_settings
from app.db.models import (AdmissionCriteria, Base, FeeStructure, Programme, School, User)
from app.db.session import SessionLocal, engine


def norm(s: str) -> str:
    s = s.lower().replace("&", "and")
    s = re.sub(r"\b(hons|honours)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def level_of(name: str) -> str:
    n = name.lower()
    if "ph.d" in n or "phd" in n:
        return "PhD"
    if n.startswith(("m.", "m ", "mba", "mca", "ma ", "ll.m", "msc", "m.sc", "m.tech", "m. tech", "m.des", "masters")):
        return "PG"
    if n.startswith(("pgd", "pg ", "post graduate", "pgc", "six months")):
        return "Diploma"
    return "UG"


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def main() -> None:
    s = get_settings()
    seed = Path(s.seed_dir)
    Base.metadata.create_all(engine())
    with engine().begin() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    schools = load(seed / "schools.yaml")
    elig = load(seed / "eligibility.yaml")
    fees = load(seed / "fees.yaml")
    progs = load(seed / "programmes.yaml")

    db = SessionLocal()
    for model in (AdmissionCriteria, FeeStructure, Programme):
        db.execute(delete(model))
    db.commit()

    for sc in schools:
        db.merge(School(id=sc["code"], name=sc["name"]))
    db.commit()

    # Programme -> school mapping comes from the eligibility page tabs (authoritative grouping).
    elig_by_norm = {norm(e["programme"]): e for e in elig}

    def school_for(name: str) -> str | None:
        n = norm(name)
        best, score = None, 0.0
        for k, e in elig_by_norm.items():
            r = SequenceMatcher(None, n, k).ratio()
            if r > score:
                best, score = e, r
        return best["school_code"] if best and score >= 0.82 else None

    seen = set()
    for p in progs:
        title = p.get("title") or ""
        if not title or "/programs/" not in p.get("url", ""):
            continue
        pid = re.sub(r"[^a-z0-9]+", "-", p["url"].rstrip("/").rsplit("/", 1)[-1].lower())
        if pid in seen:
            continue
        seen.add(pid)
        db.add(Programme(id=pid, name=title, school_id=school_for(title), level=level_of(title),
                         duration=p.get("duration"), credits=p.get("credits"),
                         specialisations=p.get("specialisations") or p.get("specializations"),
                         summary=p.get("summary"), url=p["url"]))
    # Programmes that only appear on the eligibility page
    for e in elig:
        pid = e["programme_id"]
        if pid not in seen:
            seen.add(pid)
            db.add(Programme(id=pid, name=e["programme"], school_id=e["school_code"] or None,
                             level=level_of(e["programme"]), url=e["source_url"]))

    for e in elig:
        db.add(AdmissionCriteria(programme_name=e["programme"], programme_id=e["programme_id"],
                                 school_id=e["school_code"] or None, academic_year="2026-27",
                                 eligibility_text=e["eligibility_text"], nri_text=e.get("nri_eligibility_text"),
                                 selection_text=e.get("selection_text"), rules=e["rules"],
                                 source_url=e["source_url"]))
    for f in fees:
        db.add(FeeStructure(programme_name=f["programme"], programme_id=f["programme_id"],
                            academic_year=f.get("academic_year"), tuition_by_year=f.get("tuition_by_year"),
                            total_tuition=f.get("total_tuition") if isinstance(f.get("total_tuition"), int) else None,
                            tables=f.get("tables", []), other_charges=f.get("other_charges"),
                            notes=f.get("notes"), source_url=f["source_url"]))

    # Demo accounts (local only). Passwords are for the demo, documented in README.
    demo = [
        ("student@bennett.demo", "Chirag Duhoon", "student",
         {"school": "SoAI", "programme": "B.Tech (Artificial Intelligence)", "programme_id": "b-tech-artificial-intelligence",
          "semester": 5, "year": 3, "academic_year": "2026-27"}),
        ("admin@bennett.demo", "Admin Office", "admin", {}),
        ("faculty@bennett.demo", "Faculty Member", "faculty", {"school": "SoAI"}),
    ]
    for email, name, role, profile in demo:
        u = db.query(User).filter_by(email=email).one_or_none()
        if not u:
            db.add(User(email=email, name=name, role=role, password_hash=hash_password("bennett123"), profile=profile))
    db.commit()

    print("schools", db.query(School).count(), "| programmes", db.query(Programme).count(),
          "| with school", db.query(Programme).filter(Programme.school_id.isnot(None)).count(),
          "| criteria", db.query(AdmissionCriteria).count(), "| fees", db.query(FeeStructure).count(),
          "| users", db.query(User).count())


if __name__ == "__main__":
    main()
