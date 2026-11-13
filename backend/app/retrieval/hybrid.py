"""Hybrid retrieval = semantic (Qdrant vectors) + keyword (Postgres full-text) fused with RRF.

Filters applied INSIDE both searches (not after):
  * is_current = true          -> superseded policy versions never reach the answer
  * school_id in (mine, ALL)   -> cross-school isolation: a Law rule can't leak into an AI student's answer
  * optional category          -> e.g. only 'fees' documents for a fee question

Reciprocal Rank Fusion: score(d) = Σ 1 / (k + rank_i(d)), k=60. Rewards passages ranked well by
both methods, without needing to calibrate their very different raw scores.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue
from sqlalchemy import text

from app.config import get_settings
from app.db.session import SessionLocal
from app.llm.llm_client import embed

RRF_K = 60


@dataclass
class Hit:
    chunk_id: int
    text: str
    title: str
    page: int | None
    section: str | None
    url: str
    school_id: str
    category: str
    academic_year: str
    version_label: str | None
    score: float
    via: str  # "vector", "keyword" or "both"

    def citation(self) -> dict:
        return {"chunk_id": self.chunk_id, "title": self.title, "page": self.page, "section": self.section,
                "url": self.url, "school_id": self.school_id, "academic_year": self.academic_year,
                "version": self.version_label}


@lru_cache
def _qdrant() -> QdrantClient:
    return QdrantClient(path=get_settings().qdrant_path)


def _schools(school_id: str | None) -> list[str] | None:
    return [school_id, "ALL"] if school_id else None


def vector_search(query: str, school_id: str | None, categories: list[str] | None, limit: int = 20) -> list[dict]:
    must = [FieldCondition(key="is_current", match=MatchValue(value=True))]
    if (sch := _schools(school_id)):
        must.append(FieldCondition(key="school_id", match=MatchAny(any=sch)))
    if categories:
        must.append(FieldCondition(key="category", match=MatchAny(any=categories)))
    vec = embed([query])[0]
    res = _qdrant().query_points(get_settings().qdrant_collection, query=vec, query_filter=Filter(must=must),
                                 limit=limit, with_payload=True).points
    return [{"chunk_id": p.payload["chunk_id"], "score": p.score} for p in res]


STOP = set("""a an the and or of to in on for with is am are was be can i my me we you your what which when how who
why do does did will shall should would could at by from as it this that there their about any all if not no yes per
please tell give get much many bennett university""".split())


def _or_query(query: str) -> str:
    """'Am I eligible for B.Tech CSE…' -> 'eligible or b.tech or cse …' (any keyword may match; ts_rank orders)."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9.+-]{1,}|\d{2,}", query.lower()) if w not in STOP]
    return " or ".join(dict.fromkeys(words)) or query


def keyword_search(query: str, school_id: str | None, categories: list[str] | None, limit: int = 20) -> list[dict]:
    sql = """
      SELECT c.id AS chunk_id, ts_rank_cd(c.tsv, q, 32) AS score
      FROM chunks c JOIN document_versions v ON v.id = c.version_id JOIN documents d ON d.id = v.document_id,
           websearch_to_tsquery('english', :q) q
      WHERE c.tsv @@ q AND v.is_current AND d.status = 'approved'
        AND (CAST(:school AS text) IS NULL OR d.school_id IS NULL OR d.school_id = CAST(:school AS text))
        AND (CAST(:cats AS text[]) IS NULL OR d.category = ANY(CAST(:cats AS text[])))
      ORDER BY score DESC LIMIT :lim"""
    with SessionLocal() as db:
        rows = db.execute(text(sql), {"q": _or_query(query), "school": school_id, "cats": categories,
                                      "lim": limit}).mappings().all()
    return [dict(r) for r in rows]


def _load(chunk_ids: list[int]) -> dict[int, dict]:
    if not chunk_ids:
        return {}
    sql = """SELECT c.id, c.text, c.page, c.section, d.title, d.category, coalesce(d.school_id,'ALL') AS school_id,
                    v.source_url AS url, coalesce(v.academic_year,'') AS academic_year, v.version_label
             FROM chunks c JOIN document_versions v ON v.id=c.version_id JOIN documents d ON d.id=v.document_id
             WHERE c.id = ANY(:ids)"""
    with SessionLocal() as db:
        return {r["id"]: dict(r) for r in db.execute(text(sql), {"ids": chunk_ids}).mappings()}


def search(query: str, school_id: str | None = None, categories: list[str] | None = None, k: int = 8) -> list[Hit]:
    try:
        vec = vector_search(query, school_id, categories)
    except Exception:  # vector store locked (re-indexing) or embedder unreachable -> keyword-only degraded mode
        _qdrant.cache_clear()
        vec = []
    kw = keyword_search(query, school_id, categories)
    fused: dict[int, float] = {}
    via: dict[int, set] = {}
    for name, results in (("vector", vec), ("keyword", kw)):
        for rank, r in enumerate(results, start=1):
            fused[r["chunk_id"]] = fused.get(r["chunk_id"], 0) + 1 / (RRF_K + rank)
            via.setdefault(r["chunk_id"], set()).add(name)
    top = sorted(fused, key=fused.get, reverse=True)[: k * 2]
    meta = _load(top)
    hits = []
    seen_text = set()
    for cid in top:
        m = meta.get(cid)
        if not m:
            continue
        sig = m["text"][:120]
        if sig in seen_text:  # drop near-duplicate passages (overlapping chunks / duplicate pages)
            continue
        seen_text.add(sig)
        hits.append(Hit(chunk_id=cid, text=m["text"], title=m["title"], page=m["page"], section=m["section"],
                        url=m["url"], school_id=m["school_id"], category=m["category"],
                        academic_year=m["academic_year"], version_label=m["version_label"], score=round(fused[cid], 5),
                        via="both" if len(via[cid]) == 2 else next(iter(via[cid]))))
        if len(hits) >= k:
            break
    return hits
