"""Turn crawled Bennett pages into reviewed-able structured seed data.

Reads data/raw/html/*.html (from crawl.py) and writes data/seed/:
  schools.yaml       9 schools + their programmes (from the eligibility page tabs)
  eligibility.yaml   per-programme eligibility / selection text + extracted rule fields
  fees.yaml          per-programme fee tables (AY shown on site), hostel + other charges
  programmes.yaml    programme pages: name, url, duration, credits, specialisations, summary

Every record carries `source_url` so the app can cite it. Extracted numeric fields are
best-effort and flagged `needs_review: true` when the parser was not confident.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup, Comment

ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "data" / "raw" / "html"
SEED = ROOT / "data" / "seed"
SITE = "https://www.bennett.edu.in"


def soup_of(name: str) -> BeautifulSoup:
    return BeautifulSoup((HTML / name).read_text(encoding="utf-8", errors="ignore"), "lxml")


def txt(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


SCHOOL_CODES = {
    "School of Computer Science Engineering & Technology": "SCSET",
    "School of Engineering & Applied Sciences": "SEAS",
    "School of Artificial Intelligence": "SoAI",
    "Times School of Media": "TSOM",
    "School of Liberal Arts": "SLA",
    "School of Law": "SOL",
    "School of Design": "SOD",
    "School of Management": "SOM",
    "School of Global Pathways": "SGP",
}

SUBJECTS = ["Physics", "Mathematics", "Maths", "Chemistry", "Biology", "Biotechnology", "English",
            "Botany", "Zoology", "Computer Science", "Economics", "Accountancy"]


def extract_rules(elig: str, sel: str) -> dict:
    """Best-effort extraction of machine-checkable fields from eligibility prose."""
    r: dict = {}
    m = re.search(r"minimum\s+(\d{2})\s*%", elig, re.I)
    if m:
        r["min_percentage"] = int(m.group(1))
    m = re.search(r"IB Board with minimum score of (\d+) credits", elig, re.I)
    if m:
        r["ib_min_credits"] = int(m.group(1))
    if re.search(r"best of 3", elig + " " + sel, re.I):
        r["score_basis"] = "class12_best_of_3"
    elif re.search(r"graduation percentage|graduation in any discipline|bachelor", elig + sel, re.I):
        r["score_basis"] = "graduation_aggregate"
    comp = []
    m = re.search(r"with (.+?)(?:& any|and any|with minimum|minimum)", elig, re.I)
    if m:
        comp_txt = m.group(1)
        for s in SUBJECTS:
            if re.search(rf"\b{s}\b", comp_txt, re.I):
                comp.append("Mathematics" if s == "Maths" else s)
    m2 = re.search(r"comprising of (.+?) as compulsory", sel, re.I)
    if m2:
        for s in SUBJECTS:
            if re.search(rf"\b{s}\b", m2.group(1), re.I) and ("Mathematics" if s == "Maths" else s) not in comp:
                comp.append("Mathematics" if s == "Maths" else s)
    if re.search(r"English as compulsory", elig + sel, re.I) and "English" not in comp:
        comp.append("English")
    if comp:
        r["compulsory_subjects"] = comp
    if "/" in elig and re.search(r"Biology/Biotechnology", elig):
        r["any_of_subjects"] = ["Biology", "Biotechnology", "Botany", "Zoology"]
        r["compulsory_subjects"] = [c for c in comp if c not in r["any_of_subjects"]]
    if re.search(r"should not be vocational", sel + elig, re.I):
        r["excluded_third_subjects"] = ["Music", "Dance", "Painting", "Home Science", "Arts"]
    for exam in ["JEE", "CUET", "CLAT", "CAT", "MAT", "XAT", "GMAT", "CMAT", "NATA", "UCEED", "GATE", "NET"]:
        if re.search(rf"\b{exam}\b", elig + " " + sel):
            r.setdefault("entrance_exams_mentioned", []).append(exam)
    for kw in ["interview", "portfolio", "aptitude test", "personal interview", "written test", "group discussion"]:
        if re.search(kw, sel + elig, re.I):
            r.setdefault("selection_components", []).append(kw)
    r["needs_review"] = not ("min_percentage" in r and "score_basis" in r)
    return r


def parse_eligibility() -> tuple[list, list]:
    url = f"{SITE}/admission/eligibility-and-selection-criteria/"
    s = soup_of("admission__eligibility-and-selection-criteria.html")
    tab_names = {el["data-tab"]: txt(el) for el in s.select("[data-tab]")}
    schools, elig = [], []
    for pane in s.select(".bp_tab-content"):
        school = tab_names.get(pane.get("id"), pane.get("id"))
        progs = []
        for prog in pane.select(".prog"):
            name = txt(prog.find(["h3", "h2"]))
            if not name:
                continue
            sections: dict[str, list[str]] = {}
            cur = None
            for el in prog.find_all(["h4", "p", "li"]):
                if el.name == "h4":
                    cur = txt(el).rstrip(":")
                    continue
                t = txt(el)
                if t and cur:
                    sections.setdefault(cur, []).append(t)
            e_lines = sections.get("Eligibility Criteria", [])
            domestic = [l for l in e_lines if not l.lower().startswith(("nri", "international"))]
            nri = [l for l in e_lines if l.lower().startswith(("nri", "international"))]
            sel = " ".join(sections.get("Selection Criteria", []))
            rec = {
                "programme": name,
                "programme_id": slugify(name),
                "school": school,
                "school_code": SCHOOL_CODES.get(school, ""),
                "eligibility_text": " ".join(domestic),
                "nri_eligibility_text": " ".join(nri) or None,
                "selection_text": sel,
                "other_sections": {k: v for k, v in sections.items() if k not in ("Eligibility Criteria", "Selection Criteria")} or None,
                "rules": extract_rules(" ".join(domestic), sel),
                "source_url": url,
            }
            elig.append(rec)
            progs.append(name)
        schools.append({"name": school, "code": SCHOOL_CODES.get(school, ""), "programmes_with_criteria": progs})
    return schools, elig


def money(s: str):
    s = s.replace(",", "").replace("₹", "").strip()
    return int(s) if re.fullmatch(r"\d+", s) else (None if s in ("–", "-", "") else s)


def parse_fees() -> list:
    url = f"{SITE}/admission/fee-structure/"
    s = soup_of("admission__fee-structure.html")
    out = []
    for pane in s.select(".tab-pane"):
        if not pane.find("table") or pane.select(".tab-pane"):
            continue  # skip category containers, keep leaf panes
        tables = []
        for tbl in pane.find_all("table"):
            title_el = tbl.find_previous(["h4", "h3", "h5"])
            rows = [[txt(c) for c in tr.find_all(["td", "th"])] for tr in tbl.find_all("tr")]
            rows = [r for r in rows if any(r)]
            tables.append({"title": txt(title_el), "rows": rows})
        name = tables[0]["title"] if tables else pane.get("id")
        name = re.sub(r"\s*Fees?\s*@\s*Bennett University\s*$", "", name).strip()
        if re.fullmatch(r"test_?\d*", name, re.I):
            continue
        rec ={"pane_id": pane.get("id"), "programme": name, "programme_id": slugify(re.sub(r"\bFees?\b.*$", "", name)),
               "tables": tables, "source_url": url}
        # Pull structured tuition for simple "Year | Tuition fee" tables
        t0 = tables[0]["rows"] if tables else []
        tuition = {}
        for r in t0:
            if len(r) >= 2 and re.fullmatch(r"Year \d", r[0]):
                tuition[r[0].lower().replace(" ", "_")] = money(r[1])
            if r and r[0].startswith("Total") and len(r) >= 2:
                rec["total_tuition"] = money(r[-1])
        if tuition:
            rec["tuition_by_year"] = tuition
        lis = [txt(li) for li in pane.find_all("li")]
        if lis:
            rec["other_charges"] = lis
        notes = [txt(p) for p in pane.find_all("p") if txt(p).startswith(("*", "#"))]
        if notes:
            rec["notes"] = notes
        out.append(rec)
    # Academic year label shown in nav ("Fee AY 2026-27")
    ay = re.search(r"Fee AY (\d{4}-\d{2})", s.get_text(" "))
    for r in out:
        r["academic_year"] = ay.group(1) if ay else None
    return out


def parse_programmes() -> list:
    out = []
    for f in sorted(HTML.glob("programs__*.html")):
        s = BeautifulSoup(f.read_text(encoding="utf-8", errors="ignore"), "lxml")
        canon = s.find("link", rel="canonical")
        url = canon["href"] if canon and canon.get("href") else SITE + "/" + f.stem.replace("__", "/") + "/"
        main = s.find("main") or s.body
        # drop HTML comments (stale hidden content, e.g. old fee blocks) before reading
        for c in main.find_all(string=lambda t: isinstance(t, Comment)):
            c.extract()
        flat = [l.strip() for l in main.get_text("\n").splitlines() if l.strip()]
        rec = {"url": url, "title": txt(s.find("h1")) or (s.title.string.strip() if s.title else f.stem)}
        for key in ("Duration", "Specialisations", "Specializations", "Credits", "Start Date", "Intake", "Seats"):
            if key in flat:
                i = flat.index(key)
                if i + 1 < len(flat):
                    rec[key.lower().replace(" ", "_")] = flat[i + 1]
        about = s.find(string=re.compile(r"^\s*About\s*$"))
        if about:
            nxt = about.find_parent().find_next("p")
            if nxt:
                rec["summary"] = txt(nxt)[:1200]
        if "summary" not in rec:
            md = s.find("meta", attrs={"name": "description"})
            if md:
                rec["summary"] = md.get("content", "")
        pk = re.search(r"Highest Package\W+(Rs\.?\s*[\d.]+\s*\w+\.?/Yr\.?)", main.get_text(" "))
        if pk:
            rec["highest_package_claim"] = pk.group(1)
        out.append(rec)
    return out


def dump(name: str, data) -> None:
    SEED.mkdir(parents=True, exist_ok=True)
    with (SEED / name).open("w", encoding="utf-8") as fh:
        fh.write("# AUTO-GENERATED by scraper/parse_seed.py from bennett.edu.in. Review before use.\n")
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False, width=110)
    print(f"wrote {name}: {len(data)} records")


if __name__ == "__main__":
    schools, elig = parse_eligibility()
    dump("schools.yaml", schools)
    dump("eligibility.yaml", elig)
    dump("fees.yaml", parse_fees())
    progs = parse_programmes()
    if progs:
        dump("programmes.yaml", progs)
