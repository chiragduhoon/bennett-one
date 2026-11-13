"""Download every PDF linked from one Bennett page (no skip filters).

Usage: python scraper/fetch_page_pdfs.py https://www.bennett.edu.in/notices-registrar-office/
Re-fetches the page (fresh), saves PDFs under data/raw/pdf/, appends to data/raw/manifest.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = "BennettOne-StudentProject/0.1 (academic research crawler)"
HOSTS = ("www.bennett.edu.in", "bennett.edu.in", "d2xwywryb7yxbo.cloudfront.net")


def rel_path(url: str) -> str:
    path = urlparse(url).path
    return path.split("/wp-content/uploads/")[-1].strip("/") if "/wp-content/uploads/" in path else "cdn/" + path.strip("/")


def main(page: str) -> None:
    s = requests.Session()
    s.headers["User-Agent"] = UA
    html = s.get(page, timeout=60).text
    soup = BeautifulSoup(html, "lxml")
    links: dict[str, str] = {}
    for a in soup.find_all("a", href=True):
        u = urljoin(page, a["href"].strip()).split("#")[0]
        if urlparse(u).path.lower().endswith(".pdf") and urlparse(u).netloc in HOSTS:
            links.setdefault(u, " ".join(a.get_text(" ", strip=True).split()))
    for u in re.findall(r"https?://[^\"' ]+?\.pdf", html, re.I):
        if urlparse(u).netloc in HOSTS:
            links.setdefault(u, "")
    print(f"{len(links)} PDFs linked on {page}")
    ok = skipped = failed = 0
    with (ROOT / "manifest.jsonl").open("a", encoding="utf-8") as mf:
        for i, (u, label) in enumerate(sorted(links.items()), 1):
            dest = ROOT / "pdf" / rel_path(u)
            if dest.exists() and dest.stat().st_size > 0:
                skipped += 1
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = s.get(u, timeout=120)
                time.sleep(1.0)
            except requests.RequestException as e:
                print(f"[{i}] FAIL {u} {e}")
                failed += 1
                continue
            if r.status_code != 200 or not r.content.startswith(b"%PDF"):
                print(f"[{i}] FAIL {r.status_code} {u}")
                failed += 1
                continue
            dest.write_bytes(r.content)
            mf.write(json.dumps({"url": u, "type": "pdf", "file": f"pdf/{rel_path(u)}", "found_on": page,
                                 "link_text": label, "bytes": len(r.content),
                                 "sha256": hashlib.sha256(r.content).hexdigest(),
                                 "fetched_at": datetime.now(timezone.utc).isoformat()}) + "\n")
            ok += 1
            print(f"[{i}] OK {rel_path(u)} ({len(r.content)//1024} KB)")
    print(f"\nDone: downloaded {ok}, already had {skipped}, failed {failed}, total linked {len(links)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "https://www.bennett.edu.in/notices-registrar-office/")
