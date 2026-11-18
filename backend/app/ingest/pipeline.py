"""Ingestion: official files -> clean page text -> chunks -> Postgres (text + keyword index) + Qdrant (vectors).

Run:  uv run python -m app.ingest.pipeline [--reset] [--limit N]

Steps per file
 1. classify    : index it? school / category / family / academic year (app.ingest.classify)
 2. extract     : PyMuPDF page-by-page text (keeps page numbers for citations)
 3. chunk       : ~1000-char passages along paragraph boundaries, 1-paragraph overlap,
                  remembering the most recent heading as `section`
 4. version     : group files of the same family; newest = is_current, older = superseded
 5. store       : chunks -> Postgres (with tsvector for keyword search)
 6. embed+index : bge-m3 vectors -> Qdrant with metadata payload used for filtering
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF
from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, PayloadSchemaType, PointStruct, VectorParams)
from sqlalchemy import delete, text

from app.config import get_settings
from app.db.models import Base, Chunk, Document, DocumentVersion, Programme, School
from app.db.session import SessionLocal, engine
from app.ingest import classify as C
from app.ingest.ocr import pages_with_ocr  # text layer first, OCR for scanned pages (cached)
from app.llm.llm_client import embed

warnings.filterwarnings("ignore", message="Payload indexes have no effect")

USE_OCR = True
TARGET = 1000     # chars per chunk (≈ 220 tokens): small enough to be precise, big enough for context
MIN_PAGE_CHARS = 40  # pages with less text are probably scanned images (OCR = future work)


@dataclass
class SourceFile:
    path: Path
    rel: str
    url: str
    title: str
    kind: str  # pdf | html
    category: str
    school_id: str | None
    family: str
    academic_year: str | None
    published_on: date | None
    sha256: str
    audience: str
    pages: list[tuple[int, str]] = field(default_factory=list)


HEADING = re.compile(r"^(\d+(\.\d+)*\.?\s+[A-Z][^\n]{2,90}|[A-Z][A-Z &/,()'-]{4,90}|(Section|Chapter|Clause|Rule|Article)\s+\d+[^\n]{0,80})$")


def clean(t: str) -> str:
    t = t.replace(" ", " ").replace("", "•")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    chunks, section = [], None
    for page_no, txt in pages:
        paras = [p.strip() for p in re.split(r"\n\s*\n|(?<=[.:;])\n(?=[A-Z0-9•(])", txt) if p.strip()]
        buf: list[str] = []
        size = 0
        for p in paras:
            first = p.split("\n", 1)[0].strip()
            if len(first) < 95 and HEADING.match(first):
                section = first[:280]
            if size + len(p) > TARGET and buf:
                chunks.append({"page": page_no, "section": section, "text": "\n".join(buf)})
                buf, size = [buf[-1]] if len(buf[-1]) < 400 else [], 0  # 1-paragraph overlap
                size = sum(len(b) for b in buf)
            # hard-split very long paragraphs
            while len(p) > TARGET * 1.6:
                cut = p.rfind(". ", 0, TARGET) + 1 or TARGET
                chunks.append({"page": page_no, "section": section, "text": "\n".join(buf + [p[:cut]])})
                buf, size, p = [], 0, p[cut:].strip()
            buf.append(p)
            size += len(p)
        if buf and sum(len(b) for b in buf) > 60:
            chunks.append({"page": page_no, "section": section, "text": "\n".join(buf)})
    return chunks


def pdf_pages(path: Path) -> list[tuple[int, str]]:
    out = []
    with fitz.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            t = clean(page.get_text("text"))
            if len(t) >= MIN_PAGE_CHARS:
                out.append((i, t))
    return out


def discover(settings) -> list[SourceFile]:
    raw = Path(settings.raw_dir)
    manifest = [json.loads(l) for l in (raw / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    files: dict[str, SourceFile] = {}
    seen_sha: set[str] = set()
    db = SessionLocal()
    prog_school = {p.url.rstrip("/"): p.school_id for p in db.query(Programme).filter(Programme.url.isnot(None))}
    school_by_slug = {re.sub(r"[^a-z]", "", s.name.lower()): s.id for s in db.query(School)}
    db.close()

    for r in manifest:
        f = raw / r["file"]
        if not f.exists() or r["file"] in files:
            continue
        name = f.name
        if r["type"] == "pdf":
            rel = r["file"][4:]
            if not C.should_index_pdf(rel, f.stat().st_size):
                continue
            sha = r.get("sha256") or hashlib.sha256(f.read_bytes()).hexdigest()
            if sha in seen_sha:
                continue
            seen_sha.add(sha)
            cat = C.category_of(name)
            files[r["file"]] = SourceFile(
                path=f, rel=rel, url=r["url"], title=C.display_title(name),
                kind="pdf", category=cat, school_id=C.school_of(name), family=C.family_of(name),
                academic_year=C.academic_year_of(name), published_on=C.published_from_path(rel), sha256=sha,
                audience=C.audience_of(cat))
        else:
            slug = f.stem
            if not C.should_index_html(slug) or C.EXCLUDE.search(slug):
                continue
            tfile = raw / "text" / f"{slug}.txt"
            if not tfile.exists():
                continue
            body = tfile.read_text(encoding="utf-8")
            title = (re.search(r"^TITLE: (.*)$", body, re.M) or [None, slug])[1]
            school = prog_school.get(r["url"].rstrip("/")) if "/programs/" in r["url"] else None
            if slug.startswith("schools__"):
                key = re.sub(r"[^a-z]", "", slug.split("__", 1)[1].lower())
                school = next((v for k, v in school_by_slug.items() if k.startswith(key[:14]) or key.startswith(k[:14])), None)
            cat = "admission" if slug.startswith(("admission", "programs", "international", "global", "three")) else C.category_of(slug)
            if "fee-structure" in slug:
                cat = "fees"
            elif "scholarship" in slug:
                cat = "scholarship"
            elif "hostel" in slug:
                cat = "hostel"
            files[r["file"]] = SourceFile(
                path=tfile, rel=slug, url=r["url"], title=title.split("|")[0].split("@")[0].strip()[:300], kind="html",
                category=cat, school_id=school, family="web:" + slug, academic_year="2026-27" if cat == "fees" else None,
                published_on=None, sha256=r.get("sha256", ""), audience=C.audience_of(cat))
    return list(files.values())


def version_key(sf: SourceFile):
    y = int(sf.academic_year[:4]) if sf.academic_year else (sf.published_on.year if sf.published_on else 0)
    return (y, sf.published_on or date(1900, 1, 1), "compressed" not in sf.rel.lower())


def qdrant(settings) -> QdrantClient:
    return QdrantClient(path=settings.qdrant_path)


def ensure_collection(q: QdrantClient, settings, reset: bool):
    name = settings.qdrant_collection
    if reset and q.collection_exists(name):
        q.delete_collection(name)
    if not q.collection_exists(name):
        q.create_collection(name, vectors_config=VectorParams(size=settings.embed_dim, distance=Distance.COSINE))
        for fld in ("school_id", "category", "is_current", "family", "audience", "academic_year"):
            try:
                q.create_payload_index(name, fld, PayloadSchemaType.KEYWORD if fld != "is_current" else PayloadSchemaType.BOOL)
            except Exception:
                pass  # local mode ignores payload indexes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop all documents/chunks/vectors first")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-ocr", action="store_true", help="skip OCR (scanned PDFs are left out)")
    args = ap.parse_args()
    global USE_OCR
    USE_OCR = not args.no_ocr
    s = get_settings()
    Base.metadata.create_all(engine())

    files = discover(s)
    if args.limit:
        files = files[: args.limit]
    print(f"{len(files)} files selected ({sum(f.kind == 'pdf' for f in files)} PDFs, {sum(f.kind == 'html' for f in files)} web pages)")

    db = SessionLocal()
    if args.reset:
        db.execute(text("TRUNCATE chunks, document_versions, documents, conflicts RESTART IDENTITY CASCADE"))
        db.commit()
    q = qdrant(s)
    ensure_collection(q, s, args.reset)

    # group into families -> decide current version
    fams: dict[tuple, list[SourceFile]] = defaultdict(list)
    for f in files:
        fams[(f.family, f.school_id)].append(f)

    # Resume support: families already fully ingested are skipped. The last family before a crash
    # may be half-done, so the most recently created document is deleted and redone.
    done: set[tuple] = set()
    if not args.reset:
        last = db.query(Document).order_by(Document.id.desc()).first()
        if last:
            vids = [v.id for v in last.versions]
            if vids:
                from qdrant_client.models import FieldCondition, Filter, MatchAny
                q.delete(s.qdrant_collection, points_selector=Filter(must=[FieldCondition(key="version_id", match=MatchAny(any=vids))]))
            db.delete(last)
            db.commit()
        done = {(d.family, d.school_id) for d in db.query(Document)}
        print(f"resuming: {len(done)} families already ingested")

    total_chunks = 0
    for (family, school_id), group in sorted(fams.items(), key=lambda kv: kv[0][0]):
        if (family, school_id) in done:
            continue
        group.sort(key=version_key)
        # drop same-year duplicates (e.g. "X.pdf" and "X_compressed.pdf")
        uniq: dict = {}
        for g in group:
            uniq[(g.academic_year, g.published_on if not g.academic_year else None)] = g
        group = sorted(uniq.values(), key=version_key)
        newest = group[-1]
        doc = Document(family=family, title=newest.title, category=newest.category, school_id=school_id,
                       audience=newest.audience, status="approved")
        db.add(doc)
        db.flush()
        prev_id = None
        for sf in group:
            try:
                pages = ([(n, clean(t)) for n, t in (pages_with_ocr(sf.path) if USE_OCR else pdf_pages(sf.path))]
                         if sf.kind == "pdf" else [(1, clean(sf.path.read_text(encoding="utf-8").split("\n\n", 1)[-1]))])
            except Exception as e:  # corrupt PDF etc.
                print("  ! skip", sf.rel, e)
                continue
            if not pages:
                print("  ! no extractable text (scanned?)", sf.rel)
                continue
            is_current = sf is newest
            v = DocumentVersion(document_id=doc.id, version_label=sf.academic_year or (sf.published_on.strftime("%Y-%m") if sf.published_on else "web"),
                                academic_year=sf.academic_year, published_on=sf.published_on, is_current=is_current,
                                supersedes_id=prev_id, source_url=sf.url, file_path=str(sf.path), sha256=sf.sha256,
                                pages=len(pages))
            db.add(v)
            db.flush()
            prev_id = v.id
            chunks = chunk_pages(pages)
            rows = [Chunk(version_id=v.id, page=c["page"] if sf.kind == "pdf" else None, section=c["section"], text=c["text"]) for c in chunks]
            if not rows:
                print("  ! no chunks", sf.rel)
                continue
            db.add_all(rows)
            db.flush()
            vectors = embed([f"{sf.title}\n{r.section or ''}\n{r.text}" for r in rows])
            q.upsert(s.qdrant_collection, points=[
                PointStruct(id=r.id, vector=vec, payload={
                    "chunk_id": r.id, "version_id": v.id, "document_id": doc.id, "family": family,
                    "title": sf.title, "category": sf.category, "school_id": school_id or "ALL",
                    "audience": sf.audience, "academic_year": sf.academic_year or "", "is_current": is_current,
                    "page": r.page, "section": r.section or "", "url": sf.url, "kind": sf.kind})
                for r, vec in zip(rows, vectors)])
            db.commit()
            total_chunks += len(rows)
            flag = "CURRENT" if is_current else "superseded"
            print(f"  [{flag:10}] {sf.kind} {school_id or 'ALL':5} {sf.category:14} {sf.academic_year or '':8} {len(pages):3}p {len(rows):4}ch  {sf.title[:70]}")

    db.execute(text("UPDATE chunks SET tsv = to_tsvector('english', coalesce(section,'') || ' ' || text) WHERE tsv IS NULL"))
    db.commit()
    print(f"\nDone. documents={db.query(Document).count()} versions={db.query(DocumentVersion).count()} "
          f"chunks={db.query(Chunk).count()} (+{total_chunks} this run)")


if __name__ == "__main__":
    main()
