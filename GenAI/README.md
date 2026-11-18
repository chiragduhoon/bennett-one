# BENNETT ONE: Generative AI course submission

**Project demo:** 18 Nov 2026 lab · 15 minutes including Q&A
**Code:** this repository. The application code lives in [`backend/`](../backend), [`frontend/`](../frontend) and [`scraper/`](../scraper). This folder holds the documents for the GenAI course.

> Student project (School of AI, B.Tech AI). Not an official University service.

## Where each guideline is covered

| # | Guideline | Where |
|---|---|---|
| 1 | Code on GitHub; share the link | This repository |
| 2 | Document explaining the use case and overall functionality | This page (below) |
| 3 | High-level design: architecture diagram and how components interact | [DESIGN.md §5 Architecture](DESIGN.md#5-architecture) |
| 4 | Tech stack: language, databases, UI framework, agentic framework | [DESIGN.md: Tech stack](DESIGN.md#tech-stack) |
| 5 | Overview, then the project working on examples | Slides (presented live; not in the repo because they contain university photos and logos) · [DEMO_SCRIPT.md](DEMO_SCRIPT.md) |
| 6 | Audience questions | [DEMO_SCRIPT.md: Likely questions](DEMO_SCRIPT.md#likely-questions-with-short-answers) |
| — | Design-document template from the application-design lecture (sections 1–8) | [DESIGN.md](DESIGN.md): 1 Problem and users · 2 Why GenAI, and which kind · 3 Scope · 4 Requirements · 5 Architecture · 6 Failure modes and guardrails · 7 Evaluation plan · 8 Open questions and risks |

## Use case

Students at Bennett University ask the same questions every semester:
- *Can I sit the end-sem exam with 72% attendance?*
- *Do I keep my scholarship with CGPA 8.2?*
- *Am I eligible for B.Tech CSE with these marks?*

The answers are spread across **364 official documents**: PDFs, notices, fee tables, calendars, and the University Annual Report. Some older rules have been replaced by newer ones. Students end up relying on seniors, WhatsApp groups and Reddit, where myths spread (e.g. "50% attendance is enough"; the rule is 75%).

**BENNETT ONE** answers these questions from the official documents only. It cites the document and page for every fact, and it never lets the language model decide eligibility.

## What it does

| Feature | What the user sees |
|---|---|
| **Cited chat** | Ask anything about Bennett in plain language (typos and Hinglish included). The answer streams in with live agent steps and citation chips that open the source PDF at the cited page |
| **Rule-engine verdicts** | Admission eligibility (Best-of-3, IB, graduation %), attendance, scholarship continuation, refunds and merit scholarships are computed by tested Python code. The LLM only explains the result |
| **Personalisation** | A logged-in student gets answers for their own school and programme, with their ERP attendance checked automatically |
| **Conversation memory** | Marks and programme given earlier in a chat are remembered. "What about BBA?" re-checks with the same marks |
| **Verification** | Every number must appear in the sources, and every factual sentence is checked against them. Unsupported sentences are removed and the user is told |
| **Version awareness** | Superseded rules (e.g. the old SCSET 70% attendance rule) are never used as current |
| **Safety fast path** | Ragging, self-harm or emergency messages get verified helplines instantly, without the LLM |
| **Eligibility checker, dashboard, policy library** | Forms and pages that call the rule engine directly |
| **Admin console** | Upload documents (pending until approved), see version diffs, rule conflicts and the audit log |

## Results

- **31/31** real student questions pass all four automatic checks (key facts, no myths, cited, correct behaviour), up from 21/29 for the plain-RAG baseline. The same questions guided development, so this is a regression score, not a held-out one.
- **41** unit tests in CI.
- Median latency **20 s** on a shared 16 GB lab GPU, with tokens streaming from the first seconds.

## Further reading

- [DESIGN.md](DESIGN.md): the design document
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md): demo plan and Q&A preparation
- [../docs/HOW_IT_WORKS.md](../docs/HOW_IT_WORKS.md): a detailed walkthrough of every component and decision
- [../data/eval/report.md](../data/eval/report.md): the per-question evaluation report
- [../NLP-Agentic/](../NLP-Agentic): the same project, documented for the NLP & Agentic AI course
