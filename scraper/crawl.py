"""Polite crawler for the public bennett.edu.in site.

Saves raw HTML + cleaned text for in-scope pages and downloads linked PDFs.
Respects robots.txt, 1 request/second, caches to disk (re-runs skip fetched URLs).

Usage:  python scraper/crawl.py [--max-pages 600] [--max-pdfs 250]
Output: data/raw/html/*.html, data/raw/text/*.txt, data/raw/pdf/**.pdf, data/raw/manifest.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import urllib.robotparser
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.bennett.edu.in"
ROOT = Path(__file__).resolve().parents[1] / "data" / "raw"
UA = "BennettOne-StudentProject/0.1 (academic research crawler)"
DELAY = 1.0

SEEDS = [
    "/programs/", "/schools/", "/admission/", "/admission/eligibility-and-selection-criteria/",
    "/admission/fee-structure/", "/admission/scholarships/", "/admission/admission-process/",
    "/admission/faqs/", "/admission/lateral-entry-and-migration-admissions/",
    "/admission/international-fee-structure/", "/international-admissions",
    "/notices-registrar-office/", "/examination-department/",
    "/ordinances-statutes-rules-and-regulations/", "/global-pathway/", "/three-country-program/",
    "/bennett-life/", "/bennett-life/hostels-at-bu/", "/bennett-life/student-services/",
    "/bennett-life/student-services/transportation-facility/", "/bennett-life/infrastructure/",
    "/about-us/overview/", "/about-us/leadership/", "/about-us/times-group/",
    "/placements/", "/placements/placements-across-programs/", "/contact-us/", "/",
]

# Only follow pages under these prefixes (keeps the crawl on-topic)
IN_SCOPE = (
    "/programs/", "/progrmas/", "/schools/", "/admission/", "/international-admissions",
    "/notices-registrar-office", "/examination-department", "/ordinances-statutes",
    "/global-pathway", "/three-country-program", "/bennett-life", "/about-us/",
    "/placements", "/placement-highlights", "/contact-us",
)
PDF_HOSTS = ("www.bennett.edu.in", "bennett.edu.in", "d2xwywryb7yxbo.cloudfront.net")  # BU's own CDN
SKIP_PDF = re.compile(r"(SEATING-PLAN|HR_Manual|Office-Order|Office_Order)", re.I)


def norm(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlparse(url)
    path = p.path or "/"
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return f"https://www.bennett.edu.in{path}"


def slug(url: str) -> str:
    path = urlparse(url).path.strip("/") or "home"
    return re.sub(r"[^A-Za-z0-9._-]+", "__", path)[:180]


def clean_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.string or "").strip() if soup.title else ""
    for t in soup(["script", "style", "noscript", "header", "footer", "nav", "form", "svg", "iframe"]):
        t.decompose()
    for sel in [".modal", "#mega-menu", ".menu", ".footer", ".header", ".breadcrumb"]:
        for t in soup.select(sel):
            t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    # Mark structure in-place, then flatten everything (captures carousel/mixed-content divs too)
    for h in main.find_all(["h1", "h2", "h3", "h4", "h5"]):
        h.insert_before("\n\n" + "#" * int(h.name[1]) + " ")
        h.insert_after("\n")
    for li in main.find_all("li"):
        li.insert_before("\n- ")
    for tr in main.find_all("tr"):
        for cell in tr.find_all(["td", "th"])[1:]:
            cell.insert_before(" | ")
        tr.insert_after("\n")
    for br in main.find_all(["br", "p", "div", "table", "section"]):
        br.insert_before("\n")
    raw = main.get_text("")
    out, prev = [], None
    for ln in raw.splitlines():
        ln = " ".join(ln.split())
        if ln and ln not in ("-", "#") and ln != prev:
            out.append(ln)
        prev = ln
    return title, "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=600)
    ap.add_argument("--max-pdfs", type=int, default=250)
    args = ap.parse_args()

    for d in ("html", "text", "pdf"):
        (ROOT / d).mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "manifest.jsonl"
    seen_manifest = set()
    if manifest_path.exists():
        for line in manifest_path.read_text(encoding="utf-8").splitlines():
            seen_manifest.add(json.loads(line)["url"])

    rp = urllib.robotparser.RobotFileParser(BASE + "/robots.txt")
    rp.read()
    sess = requests.Session()
    sess.headers["User-Agent"] = UA

    queue = deque(norm(BASE + s) for s in SEEDS)
    visited: set[str] = set()
    pdfs: dict[str, str] = {}  # pdf url -> page found on
    pages = 0

    with manifest_path.open("a", encoding="utf-8") as mf:
        while queue and pages < args.max_pages:
            url = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            if not rp.can_fetch("*", url):
                continue
            html_file = ROOT / "html" / f"{slug(url)}.html"
            if html_file.exists():
                html = html_file.read_text(encoding="utf-8", errors="ignore")
            else:
                try:
                    r = sess.get(url, timeout=30)
                    time.sleep(DELAY)
                except requests.RequestException as e:
                    print("ERR", url, e)
                    continue
                if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
                    continue
                html = r.text
                html_file.write_text(html, encoding="utf-8")
            pages += 1
            title, text = clean_text(html)
            (ROOT / "text" / f"{slug(url)}.txt").write_text(f"URL: {url}\nTITLE: {title}\n\n{text}", encoding="utf-8")
            if url not in seen_manifest:
                mf.write(json.dumps({"url": url, "type": "html", "file": f"html/{slug(url)}.html",
                                     "title": title, "sha256": hashlib.sha256(html.encode()).hexdigest(),
                                     "fetched_at": datetime.now(timezone.utc).isoformat()}) + "\n")
                seen_manifest.add(url)
            print(f"[{pages}] {url}")

            soup = BeautifulSoup(html, "lxml")
            for a in soup.find_all("a", href=True):
                href = urljoin(url, a["href"].strip())
                p = urlparse(href)
                if p.path.lower().endswith(".pdf") and p.netloc in PDF_HOSTS:
                    pdfs.setdefault(href.split("#")[0], url)
                    continue
                if p.netloc not in ("www.bennett.edu.in", "bennett.edu.in"):
                    continue
                if any(p.path.startswith(s) for s in IN_SCOPE):
                    n = norm(href)
                    if n not in visited:
                        queue.append(n)

        print(f"\nPages: {pages}. PDFs discovered: {len(pdfs)}")
        n_pdf = 0
        for purl, found_on in sorted(pdfs.items()):
            if n_pdf >= args.max_pdfs:
                break
            if SKIP_PDF.search(purl) or (urlparse(purl).netloc.endswith("bennett.edu.in") and not rp.can_fetch("*", purl)):
                continue
            path = urlparse(purl).path
            rel = path.split("/wp-content/uploads/")[-1].strip("/") if "/wp-content/uploads/" in path else "cdn/" + path.strip("/")
            dest = ROOT / "pdf" / rel
            n_pdf += 1
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = sess.get(purl, timeout=90)
                time.sleep(DELAY)
            except requests.RequestException as e:
                print("ERR", purl, e)
                continue
            if r.status_code != 200 or len(r.content) > 60_000_000:
                continue
            dest.write_bytes(r.content)
            mf.write(json.dumps({"url": purl, "type": "pdf", "file": f"pdf/{rel}", "found_on": found_on,
                                 "bytes": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest(),
                                 "fetched_at": datetime.now(timezone.utc).isoformat()}) + "\n")
            print(f"PDF {n_pdf}: {rel} ({len(r.content)//1024} KB)")


if __name__ == "__main__":
    main()
