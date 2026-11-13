"""Run the gold evaluation set against the live API and score each answer.

    uv run python -m app.eval.run                 # all questions
    uv run python -m app.eval.run --only att-01   # one question

Scores per question
  mention   : every `must_mention` group has at least one keyword in the answer
  no_myth   : none of the `must_not` phrases appear
  cited     : at least one official source was cited (except refusals)
  behavior  : ask_details -> status INSUFFICIENT/NEEDS_VERIFICATION or answer asks for marks;
              refuse/decline -> no fabricated specifics; answer -> not empty
Writes a report to data/eval/report.md
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import yaml

from app.config import REPO_ROOT

API = "http://localhost:8000/api"


def _post(path: str, body: dict, token: str | None = None) -> dict:
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, json.dumps(body).encode(), h)
    return json.load(urllib.request.urlopen(req, timeout=900))


def student_token() -> str:
    return _post("/auth/login", {"email": "student@bennett.demo", "password": "bennett123"})["token"]


def score(item: dict, res: dict) -> dict:
    ans = (res.get("answer") or "").lower()
    groups = item.get("must_mention") or []
    mention = all(any(k.lower() in ans for k in g) for g in groups)
    myths = [m for m in (item.get("must_not") or []) if m.lower() in ans]
    cited = bool(res.get("citations"))
    b = item["behavior"]
    if b == "ask_details":
        beh = res.get("status") in ("INSUFFICIENT_INFORMATION", "NEEDS_VERIFICATION") or "please share" in ans or "?" in ans
    elif b in ("refuse_or_redirect", "decline_rule_evasion"):
        beh = not any(w in ans for w in ("guarantee you", "you will definitely")) and len(ans) > 20
    else:
        beh = len(ans) > 40
    needs_cite = b not in ("refuse_or_redirect",)
    ok = mention and not myths and beh and (cited or not needs_cite)
    return {"pass": ok, "mention": mention, "myths_found": myths, "cited": cited, "behavior_ok": beh}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    args = ap.parse_args()
    items = yaml.safe_load((REPO_ROOT / "data" / "eval" / "gold.yaml").read_text(encoding="utf-8"))
    if args.only:
        items = [i for i in items if i["id"] == args.only]
    tok = student_token()
    rows = []
    for it in items:
        qs = it["q"] if isinstance(it["q"], list) else [it["q"]]
        sid, res, t0 = None, {}, time.time()
        try:
            for q in qs:
                res = _post("/chat", {"message": q, "session_id": sid}, tok if it["who"] == "student" else None)
                sid = res["session_id"]
        except Exception as e:  # noqa: BLE001
            res = {"answer": f"ERROR {e}", "citations": []}
        s = score(it, res)
        rows.append({"id": it["id"], "q": qs[-1], "secs": round(time.time() - t0), "status": res.get("status"),
                     "intent": res.get("intent"), "answer": res.get("answer", ""),
                     "citations": [c.get("title") for c in res.get("citations", [])], "removed": res.get("removed_claims", []), **s, "expected": it.get("source_hint")})
        print(f"{'PASS' if s['pass'] else 'FAIL'}  {it['id']:9} {rows[-1]['secs']:>3}s  mention={s['mention']} "
              f"myths={s['myths_found'] or '-'} cited={s['cited']} behavior={s['behavior_ok']}", flush=True)

    n = len(rows)
    passed = sum(r["pass"] for r in rows)
    out = [f"# BENNETT ONE evaluation report\n\n**{passed}/{n} passed ({100 * passed // max(n, 1)}%)**\n",
           "| id | pass | mention | myth-free | cited | behavior | secs |", "|---|---|---|---|---|---|---|"]
    out += [f"| {r['id']} | {'✅' if r['pass'] else '❌'} | {r['mention']} | {not r['myths_found']} | {r['cited']} | "
            f"{r['behavior_ok']} | {r['secs']} |" for r in rows]
    out.append("\n## Answers\n")
    for r in rows:
        out.append(f"### {r['id']} {'✅' if r['pass'] else '❌'}\n**Q:** {r['q']}\n\n**Expected source:** {r['expected']}\n\n"
                   f"**Cited:** {', '.join(r['citations']) or '—'}\n\n{r['answer']}\n")
    rep = REPO_ROOT / "data" / "eval" / "report.md"
    rep.write_text("\n".join(out), encoding="utf-8")
    print(f"\n{passed}/{n} passed. Report: {rep}")


if __name__ == "__main__":
    main()
