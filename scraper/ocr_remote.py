"""Standalone OCR worker for the lab machine (no project imports).

Usage on the lab box:
    ~/bennett_ocr/bin/python ocr_remote.py <pdf_dir> <out_dir> [workers]
Each <sha256>.pdf in pdf_dir -> <sha256>.json in out_dir: [[page_no, text], ...]
Same format and same word-splitting as backend/app/ingest/ocr.py, so results drop
straight into data/raw/ocr/. Processes files largest-first, in reverse order to the laptop.
"""
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

MIN_TEXT = 40
_GLUED = re.compile(r"[A-Za-z]{7,}")


def _split(line, wordninja):
    def fix(m):
        w = m.group(0)
        parts = wordninja.split(w)
        if len(parts) == 1 or any(len(p) == 1 and p.lower() not in ("a", "i") for p in parts):
            return w
        if w[0].isupper():
            parts[0] = parts[0][0].upper() + parts[0][1:]
        return " ".join(parts)
    return _GLUED.sub(fix, line)


def work(args):
    pdf, out_dir = args
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    import numpy as np
    import pymupdf
    import wordninja
    from rapidocr_onnxruntime import RapidOCR
    target = Path(out_dir) / (Path(pdf).stem + ".json")
    if target.exists():
        return f"skip {target.name}"
    ocr = RapidOCR(intra_op_num_threads=int(os.environ.get("OCR_THREADS", "4")), inter_op_num_threads=1)
    out = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc, start=1):
            t = page.get_text("text").strip()
            if len(t) < MIN_TEXT:
                pix = page.get_pixmap(dpi=200)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
                res, _ = ocr(img)
                if res:
                    res.sort(key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
                    t = "\n".join(_split(r[1], wordninja) for r in res)
                else:
                    t = ""
            if len(t.strip()) >= MIN_TEXT:
                out.append((i, t))
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)
    return f"done {target.name} ({len(out)} pages)"


if __name__ == "__main__":
    pdf_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    out_dir.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.name, reverse=True)
    with ProcessPoolExecutor(workers) as ex:
        for msg in ex.map(work, [(str(p), str(out_dir)) for p in pdfs]):
            print(msg, flush=True)
