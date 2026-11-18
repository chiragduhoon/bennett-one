# BENNETT ONE: NLP & Agentic AI course submission

**Code:** this repository. The agent is in [`backend/app/agents/graph.py`](../backend/app/agents/graph.py), retrieval in [`backend/app/retrieval/hybrid.py`](../backend/app/retrieval/hybrid.py), and the document NLP pipeline in [`backend/app/ingest/`](../backend/app/ingest). This folder holds the documents for the NLP & Agentic AI course.

> Student project (School of AI, B.Tech AI). Not an official University service.

## Where each part is covered

| # | Item | Where |
|---|---|---|
| 1 | Code on GitHub | This repository |
| 2 | Use case and overall functionality | This page (below) |
| 3 | High-level design: agent graph, NLP pipeline, how components interact | [DESIGN.md §5 Architecture](DESIGN.md#5-architecture) |
| 4 | Tech stack, including the agentic framework | [DESIGN.md: Tech stack](DESIGN.md#tech-stack) |
| 5 | Overview, then the project working on examples | Slides (presented live; not in the repo because they contain university photos and logos) · [DEMO_SCRIPT.md](DEMO_SCRIPT.md) |
| 6 | Audience questions | [DEMO_SCRIPT.md: Likely questions](DEMO_SCRIPT.md#likely-questions-with-short-answers) |
| — | Design template (sections 1–8) | [DESIGN.md](DESIGN.md) |

## Use case

Students ask about attendance, exams, scholarships, fees, admissions and hostel rules in their own words, with typos, abbreviations, Hinglish and follow-ups. The answers are in **364 official Bennett documents** (8,508 indexed passages), including the 179-page University Annual Report 2024-25.

BENNETT ONE understands the question, finds the right passage, applies the official rule in code, and writes an answer in which every sentence is checked against its source.

## What the NLP and agent parts do

| Capability | How |
|---|---|
| **Intent classification + slot filling** | One schema-constrained JSON call: 14 intents plus out-of-scope and greeting, about 20 slots (marks, CGPA, JEE percentile, attendance, dates…) and a rewritten search query |
| **Dialogue memory** | Slots are saved per chat and merged by code: marks merge subject by subject, and the topic carries over on follow-ups |
| **Normalisation** | Abbreviation tables ("cse" → B.Tech Computer Science Engineering) and fuzzy matching for typos ("PJYSICS" → Physics) |
| **Hybrid retrieval** | bge-m3 multilingual vectors + Postgres full-text, fused with Reciprocal Rank Fusion, filtered by school, current version and intent category |
| **Document NLP** | PDF extraction, OCR with word segmentation for scanned notices, section-aware chunking, document versioning |
| **LangGraph agent** | understand → retrieve → validate (tools) → generate → verify, with the steps streamed live to the UI |
| **Tools** | Rule engine (eligibility, attendance, scholarship, refund, merit bands), fee and criteria tables, calendar date table |
| **Self-checking** | Numeric grounding check with one regeneration, claim-by-claim verification, citation repair, never-empty fallback |
| **Fast paths** | Regex detectors for safety (including Hindi phrases) and small talk, which skip the LLM |

## Results

- **31/31** on the 31-question evaluation (baseline single RAG chain: 21/29). The latest run, after adding the Annual Report, is still 31/31.
- **41** unit tests in CI (rule-engine tools, chat memory, safety and small-talk detectors, document classification).
- Median **20 s** end to end, with 3 LLM calls per question on a shared 16 GB lab GPU.

## Further reading

- [DESIGN.md](DESIGN.md): the NLP & agent design document
- [DEMO_SCRIPT.md](DEMO_SCRIPT.md): demo plan and Q&A preparation
- [../docs/HOW_IT_WORKS.md](../docs/HOW_IT_WORKS.md): a detailed walkthrough of every component
- [../GenAI/](../GenAI): the same project, documented for the Generative AI course
