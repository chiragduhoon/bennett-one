"""Decide, for each crawled file, whether to index it and with what metadata.

Metadata is what makes retrieval *school-aware* and *version-aware*:
  school_id  -> None means university-wide (applies to everyone)
  category   -> attendance / exam / academic_rules / fees / scholarship / ...
  family     -> normalised name shared by all versions of the same policy
  academic_year / published_on -> used to pick the CURRENT version
"""
from __future__ import annotations

import re
from datetime import date

# Never index (noise for students: moot-court scores, journals, newsletters, committee orders...)
EXCLUDE = re.compile(
    r"newsletter|moot|bnmcc|bimcc|score|ranking|journal|bjls|call-for-paper|editorial|\btoc\b|toc-vol|cover|"
    r"copyright|lawbyrinth|annual-report|office[-_]order|achievement|publications|list-of-(books|journals|conference)|"
    r"team-code|knockout|memorial|preliminary|researchers|clarification|retraction|seating-plan|hr_manual|"
    r"faculty-|ph_d_-data|research-topics|telephone|statutory|nirf|naac-ssr|guest-interview|deans?-note|foreword|"
    r"forword|editors?-note|ugc-letter|establishment|^\d+-[a-z]|aayush|ashish|venus|rajat|sabahat|guidelines-for-paper|"
    r"proposition|brochure-bimcc|competition|mapping-of-17|sdg|feedback-analysis|event-sponsorship|labs-equipment",
    re.I,
)
INCLUDE = re.compile(
    r"rule|ordinance|regulation|policy|calendar|calender|attendance|exam|manual|hand-?book|refund|scholarship|fee|hostel|"
    r"ragging|discipline|conduct|ufm|grievance|change-of-stream|lateral|mentor|internship|placement|bfs|brochure|"
    r"admission|visa|education-loan|transport|form|withdrawal|no-dues|id-card|privacy|circular|notification|notice|"
    r"vac|learners|ehs|standing-orders|student-council|sports|professor-of-practice|phd|ph\.d|bci|status-of|"
    r"academic-documents|gender|posh|library|re-evaluation|scriber|instructions|date-sheet|scheme|syllabus",
    re.I,
)
MAX_BYTES = 15 * 1024 * 1024  # skip 20-50 MB scanned curriculum books
# Index even though EXCLUDE matches: the university-wide Annual Report ("Annual-Report-AY-2024-2025_...",
# rankings, placements, research, infrastructure). The Examination Department's short reports
# ("Annual-Report_AY-2024-25") stay excluded.
FORCE_INCLUDE = re.compile(r"^annual-report-ay-20\d{2}-20\d{2}", re.I)

SCHOOL_HINTS = [
    (re.compile(r"\bSOL\b|school-of-law|law|llb|bci|moot", re.I), "SOL"),
    (re.compile(r"SCSET|computer-science|\bBCA\b|\bMCA\b|cse", re.I), "SCSET"),
    (re.compile(r"\bSEAS\b|engineering-and-applied|biotech|physics|m\.?tech", re.I), "SEAS"),
    (re.compile(r"\bSoAI\b|school-of-artificial|artificial-intelligence", re.I), "SoAI"),
    (re.compile(r"\bBBA\b|\bMBA\b|management", re.I), "SOM"),
    (re.compile(r"BAJMC|media|mass-comm|film|journalism|\bTSOM\b", re.I), "TSOM"),
    (re.compile(r"liberal[-_ ]arts|\bSLA\b", re.I), "SLA"),
    (re.compile(r"design|b\.?des|m\.?des", re.I), "SOD"),
    (re.compile(r"global|three-country|essex|birmingham|reading", re.I), "SGP"),
]
# These are explicitly university-wide even if a school word appears in them
UNIVERSITY_WIDE = re.compile(
    r"attendance|exam|calendar|refund|scholarship|anti-ragging|discipline|conduct|ufm|grievance|hostel|privacy|"
    r"change-of-stream|lateral|mentor|ordinance|statute|no-dues|id-card|withdrawal|vac|learners|ehs|posh|gender|"
    r"placement-policy|BU-Internship-Policy-AY|sports|student-council|library|transport|academic-documents|bfs",
    re.I,
)

CATEGORIES = [
    ("attendance", r"attendance"),
    ("exam", r"exam|ufm|unfair|re-evaluation|scriber|date-sheet|grievance-form|instructions"),
    ("calendar", r"calendar|calender"),
    ("fees", r"fee|refund|education-loan|transport|payment"),
    ("scholarship", r"scholarship|bfs|finishing-school"),
    ("hostel", r"hostel|mess|cafeteria"),
    ("conduct", r"ragging|discipline|conduct|posh|gender|grievance"),
    ("academic_rules", r"rule|ordinance|regulation|hand-?book|change-of-stream|lateral|learners|vac|credit|"
                       r"professor-of-practice|scheme|syllabus|curriculum"),
    ("admission", r"admission|eligibility|brochure|visa|international|withdrawal|lateral-entry"),
    ("placement", r"placement|internship"),
    ("forms", r"form|authorization|letter|no-dues|id-card"),
    ("student_life", r"sports|club|student-council|mentor|library|ehs|life|infrastructure"),
]


def category_of(name: str) -> str:
    for cat, pat in CATEGORIES:
        if re.search(pat, name, re.I):
            return cat
    return "general"


def school_of(name: str) -> str | None:
    if UNIVERSITY_WIDE.search(name) and not re.search(r"\bSOL\b|SCSET|SEAS|BBA|MBA|BAJMC|Liberal", name):
        return None
    for pat, code in SCHOOL_HINTS:
        if pat.search(name):
            return code
    return None


def academic_year_of(text: str) -> str | None:
    """'2025-26', 'A.Y. 2024-25', '25-26', 'AY-24-25' -> '2025-26' style."""
    m = re.search(r"(20\d{2})\s*[-–_/]\s*(20)?(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(3)}"
    m = re.search(r"(?<!\d)(2\d)\s*[-_]\s*(2\d)(?!\d)", text)
    if m and int(m.group(2)) == int(m.group(1)) + 1:
        return f"20{m.group(1)}-{m.group(2)}"
    return None


def published_from_path(rel: str) -> date | None:
    m = re.match(r"(20\d{2})/(\d{2})/", rel)
    return date(int(m.group(1)), int(m.group(2)), 1) if m else None


FAMILIES = [  # explicit, ordered: first match wins
    (r"academic.calend[ae]r.*freshm", "academic calendar (freshmen)"),
    (r"academic.calend[ae]r", "academic calendar"),
    (r"hostel.*sports.*refund", "hostel & sports charges refund policy"),
    (r"(fee.)?refund.policy", "fee refund policy"),
    (r"sports.scholarship", "sports scholarship policy"),
    (r"scholarship.policy", "scholarship policy"),
    (r"exam(ination)?.manual", "examination manual"),
    (r"internship.policy.*except.sol|bu.internship.policy.ay", "internship policy (all schools except SOL)"),
    (r"internship.policy.*sol", "internship policy (School of Law)"),
    (r"placement.policy", "placement policy"),
    (r"lateral.entry", "lateral entry & credit transfer ordinance"),
    (r"ph\.?d.*(regulation|ordinance)|ordinances.rules.and.regulations.for.ph", "phd regulations"),
    (r"bci.(approval|consent)|^bci", "bar council of india approval"),
    (r"date.sheet", "examination date sheet"),
    (r"hostel.notice", "hostel notice"),
    (r"^annual.report.ay.20\d{2}.20\d{2}", "university annual report"),
]


def family_of(filename: str) -> str:
    """Normalise so different versions of one policy share a key (explicit families first)."""
    low = filename.lower()
    for pat, fam in FAMILIES:
        if re.search(pat, low):
            return fam
    n = low.rsplit(".", 1)[0]
    n = re.sub(r"(a\.?y\.?[-_ ]?)?(20\d{2}[-_–]?\d{0,4}|\d{2}[-_]\d{2})", " ", n)
    n = re.sub(r"\b(updated|final|latest|revised|compressed|v\d+(\.\d+)?|copy|new|f1|\d{1,2}\.\d{1,2}\.\d{2,4}|"
               r"\d{1,2}(july|june|may)\d{0,4})\b", " ", n)
    n = re.sub(r"[^a-z]+", " ", n)
    n = re.sub(r"\b(for|the|of|a|y|bu|students|all|returning|freshman)\b", " ", n)
    n = " ".join(n.split())
    n = n.replace("calender", "calendar")
    if "exam" in n and "manual" in n:
        return "examination manual"
    return n or filename.lower()


def display_title(filename: str) -> str:
    """Title shown in citations; most files keep their de-slugged name."""
    stem = filename.rsplit(".", 1)[0]
    if FORCE_INCLUDE.search(filename):
        return f"Bennett University Annual Report {academic_year_of(filename)}"
    return re.sub(r"[-_]+", " ", stem).strip()


def audience_of(category: str) -> str:
    return {"admission": "prospective", "fees": "all", "scholarship": "all"}.get(category, "enrolled" if category in
            ("attendance", "exam", "calendar", "academic_rules", "conduct", "hostel", "forms") else "all")


def should_index_pdf(rel_path: str, size: int) -> bool:
    name = rel_path.rsplit("/", 1)[-1]
    if size > MAX_BYTES:
        return False
    if FORCE_INCLUDE.search(name):
        return True
    if EXCLUDE.search(name):
        return False
    return bool(INCLUDE.search(name))


HTML_INCLUDE = re.compile(r"^(admission|programs|schools|bennett-life__(hostels|student-services|sports|infrastructure|"
                          r"life-at-campus)|international-admissions|examination-department|ordinances|placements$|"
                          r"global-pathway|three-country-program|contact-us|about-us__(overview|times-group|leadership))",
                          re.I)


def should_index_html(slug: str) -> bool:
    return bool(HTML_INCLUDE.search(slug)) and "page__" not in slug
