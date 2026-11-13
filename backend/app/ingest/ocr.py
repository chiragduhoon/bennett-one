"""OCR for scanned PDFs (pages that have no text layer).

Engine: RapidOCR (PaddleOCR models on ONNX Runtime) — pure pip install, runs on CPU, no admin rights.
Its English recogniser often drops spaces ("Theminimum attendance"), so we re-split glued words
with `wordninja` (a word-frequency based splitter).

Results are cached per file hash in data/raw/ocr/<sha256>.json so OCR runs only once.

Run standalone to pre-OCR every scanned PDF that the pipeline will index:
    uv run python -m app.ingest.ocr
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import warnings
from functools import lru_cache
from pathlib import Path

import numpy as np
import pymupdf
import wordninja

from app.config import get_settings

warnings.filterwarnings("ignore")
MIN_TEXT = 40
_GLUED = re.compile(r"[A-Za-z]{7,}")


@lru_cache
def _engine():
    from rapidocr_onnxruntime import RapidOCR
    import os
    return RapidOCR(intra_op_num_threads=int(os.environ.get("OCR_THREADS", "3")), inter_op_num_threads=1)


def _split_glued(line: str) -> str:
    def fix(m: re.Match) -> str:
        w = m.group(0)
        parts = wordninja.split(w)
        # keep acronyms/proper nouns that wordninja would shred into single letters
        if len(parts) == 1 or any(len(p) == 1 and p.lower() not in ("a", "i") for p in parts):
            return w
        if w[0].isupper():
            parts[0] = parts[0][0].upper() + parts[0][1:]
        return " ".join(parts)
    return _GLUED.sub(fix, line)


def cache_dir() -> Path:
    d = Path(get_settings().raw_dir) / "ocr"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ocr_page(page: pymupdf.Page, dpi: int = 200) -> str:
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
    res, _ = _engine()(img)
    if not res:
        return ""
    # sort lines top-to-bottom, then left-to-right
    res.sort(key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
    return "\n".join(_split_glued(r[1]) for r in res)


def pages_with_ocr(path: Path) -> list[tuple[int, str]]:
    """Text per page; pages without a text layer are OCR'd (cached)."""
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    cf = cache_dir() / f"{sha}.json"
    if cf.exists():
        return [tuple(x) for x in json.loads(cf.read_text(encoding="utf-8"))]
    out = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            t = page.get_text("text").strip()
            if len(t) < MIN_TEXT:
                t = ocr_page(page)
            if len(t.strip()) >= MIN_TEXT:
                out.append((i, t))
    cf.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def needs_ocr(path: Path) -> bool:
    with pymupdf.open(path) as doc:
        return sum(len(p.get_text("text").strip()) for p in doc) < MIN_TEXT * max(1, doc.page_count) // 2


if __name__ == "__main__":
    from app.ingest.pipeline import discover
    files = [f for f in discover(get_settings()) if f.kind == "pdf"]
    # Parallel: `python -m app.ingest.ocr 2 4` = worker 2 of 4 (each worker takes every 4th file).
    shard, of = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) == 3 else (0, 1)
    scanned = [f for f in files if needs_ocr(f.path)]
    todo = [f for i, f in enumerate(sorted(scanned, key=lambda f: f.path.name)) if i % of == shard
            and not (cache_dir() / f"{f.sha256 or hashlib.sha256(f.path.read_bytes()).hexdigest()}.json").exists()]
    print(f"worker {shard}/{of}: {len(todo)} PDFs left ({sum(pymupdf.open(f.path).page_count for f in todo)} pages)", flush=True)
    for k, f in enumerate(todo, 1):
        pages = pages_with_ocr(f.path)
        print(f"[{k}/{len(todo)}] {f.path.name}: {len(pages)} pages OCR'd", flush=True)
    sys.exit(0)
