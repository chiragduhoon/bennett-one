"""Instant replies for greetings / "what can you do" / thanks — no LLM, no GPU, < 10 ms.

Why: these messages carry no question about Bennett, so running the full agent (LLM intent step +
search + LLM answer) only adds latency. The replies are personalised from the user's profile.
Only *short* messages that are clearly small talk are caught; anything longer goes to the agent.
"""
from __future__ import annotations

import re

GREET = re.compile(r"^\s*(hi+|hello+|hey+|hii+|namaste|hola|good (morning|afternoon|evening)|yo|sup)\b[\s!.,?]*$", re.I)
THANKS = re.compile(r"^\s*(thanks?|thank you|thx|ty|ok(ay)?|cool|great|nice|got it|shukriya|dhanyavaad)\b[\s!.,?]*$", re.I)
WHO = re.compile(r"^\s*(who are you|what are you|what is (this|bennett one)|what can you do|how can you help|"
                 r"what do you do|help|what all can you (do|answer)|kya kar sakte ho)\s*\??\s*$", re.I)
BYE = re.compile(r"^\s*(bye|goodbye|see you|tata|good night)\b[\s!.]*$", re.I)


def detect(text: str) -> str | None:
    t = text.strip()
    if len(t) > 60:
        return None
    for name, rx in (("greet", GREET), ("thanks", THANKS), ("who", WHO), ("bye", BYE)):
        if rx.match(t):
            return name
    return None


def _suggestions(prof: dict) -> list[str]:
    if prof.get("role") == "student":
        return ["Am I eligible to sit the end-sem in all my courses?", "When do end-semester exams start?",
                "Write a leave application for 2 days", "How do I keep my scholarship next year?"]
    return ["Am I eligible for B.Tech CSE? (share your Class 12 marks)", "What are the B.Tech AI fees for 2026-27?",
            "How do merit scholarships work?", "What is the refund policy if I withdraw?"]


def respond(kind: str, prof: dict) -> dict:
    name = (prof.get("name") or "").split(" ")[0]
    hi = f"Hi {name}! " if name else "Hi! "
    if kind == "thanks":
        ans = "You're welcome! Ask me anything else about Bennett — I'll answer from official documents."
    elif kind == "bye":
        ans = "Bye! All the best — come back any time you need something about Bennett."
    else:
        ctx = (f"I'm answering for **{prof.get('school')} · {prof.get('programme')} · Semester {prof.get('semester')}**, "
               "so rules and dates are matched to you.\n\n") if prof.get("role") == "student" else ""
        ans = (f"{hi}I'm **BENNETT ONE**, Bennett University's information assistant.\n\n{ctx}"
               "**I can help with:**\n"
               "- **Admissions** — eligibility check (Best-of-3), programmes, entrance & selection process\n"
               "- **Fees & scholarships** — 2026-27 fee tables, hostel fees, scholarship slabs & renewal, refunds\n"
               "- **Academics** — attendance rules, exam & UFM rules, re-evaluation, academic calendar dates\n"
               "- **Campus** — hostel rules, policies, forms, and who to contact\n"
               "- **Applications** — drafting leave / condonation / other requests\n\n"
               "Every answer comes from **official Bennett documents** with the source shown.\n\n"
               "**Try asking:**\n" + "\n".join(f"- {s}" for s in _suggestions(prof)))
    return {"answer": ans, "citations": [], "status": None, "rule_result": None, "facts": None, "warnings": [],
            "intent": "greeting", "understanding": {"intent": "greeting"}}
