"""Safety fast-path: ragging, harassment, threats, self-harm, emergencies.

Why a separate path: when someone says "I am being ragged" they need exact, verified help contacts
immediately — not a search that might miss, and not LLM wording that might soften or hallucinate.
This runs BEFORE the normal agent, needs no GPU, and always returns the same verified contacts.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings

RAGGING = re.compile(r"\bragg|\bbully|\bbullied|harass|threat|beat(en|ing) me|assault|molest|abus(e|ed|ing)|"
                     r"stalk|unsafe|forced me|seniors? (are )?(troubl|torture)|eve.?teas|sexual", re.I)
SELF_HARM = re.compile(r"suicid|kill (my)?self|end (my|it all|my life)|self.?harm|want to die|cut myself|"
                       r"no reason to live|hopeless|marna chahta|mar jaun", re.I)
EMERGENCY = re.compile(r"\bemergency\b|\bhelp me\b.*\bnow\b|\bfire\b|\baccident\b|\bbleeding\b|\bunconscious\b", re.I)


@lru_cache
def contacts() -> dict:
    return yaml.safe_load((Path(get_settings().seed_dir) / "safety_contacts.yaml").read_text(encoding="utf-8"))


def detect(text: str) -> str | None:
    if SELF_HARM.search(text):
        return "self_harm"
    if RAGGING.search(text):
        return "ragging"
    if EMERGENCY.search(text):
        return "emergency"
    return None


def _line(c: dict) -> str:
    parts = [f"**{c.get('role') or c.get('name')}**" + (f" — {c['name']}" if c.get("role") else "")]
    if c.get("phone"):
        parts.append(f"📞 {c['phone']}")
    if c.get("email"):
        parts.append(f"✉️ {c['email']}")
    return " · ".join(parts)


def respond(kind: str, school_id: str | None) -> dict:
    c = contacts()
    nat = {n["name"]: n for n in c["national"]}
    tele, emerg = nat.get("Tele-MANAS mental-health helpline (Govt. of India, 24×7, free)"), nat.get("Emergency (Police / Ambulance)")
    anti = next(n for n in c["national"] if "Anti-Ragging" in n["name"])
    lines = []
    if kind == "self_harm":
        lines += ["**You don't have to go through this alone. Please reach out right now:**", "",
                  f"- 📞 **Tele-MANAS (free, 24×7, confidential): {tele['phone']}**",
                  f"- 🚨 If you are in immediate danger: **{emerg['phone']}**",
                  "- Talk to someone you trust nearby — a friend, your warden, or a faculty member — and let them stay with you.", ""]
        lines += ["**At Bennett, you can also contact:**"]
        lines += [f"- {_line(x)}" for x in c["university"][:2]]
    else:
        title = "If you are being ragged, harassed or threatened" if kind == "ragging" else "In an emergency"
        lines += [f"**{title}, you are not at fault and you can get help immediately.**", "",
                  "**1. If you are in danger right now:** call **112** or go to the nearest security post / warden.", "",
                  "**2. Bennett Anti-Ragging Monitoring Cell** (official, notified 17 Apr 2026):"]
        dean = (c.get("school_deans") or {}).get(school_id or "")
        if dean:
            lines.append(f"- {_line({**dean, 'role': dean['role'] + ' (your school)'})}")
        lines += [f"- {_line(x)}" for x in c["university"]]
        lines += ["", f"**3. National Anti-Ragging Helpline (UGC, 24×7, toll-free):** 📞 **{anti['phone']}** · ✉️ {anti['email']} · {anti['web']}",
                  "", "**What helps your complaint:** note dates, times, places and names; keep screenshots/messages; "
                  "a friend can report on your behalf. Ragging is a punishable offence under the UGC Regulations and "
                  "Bennett's Anti-Ragging rules, and complaints are handled confidentially."]
        if kind == "ragging":
            lines += ["", f"If it affects how you feel, Tele-MANAS ({tele['phone']}, free, 24×7) is there to talk."]
    return {"answer": "\n".join(lines), "status": "URGENT_SUPPORT", "intent": "safety", "rule_result": None, "facts": None,
            "warnings": [], "understanding": {"intent": "safety"},
            "citations": [{"tag": "RULE", "title": c["source"]["title"], "url": c["source"]["url"], "page": 1},
                          {"tag": "RULE", "title": "National Anti-Ragging Helpline (UGC)", "url": anti["web"], "page": None}]}
