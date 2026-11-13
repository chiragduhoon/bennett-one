"""Academic calendars -> a structured date table.

Why: a calendar is a day-by-day table. Chunking it for RAG splits one exam period across many
chunks, so the LLM only sees fragments ("starts 10-12-2026" but not "ends 24-12-2026").
Parsing it into rows (date, day type, event) lets us answer date questions exactly and
merge consecutive days into ranges: "End Semester Examination: 10 Dec – 24 Dec 2026".

Run (after ingestion):  uv run python -m app.ingest.calendar
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime

import pymupdf
from sqlalchemy import Boolean, Date, Integer, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, Document, DocumentVersion
from app.db.session import SessionLocal, engine

DATE_RE = re.compile(r"^(\d{2})[-/.](\d{2})[-/.](\d{4})\b(.*)$")
DAY_TYPES = ("Teaching Day", "Holiday", "Non-Teaching Day", "Examination Day", "Examination")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(Integer, index=True)
    calendar: Mapped[str] = mapped_column(String(200))        # e.g. "Academic Calendar 2026-27"
    audience: Mapped[str] = mapped_column(String(30))         # returning / freshmen / all
    academic_year: Mapped[str | None] = mapped_column(String(10))
    day: Mapped[date] = mapped_column(Date, index=True)
    day_type: Mapped[str | None] = mapped_column(String(40))  # Teaching Day / Holiday
    event: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean)
    source_url: Mapped[str] = mapped_column(String(500))


def parse_calendar(path: str) -> list[dict]:
    """Rows look like: '10-12-2026 Thursday\\nTeaching Day*\\nEnd Semester Examination ...' (text may wrap)."""
    rows: list[dict] = []
    cur = None
    with pymupdf.open(path) as doc:
        for pno, page in enumerate(doc, start=1):
            for raw in page.get_text("text").splitlines():
                line = " ".join(raw.split())
                if not line:
                    continue
                m = DATE_RE.match(line)
                if m:
                    try:
                        d = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                    except ValueError:
                        continue
                    cur = {"day": d, "page": pno, "day_type": None, "events": []}
                    rows.append(cur)
                    rest = m.group(4).strip()
                    rest = re.sub(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", "", rest).strip()
                    line = rest
                    if not line:
                        continue
                if cur is None:
                    continue
                for dt in DAY_TYPES:
                    if line.lower().startswith(dt.lower()):
                        cur["day_type"] = cur["day_type"] or dt
                        line = line[len(dt):].lstrip("* ").strip()
                if not line or line in ("Day", "Date", "Remarks"):
                    continue
                # continuation of a wrapped event line
                if cur["events"] and (line[0].islower() or line.startswith("(") or cur["events"][-1].endswith(("has", "the", "of", "and", "–", "-"))):
                    cur["events"][-1] += " " + line
                else:
                    cur["events"].append(line)
    return rows


def main() -> None:
    Base.metadata.create_all(engine())
    db = SessionLocal()
    db.query(CalendarEvent).delete()
    q = (select(DocumentVersion, Document).join(Document, Document.id == DocumentVersion.document_id)
         .where(Document.category == "calendar"))
    n = 0
    for v, d in db.execute(q).all():
        if not v.file_path.lower().endswith(".pdf"):
            continue
        audience = "freshmen" if "freshm" in (d.family + v.file_path).lower() else "returning/all"
        rows = parse_calendar(v.file_path)
        for r in rows:
            events = r["events"] or [None]
            for ev in events:
                db.add(CalendarEvent(version_id=v.id, calendar=d.title, audience=audience, academic_year=v.academic_year,
                                     day=r["day"], day_type=r["day_type"], event=ev, page=r["page"],
                                     is_current=v.is_current, source_url=v.source_url))
                n += 1
        print(f"{'CURRENT ' if v.is_current else 'old     '} {d.title[:60]:60} {v.academic_year or '':8} {len(rows)} days")
    db.commit()
    print(f"{n} calendar rows")


def find_events(query: str, academic_year: str | None = None, audience: str | None = None, limit: int = 12) -> list[dict]:
    """Keyword match on current calendars, merged into date ranges per event."""
    stop = {"when", "what", "is", "the", "for", "of", "a", "an", "start", "starts", "end", "ends", "date", "dates", "sem",
            "semester", "do", "does", "will", "be", "my", "this", "year", "ay", "in", "on", "and", "are", "there"}
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in stop and len(w) > 2]
    syn = {"endsem": ["end", "semester", "examination"], "midsem": ["mid", "term"], "exam": ["examination"],
           "exams": ["examination"], "holidays": ["holiday"], "vacation": ["vacation", "break"], "diwali": ["diwali", "deepavali"]}
    terms = []
    for w in words:
        terms += syn.get(w, [w])
    sem = "odd" if re.search(r"\bodd\b", query.lower()) else "even" if re.search(r"\beven\b", query.lower()) else None
    if re.search(r"end\s*-?\s*sem|end\s*term|endsem", query.lower()):
        terms += ["end semester examination"]
    with SessionLocal() as db:
        qs = db.query(CalendarEvent).filter(CalendarEvent.is_current.is_(True), CalendarEvent.event.isnot(None))
        if audience:
            qs = qs.filter(CalendarEvent.audience == audience)
        rows = qs.order_by(CalendarEvent.day).all()
    def score(ev: str) -> int:
        e = ev.lower()
        s = sum(2 if " " in t else 1 for t in set(terms) if t in e)
        if sem and sem not in e and ("odd" in e or "even" in e):
            s -= 3
        return s
    hits = [r for r in rows if score(r.event) > 0]
    if not hits:
        return []
    best = max(score(r.event) for r in hits)
    hits = [r for r in hits if score(r.event) >= max(1, best - 1)]
    groups: dict[tuple, list] = defaultdict(list)
    for r in hits:
        key = (re.sub(r"\s*\(.*?\)\s*$", "", r.event).strip(), r.calendar, r.audience)
        groups[key].append(r)
    out = []
    for (ev, cal, aud), rs in groups.items():
        days = sorted({r.day for r in rs})
        out.append({"event": rs[0].event, "from": days[0].isoformat(), "to": days[-1].isoformat(), "days": len(days),
                    "calendar": cal, "audience": aud, "page": rs[0].page, "source_url": rs[0].source_url})
    out.sort(key=lambda x: x["from"])
    return out[:limit]


if __name__ == "__main__":
    main()
