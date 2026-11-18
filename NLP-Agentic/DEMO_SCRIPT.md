# Demo script: NLP & Agentic AI (15 minutes total)

About **9 minutes of presenting**, leaving about 6 minutes for questions. This version puts the language understanding and the agent at the centre. For the general product demo, see [../GenAI/DEMO_SCRIPT.md](../GenAI/DEMO_SCRIPT.md).

## Before the lab
- [ ] Run `.\scripts\start.ps1`. Check that http://localhost:5173 loads and `http://localhost:8000/api/health` returns `{"ok":true}`.
- [ ] Ask one warm-up question so the model is loaded on the GPU.
- [ ] Check the GPU isn't full: `ssh chirag nvidia-smi`.
- [ ] Open these tabs: the app, `NLP-Agentic/DESIGN.md` (agent graph in §5.1), and http://localhost:8000/docs (to show the raw JSON).
- [ ] Backup: `docs/media/demo.gif` and the screenshots.
- [ ] Logins: `student@bennett.demo` / `bennett123`, `admin@bennett.demo` / `bennett123`.

---

## 1. Problem (1 min)
> "Students don't write clean queries. They write 'PJYSICS 65 AND IT 74', '82% in PCM', 'end sem ke liye attendance kitni chahiye?', or just 'what about BBA'. The answers are spread across 364 official documents, and some rules have been replaced. We need to understand messy language, find the right passage, and apply the rule without the model making things up."

## 2. Our design in one line (30 s)
> "A LangGraph agent with five fixed steps. The LLM does the language work (understand, write, check). Code does the decisions, and every sentence is checked against its source."

## 3. Architecture (2 min). Show the diagrams in DESIGN.md §5
- **Before the graph:** regex fast paths for safety and small talk, with no LLM.
- **understand:** one JSON call gives the intent (14 + out-of-scope + greeting), about 20 slots, and a rewritten search query. Then `merge_memory` adds what the user said earlier in the chat.
- **retrieve:** hybrid search, bge-m3 vectors + Postgres full-text, fused with RRF, filtered by school, current version and intent category.
- **validate:** tools chosen from the intent and slots: programme matcher, rule engine, fee tables, calendar table.
- **generate → verify:** a grounded answer, a number check (regenerate once), a claim-by-claim check, then citation repair.
- **Why not a ReAct agent?** A 14B model on a shared GPU chooses tools unreliably, every loop step costs seconds, and it can't be unit-tested. A fixed graph is predictable and shows its steps live.

## 4. Live demo (5 min)

| # | Type this | Point out |
|---|---|---|
| 1 | *hello* | Small-talk fast path: instant, no LLM |
| 2 | *am I eligible for btech cse* → *PJYSICS 65 AND IT 74* → *I got 44 in maths* | **Slot filling + memory + typo handling.** "cse" resolves to B.Tech CSE; "PJYSICS" becomes Physics; Maths is merged with the earlier marks. Best of 3 = 61% ≥ 55%, computed by the rule engine |
| 3 | *what about BBA* → *english 70* | **Follow-up.** The topic changes and the marks carry over |
| 4 | *end sem ke liye attendance kitni chahiye?* | **Hinglish.** Intent `attendance`; the 75% rule cited from the attendance notification, p. 1 |
| 5 | Log in as **student**. *Am I eligible to sit the end-sem in all my courses?* | **Tool use with personal data.** No numbers typed; the attendance tool reads the ERP profile. The superseded SCSET 70% rule is ignored |
| 6 | *can I keep a kettle in the hostel?* | **Category reasoning.** The rule says "electrical appliances"; the answer applies it and cites hostel rule 9 |
| 7 | *what does the annual report 2024-25 say about research publications and patents?* | **Long-document retrieval** from the 179-page Annual Report, cited at p. 148 |
| 8 | *what are IIT Delhi fees?* | **Intent override** to out-of-scope |
| 9 | *someone is ragging me* | **Safety fast path:** verified helplines instantly |
| 10 | In http://localhost:8000/docs, run `POST /api/chat` with *physics 78 maths 85 chemistry 83 english 88 for btech cse* | Show the raw `understanding` JSON (intent, marks, search_query), the `memory`, the `rule_result` and the citations |

While answers stream, point out the **live agent steps** (Understanding → Searching → Checking rules → Writing → Checking every claim → Verifying).

## 5. Evaluation and honesty (1 min)
- 31 real student questions, 4 automatic checks each: **72% → 100%**. 41 unit tests in CI, covering the tools, memory and document classification.
- Every bug the evaluation found has a regression test ("cse" → M.Tech, "PJYSICS", "82% in PCM", 88% vs 83.67%).
- **Be upfront:** the questions guided development, so this isn't a held-out score. Intent accuracy hasn't been measured on its own yet.

---

## Likely questions, with short answers

**Is this really an agent if the graph is fixed?**
Yes. It keeps state across steps, uses tools (search, rule engine, SQL tables, calendar) and checks its own output. What it doesn't do is let the LLM pick the next step freely. We chose that for reliability and testability on a 14B model.

**How does it remember the conversation?**
After each answer, code saves the extracted slots (marks, programme, intent, CGPA…) in Postgres. On the next message, `merge_memory` combines them with the new extraction: facts about the person persist, the topic carries over on follow-ups, and new values replace old ones subject by subject.

**How do you classify intent?**
One schema-constrained JSON call to Qwen3-14B at temperature 0. Code then overrides it where rules are clearer: other institutions become out-of-scope, unknown labels become `general`.

**Why hybrid search?**
Vectors catch paraphrases and Hinglish; full-text search catches exact codes like "BU/RO/307". Reciprocal Rank Fusion combines the two rankings without needing comparable scores.

**How do you stop hallucinations?**
1. Code writes the verdict line.
2. Every number must appear in the evidence, otherwise the answer is regenerated.
3. Each factual sentence is labelled supported or unsupported, and unsupported ones are removed.
4. Fake citation tags are stripped, and if nothing is left the user gets a "not found" answer.

**What if a PDF says "ignore your instructions"?**
Retrieved text is wrapped in `<source>` tags and declared as data, and uploads need admin approval before they're searchable.

**What would you improve next?**
- A labelled intent and slot set with a confusion matrix
- Explicit translation of Hinglish search queries
- A separate, smaller verifier model
- Wider categories for annual-report questions
