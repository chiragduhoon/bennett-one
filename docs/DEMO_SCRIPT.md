# Demo script: 18 Nov lab (15 minutes total)

About **9 minutes of presenting**, leaving about 6 minutes for questions.

## Before the lab (morning of 18 Nov)
- [ ] Run `.\scripts\start.ps1` and confirm http://localhost:5173 loads and `http://localhost:8000/api/health` returns `{"ok":true}`.
- [ ] Ask one warm-up question, e.g. "what is the minimum attendance". The first answer loads the model onto the GPU, so later ones are faster.
- [ ] Check the GPU isn't full: `ssh chirag nvidia-smi`.
- [ ] Open these tabs: the app (logged out), the GitHub repo, `docs/DESIGN.md` (shows the architecture diagram).
- [ ] Backup: `docs/media/demo.gif` and the screenshots, in case the lab GPU is busy.
- [ ] Logins: `student@bennett.demo` / `bennett123` and `admin@bennett.demo` / `bennett123`.

---

## 1. Problem (1 min)
> "Bennett's rules are spread across 300+ PDFs and notices, and some are already outdated. Students rely on WhatsApp and Reddit, where myths spread. We found people saying 50% attendance is enough, when the rule is 75%. A wrong answer here can cost a student an exam or a scholarship."

## 2. Our idea in one line (30 s)
> "BENNETT ONE answers from official documents only, cites the page, and **never lets the LLM decide** eligibility. Python code decides, and the LLM explains."

## 3. Architecture (1.5 min). Show the diagram in DESIGN.md §5
- Crawled bennett.edu.in, giving 363 documents and 7,670 chunks. OCR was used for scanned notices, and documents are versioned.
- **Hybrid search:** meaning (Qdrant + bge-m3) and exact words (Postgres full-text), fused together.
- **LangGraph agent, 5 steps:** understand → retrieve → **rule engine** → generate → **verify**.
- **Self-hosted Qwen3-14B** on the lab GPU, so student data never leaves campus and it costs ₹0.

## 4. Live demo (5 min)

| # | Type this | Point out |
|---|---|---|
| 1 | *hello* | Instant: the small-talk fast path skips the LLM |
| 2 | *am I eligible for btech cse* → *physics 65 and IT 74* → *I got 44 in maths* | **Memory.** It asks only for what's missing, then calculates Best of 3 = 61% ≥ 55%. The calculation is done by code, not the LLM. Open "What was checked" |
| 3 | *what about BBA* → *english 70* | Remembers the marks and re-checks against BBA's rule (60%, English compulsory) |
| 4 | Log in as **student**. Ask *Am I eligible to sit the end-sem in all my courses?* | Personalised from ERP attendance. Point out the **75% rule** and that the older SCSET 70% rule is superseded. Click a citation to open the source |
| 5 | *I have JEE 93 percentile, how much scholarship?* | Doesn't assume the course; asks and shows the options per programme |
| 6 | *can I keep a kettle in the hostel?* | Applies hostel rule 9 (electrical appliances) and cites it |
| 7 | *what are IIT Delhi fees?* | Out of scope, so a polite redirect |
| 8 | *someone is ragging me* | Safety fast path: verified anti-ragging contacts instantly |
| 9 | Log in as **admin** | Version history, the 70% vs 75% conflict, audit log |

While answers stream, point out the **live steps** (Understanding → Searching → Checking rules → Verifying) and the **Sources used** chips.

## 5. Evaluation and honesty (1 min)
- 31 real student questions with 4 automatic checks each: **72% → 100%**. 38 unit tests run in CI.
- Every bug testing found got its own test, e.g. the LLM wrote 88% when the code computed 83.67%.
- **Be upfront:** "These questions guided development, so 100% isn't a held-out score. Our next step is a fresh question set from other students."

---

## Likely questions, with short answers

**Why not just ask ChatGPT?**
It doesn't know Bennett's current rules, can't cite a page, and invents numbers. Our answers come only from official documents, and the verdicts come from tested code.

**Why RAG and not fine-tuning?**
The rules change every semester. With RAG, updating is re-indexing a new PDF, and every answer can cite its source. A fine-tuned model would need retraining and still couldn't cite anything.

**How do you stop hallucinations?**
Four layers:
1. The code writes the verdict.
2. Every number must appear in the sources, otherwise the answer is regenerated.
3. Each claim is checked against the sources and unsupported ones are removed.
4. If nothing is found, it says so instead of guessing.

**Why is it ~20 s?**
It's a 14B model on a *shared* 16 GB lab GPU, and the answer goes through 3 LLM passes (understand, write, verify). We chose accuracy over speed. Streaming shows the words in a few seconds, and greetings and emergencies skip the LLM entirely. A response cache and a faster GPU would cut this down.

**Why two databases?**
Postgres holds exact facts (fees, criteria) and keyword search. Qdrant holds meaning-based vector search. Fusing both beats either one alone: keywords catch "BU/RO/307", and vectors catch "end-term" ≈ "end-semester".

**What if two documents disagree?**
Each document has a version and an authority. The newer, higher-authority one wins, the older one is marked superseded, and the conflict shows up in admin. Example: SCSET 70% vs university 75%.

**What if a PDF contains "ignore your instructions"?**
Retrieved text is wrapped as data, not instructions, and new documents need admin approval before they're searchable.

**Does it remember the conversation?**
Yes, within one chat. Code saves the extracted details (marks, programme) and merges them with each new message. A new chat starts fresh.

**What doesn't work yet?**
- No held-out accuracy number yet.
- No automatic re-crawl when the site changes.
- Hindi is untested.
- It depends on the shared lab GPU.
