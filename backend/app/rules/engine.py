"""Deterministic rule engine — the "judge". The LLM only explains what this returns.

Why: LLMs are unreliable at arithmetic and at applying thresholds consistently. A Python function
gives the same answer every time, can be unit-tested, and records exactly which checks ran
(blueprint Feature 4: explainability — what was checked, which rule, which source, what's missing).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings

# Status vocabulary (shown as badges in the UI)
MEETS = "MEETS_CHECKED_CRITERIA"
NOT_MET = "DOES_NOT_MEET_CRITERIA"
INSUFFICIENT = "INSUFFICIENT_INFORMATION"
NEEDS_VERIFICATION = "NEEDS_VERIFICATION"  # e.g. interview/portfolio rounds we cannot evaluate

SUBJECT_ALIASES = {
    "maths": "Mathematics", "math": "Mathematics", "mathematics": "Mathematics",
    "physics": "Physics", "chemistry": "Chemistry", "biology": "Biology", "bio": "Biology",
    "english": "English", "computer science": "Computer Science", "cs": "Computer Science",
    "informatics practices": "Informatics Practices", "ip": "Informatics Practices",
    "biotechnology": "Biotechnology", "botany": "Botany", "zoology": "Zoology",
    "economics": "Economics", "accountancy": "Accountancy", "business studies": "Business Studies",
    "music": "Music", "dance": "Dance", "painting": "Painting", "home science": "Home Science",
}


def canon(subject: str) -> str:
    """Official subject name. Fixes common typos ("pjysics", "mathamatics", "chemestry") by close matching."""
    key = subject.strip().lower()
    if key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[key]
    if len(key) >= 5:
        from difflib import get_close_matches
        hit = get_close_matches(key, [k for k in SUBJECT_ALIASES if len(k) >= 5], n=1, cutoff=0.8)
        if hit:
            return SUBJECT_ALIASES[hit[0]]
    return "IT" if key in ("it", "i t", "information technology") else subject.strip().title()


# Students say "82% in PCM" — a stream average, not a subject.
GROUPS = {
    "pcm": ["Physics", "Chemistry", "Mathematics"], "pcb": ["Physics", "Chemistry", "Biology"],
    "pcmb": ["Physics", "Chemistry", "Mathematics", "Biology"], "pcme": ["Physics", "Chemistry", "Mathematics", "English"],
    "pmc": ["Physics", "Mathematics", "Chemistry"], "science": ["Physics", "Chemistry", "Mathematics"],
}
EXAM_KEYS = {"jee", "jeemain", "jeemains", "jeeadvanced", "cuet", "sat", "ib", "neet", "clat", "ailet", "cat", "xat",
             "mat", "cmat", "nmat", "gmat", "uceed", "nid", "nift", "budat", "percentile"}
AGGREGATE_KEYS = {"aggregate", "overall", "total", "class 12", "class xii", "12th", "xii", "percentage", "percent", "average", "boards"}


def normalise_marks(marks: dict) -> tuple[dict[str, float], dict[str, float], float | None]:
    """Split what the student typed into
       subjects  : real subject-wise marks            {"Physics": 78, ...}
       groups    : stream averages like "82% in PCM"  {"PCM": 82}
       aggregate : a single overall percentage        88
    We never invent subject marks from a group average — the rule needs the real ones."""
    subjects: dict[str, float] = {}
    groups: dict[str, float] = {}
    aggregate = None
    for k, v in (marks or {}).items():
        try:
            val = float(v)
        except (TypeError, ValueError):
            continue
        key = re.sub(r"[^a-z0-9 ]", "", str(k).lower()).strip()
        if key.replace(" ", "") in GROUPS:
            groups[key.replace(" ", "").upper()] = val
        elif key.replace(" ", "") in EXAM_KEYS:
            continue  # entrance-exam scores (JEE, CUET…) are not Class XII subjects; they matter for scholarships
        elif key in AGGREGATE_KEYS:
            aggregate = val
        else:
            subjects[canon(k)] = val
    return subjects, groups, aggregate


def _ask_for_subject_marks(r: "RuleResult", criteria: dict, groups: dict, aggregate: float | None, min_pct) -> "RuleResult":
    """Only an average was given: ask for exactly the marks the Best-of-3 rule needs, plus an honest provisional hint."""
    comp = criteria.get("compulsory_subjects") or []
    need = [f"{s} %" for s in comp] + ["your highest-scoring other subject and its % (not vocational)"]
    r.status = INSUFFICIENT
    r.missing = need
    given = ", ".join(f"{g} {v:g}%" for g, v in groups.items()) or f"overall {aggregate:g}%"
    r.checks.append(Check("Marks provided", None, f"{given} — an average, not subject-wise marks"))
    r.checks.append(Check("Rule needs", None, "Best of 3 = " + " + ".join(comp + ["highest other eligible subject"]) + f", minimum {min_pct}%"))
    pcm = groups.get("PCM") or groups.get("PMC")
    if pcm is not None and {"Physics", "Mathematics"} >= set(comp) and min_pct is not None:
        # Chemistry is an eligible third subject, so Best-of-3 >= (P+M+C)/3 = PCM average.
        hint = (f"Provisional: Best of 3 can't be lower than your PCM average, so it is at least {pcm:g}% "
                f"({'above' if pcm >= min_pct else 'below'} the {min_pct}% minimum). Share the exact marks to confirm.")
        r.checks.append(Check("Provisional estimate", pcm >= min_pct if pcm < min_pct else None, hint))
        r.computed["provisional_min_best_of_3"] = pcm
    elif aggregate is not None and min_pct is not None:
        r.checks.append(Check("Provisional estimate", None,
                              f"Overall {aggregate:g}% is {'above' if aggregate >= min_pct else 'below'} the {min_pct}% minimum, "
                              "but Best of 3 depends on specific subjects — share them to confirm."))
    return r


@dataclass
class Check:
    name: str
    passed: bool | None  # None = could not evaluate
    detail: str


@dataclass
class RuleResult:
    status: str
    checks: list[Check] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    computed: dict = field(default_factory=dict)
    sources: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- admissions eligibility
def best_of_three(marks: dict[str, float], compulsory: list[str], excluded: list[str],
                  any_of: list[str] | None = None) -> tuple[float | None, list[str], str | None]:
    """Class XII 'Best of 3': compulsory subjects + highest remaining eligible subject(s)."""
    marks = {canon(k): float(v) for k, v in marks.items()}
    chosen = []
    for c in compulsory:
        if c not in marks:
            return None, [], f"Compulsory subject missing: {c}"
        chosen.append(c)
    if any_of:
        opts = [s for s in any_of if s in marks]
        if not opts:
            return None, [], f"Needs one of: {', '.join(any_of)}"
        chosen.append(max(opts, key=lambda s: marks[s]))
    rest = sorted((s for s in marks if s not in chosen and s not in excluded), key=lambda s: -marks[s])
    while len(chosen) < 3 and rest:
        chosen.append(rest.pop(0))
    if len(chosen) < 3:
        return None, chosen, "Fewer than 3 eligible subjects provided"
    return round(sum(marks[s] for s in chosen) / 3, 2), chosen, None


def check_admission(student: dict, criteria: dict, source: dict | None = None) -> RuleResult:
    """student: {"board": "CBSE"|"IB"|..., "marks": {"Physics": 90, ...}, "ib_credits": int,
                 "graduation_pct": float}
    criteria: AdmissionCriteria.rules (extracted from the official eligibility page)."""
    r = RuleResult(status=MEETS, sources=[source] if source else [])
    basis = criteria.get("score_basis")
    min_pct = criteria.get("min_percentage")

    if criteria.get("needs_review") and not min_pct:
        r.status = NEEDS_VERIFICATION
        r.checks.append(Check("Machine-checkable criteria", None,
                              "This programme's criteria depend on rounds we cannot evaluate automatically "
                              f"({', '.join(criteria.get('selection_components', [])) or 'see official text'})."))
        return r

    if (student.get("board") or "").upper() == "IB" and criteria.get("ib_min_credits"):
        credits = student.get("ib_credits")
        if credits is None:
            r.missing.append("IB total credits")
            r.status = INSUFFICIENT
            return r
        ok = credits >= criteria["ib_min_credits"]
        r.checks.append(Check("IB credits", ok, f"{credits} vs minimum {criteria['ib_min_credits']}"))
        r.status = MEETS if ok else NOT_MET
    elif basis == "graduation_aggregate":
        g = student.get("graduation_pct")
        if g is None:
            r.missing.append("Graduation aggregate percentage")
            r.status = INSUFFICIENT
            return r
        ok = g >= (min_pct or 0)
        r.checks.append(Check("Graduation aggregate", ok, f"{g}% vs minimum {min_pct}%"))
        r.status = MEETS if ok else NOT_MET
    else:
        marks, groups, aggregate = normalise_marks(student.get("marks") or {})
        invalid = {k: v for k, v in {**marks, **groups, **({"overall": aggregate} if aggregate is not None else {})}.items()
                   if not 0 <= v <= 100}
        if invalid:  # impossible input must never produce a verdict
            r.status = INSUFFICIENT
            for k, v in invalid.items():
                r.checks.append(Check(f"Invalid mark: {k}", False, f"{v:g}% is not a valid percentage (must be between 0 and 100)"))
            r.missing = [f"a valid {k} percentage (0–100)" for k in invalid]
            return r
        compulsory = criteria.get("compulsory_subjects", [])
        excluded = criteria.get("excluded_third_subjects", [])
        any_of = criteria.get("any_of_subjects")
        given = set(marks)
        if not marks and (groups or aggregate is not None):
            # "82% in PCM" / "88% overall": don't guess — ask for the marks the rule actually uses.
            return _ask_for_subject_marks(r, criteria, groups, aggregate, min_pct)
        if not marks:
            r.missing = [f"{c} %" for c in compulsory] + ["your highest-scoring other subject and its % (not vocational)"]
            r.checks.append(Check("Rule needs", None, "Best of 3 = " + " + ".join(compulsory + ["highest other eligible subject"])
                                  + f", minimum {min_pct}%"))
            r.status = INSUFFICIENT
            return r
        absent = [c for c in compulsory if c not in given]
        eligible_others = [s for s in given if s not in compulsory and s not in excluded]
        missing_any_of = bool(any_of) and not any(s in given for s in any_of)
        if absent or missing_any_of or (len(given) < 3 and (not eligible_others or len(compulsory) + len(eligible_others) < 3)):
            # a required subject wasn't mentioned — ask for it instead of declaring "not eligible"
            r.status = INSUFFICIENT
            r.missing = ([f"{s} %" for s in absent] + ([f"one of {' / '.join(any_of)} %"] if missing_any_of else [])
                         + ([] if eligible_others else ["your highest-scoring other subject and its % (not vocational)"]))
            r.checks.append(Check("Marks provided", None, ", ".join(f"{k} {v:g}%" for k, v in marks.items())))
            if absent:
                r.checks.append(Check("Compulsory subject not given", None,
                                      f"{' and '.join(absent)} is compulsory — if you did not study it in Class XII, "
                                      "you do not meet this programme's eligibility rule"))
            r.checks.append(Check("Rule needs", None, "Best of 3 = " + " + ".join(compulsory + ["highest other eligible subject"])
                                  + f", minimum {min_pct}%"))
            return r
        for c in compulsory:
            r.checks.append(Check(f"Compulsory subject: {c}", c in given, "present" if c in given else "not in your marks"))
        if any_of:
            hit = [s for s in any_of if s in given]
            r.checks.append(Check(f"One of {'/'.join(any_of)}", bool(hit), ", ".join(hit) or "none provided"))
        score, chosen, err = best_of_three(marks, compulsory, excluded, any_of)
        if err:
            r.checks.append(Check("Best of 3 computation", False, err))
            r.status = NOT_MET if "missing" in err.lower() or "needs" in err.lower() else INSUFFICIENT
            return r
        r.computed = {"best_of_3": score, "subjects_used": chosen}
        if excluded:
            dropped = [s for s in (canon(k) for k in marks) if s in excluded]
            if dropped:
                r.checks.append(Check("Vocational subjects excluded", True, f"Not counted: {', '.join(dropped)}"))
        ok = min_pct is None or score >= min_pct
        r.checks.append(Check("Minimum percentage", ok, f"Best of 3 = {score}% ({', '.join(chosen)}) vs minimum {min_pct}%"))
        if not all(c.passed for c in r.checks if c.passed is not None):
            r.status = NOT_MET
    if criteria.get("selection_components"):
        r.checks.append(Check("Further selection steps", None,
                              "Also required: " + ", ".join(criteria["selection_components"]) + " (not evaluated here)"))
        if r.status == MEETS:
            r.status = NEEDS_VERIFICATION
    return r


# ---------------------------------------------------------------- attendance
@lru_cache
def policy_facts() -> dict:
    p = Path(get_settings().seed_dir) / "policy_facts.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def superseded_rules(facts: dict | None = None) -> list[dict]:
    """Older rules replaced by newer ones, e.g. SCSET's 70% attendance rule -> the 2022 university-wide 75%.

    Only versioned topics (a list of rule entries with ids) can have superseded entries; topics stored
    as a single dict (scholarship_policy, refund_policy, ...) are skipped.
    """
    facts = policy_facts() if facts is None else facts
    out = []
    for topic, items in facts.items():
        if not isinstance(items, list):
            continue
        by_id = {x.get("id"): x for x in items if isinstance(x, dict)}
        for f in by_id.values():
            if f.get("superseded_by"):
                out.append({"topic": topic, "older": f, "newer": by_id.get(f["superseded_by"]),
                            "status": "resolved_by_recency_and_authority"})
    return out


def attendance_rule(school_id: str | None) -> dict:
    """Pick the governing attendance fact: non-superseded, school-specific beats university-wide."""
    facts = [f for f in policy_facts().get("min_attendance_end_sem", []) if not f.get("superseded_by")]
    specific = [f for f in facts if f["scope"] == school_id]
    return (specific or [f for f in facts if f["scope"] == "university"])[0]


def check_attendance(course_pcts: dict[str, float], school_id: str | None = None) -> RuleResult:
    rule = attendance_rule(school_id)
    threshold = rule["value_pct"]
    superseded = [f for f in policy_facts().get("min_attendance_end_sem", []) if f.get("superseded_by") == rule["id"]]
    r = RuleResult(status=MEETS, sources=[rule["source"]], computed={"threshold_pct": threshold, "rule_id": rule["id"]})
    if not course_pcts:
        r.status, r.missing = INSUFFICIENT, ["Course-wise attendance percentages"]
        return r
    for course, pct in course_pcts.items():
        ok = float(pct) >= threshold
        r.checks.append(Check(course, ok, f"{pct}% vs minimum {threshold}%"
                                          + ("" if ok else f" — short by {round(threshold - float(pct), 2)}%")))
    if any(c.passed is False for c in r.checks):
        r.status = NOT_MET
    if superseded:
        r.computed["note"] = ("Older rule(s) superseded: " + "; ".join(
            f"{f['source']['title']} said {f['value_pct']}%" for f in superseded))
    return r


def classes_needed(attended: int, held: int, threshold_pct: float, remaining: int | None = None) -> dict:
    """How many consecutive classes must be attended to reach the threshold (simple projection)."""
    if held <= 0:
        return {"current_pct": None, "needed": None}
    cur = 100 * attended / held
    need = 0
    while 100 * (attended + need) / (held + need) < threshold_pct:
        need += 1
        if need > 10_000:
            break
    out = {"current_pct": round(cur, 2), "needed": need}
    if remaining is not None:
        out["achievable"] = need <= remaining
    return out


# ---------------------------------------------------------------- scholarships
def _min_cgpa(rule: dict, school_id: str | None) -> float:
    return float(rule["min_cgpa"].get(school_id or "", rule["min_cgpa"]["default"]))


def check_scholarship(cgpa: float | None, school_id: str | None, has_admission_scholarship: bool | None,
                      backlogs: bool | None = None, ufm: bool | None = None, disciplinary: bool | None = None,
                      top_10_percent: bool | None = None) -> RuleResult:
    """Continuation (if the student already holds an admission scholarship) or Academic Scholarship (if not)."""
    pol = policy_facts().get("scholarship_policy") or {}
    src = pol.get("source", {})
    which = "continuation" if has_admission_scholarship else "academic"
    rule = pol.get(which, {})
    r = RuleResult(status=MEETS, sources=[{**src, "page": rule.get("page"), "quote": rule.get("quote")}],
                   computed={"scheme": which, "min_cgpa": _min_cgpa(rule, school_id)})
    if ufm or disciplinary:
        # Both continuation and the Academic Scholarship exclude UFM / disciplinary cases (policy pp. 4-5),
        # so the outcome is known without asking which scheme applies.
        r.status = NOT_MET
        if ufm:
            r.checks.append(Check("No Unfair Means (UFM) case", False, "a UFM case disqualifies both continuation of an admission "
                                                                     "scholarship and the Academic Scholarship"))
        if disciplinary:
            r.checks.append(Check("No adverse disciplinary record", False, "a proven disciplinary case disqualifies the scholarship"))
        r.computed["note"] = ("Continuation scholarships that are discontinued are not reinstated later in the programme. "
                              "If you believe the UFM/disciplinary finding is wrong, raise it through the examination "
                              "grievance / Registrar process before the scholarship review.")
        return r
    if has_admission_scholarship is None:
        r.status, r.missing = INSUFFICIENT, ["whether you currently hold an on-admission scholarship"]
        return r
    if cgpa is None:
        r.missing.append("your current CGPA")
    else:
        if not 0 <= cgpa <= 10:
            r.status = INSUFFICIENT
            r.checks.append(Check("Invalid CGPA", False, f"{cgpa} is not on a 10-point scale"))
            return r
        need = _min_cgpa(rule, school_id)
        r.checks.append(Check("Minimum CGPA", cgpa >= need, f"{cgpa} vs {need} required for {school_id or 'your school'}"))
    for flag, label in ((backlogs, "No backlogs / supplementary exams"), (ufm, "No Unfair Means (UFM) case"),
                        (disciplinary, "No adverse disciplinary record")):
        if flag is None:
            r.checks.append(Check(label, None, "not stated — required by the policy"))
        else:
            r.checks.append(Check(label, not flag, "none" if not flag else "present — this disqualifies the scholarship"))
    if which == "academic":
        r.computed["amount_pct_of_tuition"] = rule.get("amount_pct_of_tuition")
        r.checks.append(Check("Top 10% of your programme", top_10_percent,
                              "required for the Academic Scholarship" if top_10_percent is None else ("yes" if top_10_percent else "no")))
    if any(c.passed is False for c in r.checks):
        r.status = NOT_MET
    elif r.missing or any(c.passed is None for c in r.checks):
        r.status = NEEDS_VERIFICATION if not r.missing else INSUFFICIENT
    if rule.get("no_reinstatement") and r.status == NOT_MET:
        r.computed["note"] = "Once a continuation scholarship is discontinued it is not reinstated later in the programme."
    return r


# ---------------------------------------------------------------- refunds
def check_refund(request_date: str | None = None, hostel_day: int | None = None) -> RuleResult:
    """request_date: ISO date the withdrawal request reaches the University.
    hostel_day: days after session start / hostel occupancy (0 = on or before)."""
    from datetime import date as _d
    pol = policy_facts().get("refund_policy") or {}
    t = pol.get("tuition", {})
    r = RuleResult(status=MEETS, sources=[{**pol.get("source", {}), "page": t.get("page"), "quote": t.get("quote")}])
    if request_date:
        try:
            d = _d.fromisoformat(request_date)
        except ValueError:
            r.missing.append("the date of your withdrawal request (YYYY-MM-DD)")
            d = None
        if d:
            full, fee = _d.fromisoformat(t["full_refund_until"]), _d.fromisoformat(t["processing_fee_until"])
            if d <= full:
                r.checks.append(Check("Tuition fee refund", True, f"Request on {d:%d %b %Y} is on/before {full:%d %b %Y}: full refund"))
                r.computed["tuition_refund"] = "full"
            elif d <= fee:
                r.checks.append(Check("Tuition fee refund", True, f"Request on {d:%d %b %Y} is between {full:%d %b} and {fee:%d %b %Y}: "
                                                                f"refund minus a processing fee of at most ₹{t['max_processing_fee_inr']:,}"))
                r.computed["tuition_refund"] = f"full minus processing fee ≤ ₹{t['max_processing_fee_inr']:,}"
            else:
                r.checks.append(Check("Tuition fee refund", None, f"Request on {d:%d %b %Y} is after {fee:%d %b %Y} — not covered by the "
                                                                "2026-27 schedule; the decision rests with the University (Vice Chancellor)"))
                r.status = NEEDS_VERIFICATION
    if hostel_day is not None:
        for s in pol.get("hostel", {}).get("slabs", []):
            if hostel_day <= s["until_day"]:
                r.checks.append(Check("Hostel charges refund", s["refund_pct"] > 0, f"Day {hostel_day}: {s['refund_pct']}% refund ({s['label']})"))
                r.computed["hostel_refund_pct"] = s["refund_pct"]
                break
    if not r.checks:
        r.status = INSUFFICIENT
        r.missing = r.missing or ["the date you will submit the withdrawal request"]
    r.computed["processing_time"] = (pol.get("how_to_apply") or {}).get("processing_time")
    return r


def parse_percentages(values: dict) -> dict[str, float]:
    """Students write '60%', '72.5 %', 'around 70', 'below 75'. Keep the number; 'below X' -> just under X.
    Non-numeric values are dropped rather than crashing the request."""
    out: dict[str, float] = {}
    for k, v in (values or {}).items():
        if isinstance(v, (int, float)):
            out[k] = float(v)
            continue
        m = re.search(r"(\d+(?:\.\d+)?)", str(v))
        if not m:
            continue
        n = float(m.group(1))
        if re.search(r"below|less than|under|<", str(v), re.I):
            n = round(n - 0.01, 2)
        out[k] = n
    return out


# ---------------------------------------------------------------- scholarship amount on official tuition
def scholarship_amounts(programme: str, tuition_by_year: dict | None, pct: float, source_url: str = "",
                        academic_year: str | None = None) -> RuleResult:
    """Scholarships apply to the TUITION fee only (Scholarship Policy 2026-27). Computes per-year and total
    tuition after scholarship from the official fee table. Hostel, exam, registration etc. are not reduced."""
    r = RuleResult(status=MEETS, sources=[{"title": f"Fee Structure AY {academic_year or '2026-27'}", "url": source_url}])
    if not tuition_by_year or not 0 < pct <= 100:
        r.status = INSUFFICIENT
        r.missing = ["official year-wise tuition for this programme" if not tuition_by_year else "a scholarship % between 0 and 100"]
        return r
    rows, total_before, total_after = [], 0, 0
    for year, fee in tuition_by_year.items():
        if not isinstance(fee, (int, float)):
            continue
        waived = round(fee * pct / 100)
        rows.append({"year": year.replace("_", " ").title(), "tuition": fee, "scholarship": waived, "payable": fee - waived})
        total_before += fee
        total_after += fee - waived
    r.computed = {"programme": programme, "scholarship_pct": pct, "per_year": rows, "total_tuition": total_before,
                  "total_scholarship": total_before - total_after, "total_tuition_payable": total_after,
                  "note": "Scholarship applies to tuition only; hostel, examination, registration and other charges are extra. "
                          "Continuation from year 2 needs the minimum CGPA (SoAI 8.5, others 8.0), no backlogs and no UFM."}
    r.checks.append(Check("Tuition after scholarship", True,
                          f"₹{total_before:,} − {pct:g}% = ₹{total_after:,} payable over {len(rows)} years"))
    return r


# ---------------------------------------------------------------- admission (merit) scholarship bands
@lru_cache
def merit_table() -> dict:
    p = Path(get_settings().seed_dir) / "merit_scholarships.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {"groups": []}


def merit_group(programme: str | None) -> dict | None:
    if not programme:
        return None
    n = programme.lower()
    best, best_len = None, 0
    for g in merit_table()["groups"]:
        for m in g["match"]:
            if m in n and len(m) > best_len:  # most specific match wins ("bca (artificial intelligence)" over "bca")
                best, best_len = g, len(m)
    return best


def merit_band(group: dict, exam: str, score: float) -> int:
    for lo, hi, pct in group["bands"].get(exam, []):
        if lo <= score <= hi:
            return pct
    return 0


def check_merit_scholarship(programme: str | None, exam: str | None, score: float | None) -> RuleResult:
    """On-admission merit scholarship % from Annexure A. If the programme is unknown, show what the score earns
    across programmes that accept that exam, and ask which programme."""
    t = merit_table()
    names = t.get("exam_names", {})
    r = RuleResult(status=MEETS, sources=[{**t.get("source", {})}])
    if not exam or score is None:
        r.status = INSUFFICIENT
        r.missing = ["your exam (JEE percentile, Class 12 Best-of-3 %, CUET, SAT, IB …) and score"]
        return r
    if not 0 <= score <= 200000:
        r.status = INSUFFICIENT
        r.checks.append(Check("Invalid score", False, f"{score} doesn't look like a valid {names.get(exam, exam)}"))
        return r
    group = merit_group(programme)
    if group is None:
        options = [{"programme": g["name"], "scholarship_pct": merit_band(g, exam, score), "page": g["page"]}
                   for g in t["groups"] if exam in g["bands"]]
        r.computed = {"exam": names.get(exam, exam), "score": score, "by_programme": options}
        r.status = INSUFFICIENT
        r.missing = ["which programme you are applying for (the scholarship band depends on it)"]
        for o in options:
            r.checks.append(Check(o["programme"], None, f"{o['scholarship_pct']}% of tuition with {names.get(exam, exam)} {score:g}"))
        return r
    if exam not in group["bands"]:
        r.status = NOT_MET
        r.checks.append(Check(f"{names.get(exam, exam)} accepted for {group['name']}", False,
                              "this exam is not a scholarship basis for this programme; accepted: "
                              + ", ".join(names.get(e, e) for e in group["bands"])))
        return r
    pct = merit_band(group, exam, score)
    bands = "; ".join(f"{lo:g}–{hi:g} → {p}%" for lo, hi, p in group["bands"][exam])
    r.sources[0]["page"] = group["page"]
    r.computed = {"programme_group": group["name"], "exam": names.get(exam, exam), "score": score, "scholarship_pct": pct,
                  "bands": bands, "note": "Applies to tuition only; first-come first-served subject to availability; "
                                          "continuation from year 2 needs the minimum CGPA, no backlogs and no UFM."}
    r.checks.append(Check("Admission scholarship band", pct > 0,
                          f"{names.get(exam, exam)} {score:g} → {pct}% of tuition for {group['name']} (bands: {bands})"))
    if pct == 0:
        r.status = NOT_MET
    return r
