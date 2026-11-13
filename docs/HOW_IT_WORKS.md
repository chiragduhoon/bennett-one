# BENNETT ONE: how it works, and why we built it this way

> This is a living document, updated after every build step. Each component answers four questions: **What is it? How does it work? Why did we pick it? What did we reject, and why?** Read it before a demo or viva.

---

## 0. The core idea in one paragraph

Ask ChatGPT "What attendance do I need for end-sem exams at Bennett?" and it will **guess**. It has never read Bennett's rulebooks, it doesn't know your school, and it can't tell a 2022 rule from its 2025 replacement. BENNETT ONE fixes this in three ways:
1. **It answers only from official Bennett documents** that we collected. This is Retrieval-Augmented Generation, or RAG.
2. **It knows who is asking** (school, programme, semester), so it applies the right school's rules.
3. **It never lets the LLM do the maths or make the decision.** Eligibility, fees and attendance checks run in plain Python (the *rule engine*). The LLM only *explains* the result and *cites the page* it came from.

That last point is the big difference from a normal chatbot. **The LLM is the spokesperson, not the judge.**

```
Question ─► Who is asking? ─► Find official passages ─► Check rules in code ─► LLM writes answer ─► Verify every claim has a source ─► Answer + citations
            (profile)          (hybrid search)            (rule engine)          (Qwen3-14B)         (verifier)
```

---

## 1. Data collection (DONE)

### 1.1 The crawler: `scraper/crawl.py`
**What:** a small program that visits bennett.edu.in page by page. It saves each page's HTML and clean text, and downloads every linked PDF.

**How:**
- It starts from seed pages (`/programs/`, `/admission/`, `/notices-registrar-office/` …) and follows links, but only into relevant sections (programmes, schools, admissions, notices, exams, ordinances, hostels, placements).
- It reads `robots.txt` first and skips anything the site asks bots not to touch.
- It waits 1 second between requests so it doesn't load the university's server.
- It **caches**: a page already on disk is never downloaded again, so the crawl can stop and resume safely.
- It writes `data/raw/manifest.jsonl`, with one line per file: `url`, `sha256` fingerprint, and `fetched_at` time.

**Why the manifest matters:** every answer the app gives can point back to the **exact official URL** and the date we fetched it. The sha256 fingerprint also tells us when Bennett *changes* a document: the same URL with a new fingerprint means the policy was updated. That feeds the **version tracking** feature.

**Alternatives rejected:**
- *Copy-pasting by hand.* About 80 programmes and 200+ PDFs is too slow, and it can't be redone when the site changes.
- *Scrapy.* It's a full framework, overkill for one site.
- *Asking ChatGPT for the data.* It would invent numbers.

### 1.2 One-off downloader: `scraper/fetch_page_pdfs.py`
It downloads *every* PDF linked from one page. We used it on the Registrar Notices page and got 112 of 113 PDFs: academic rules for each school, the attendance notification, exam manuals, academic calendars 2023-24 → 2025-26, scholarship and refund policies, hostel rules, and forms.

### 1.3 The parser: `scraper/parse_seed.py`
**What:** turns messy web pages into **structured data** (YAML files in `data/seed/`).

| File | Contents | Why structured? |
|---|---|---|
| `schools.yaml` | the 9 schools and their programmes | the app needs an exact list for filters and menus |
| `eligibility.yaml` | 47 programmes: eligibility text **plus** extracted rules (min 55%, Best-of-3, compulsory Physics + Maths, excluded vocational subjects, IB 24 credits) | the **rule engine** needs numbers, not prose |
| `fees.yaml` | 66 programmes, AY 2026-27 tuition by year, totals, hostel, other charges | fee questions need exact numbers; the LLM must not "remember" them |

**A trap we caught:** programme pages contain **hidden, commented-out fee blocks** with *older* numbers. B.Tech CSE shows ₹3,70,000 in the hidden block, but the official fee page says ₹3,80,000 for Year 1. A naive scraper would have fed wrong fees into the app. The parser ignores HTML comments and takes fees only from the official `/admission/fee-structure/` page. **Lesson: always trust the authoritative page, not whichever copy you happened to find.**

**Crawl totals (12 Nov 2026):** 352 web pages, 451 PDFs (1.9 GB), 103 programme pages parsed (65 with duration, 100 with an official summary).

### 1.3b Official brand assets: downloaded, not generated
We took logos **straight from Bennett's own website and CDN**, not from screenshots or AI image generators:
- the header logo with the NAAC A+ badge, and the crest (transparent PNG)
- **all 9 official school logos at 1200×1200, transparent** (`FINAL-LOGOS_*.webp`)

**Why not AI-generate logos?** An image model can't reproduce a real trademark exactly. It produces something *almost* right, and that makes a product look fake. Screenshots are blurry and carry backgrounds. The originals are sharp at any size.

### 1.4 Private data: `data/private/` (git-ignored, never uploaded)
- Your ERP-derived demo profile: SoAI, B.Tech AI, Sem 5, your courses, attendance and CGPA.
- Logo files, the campus banner, and the colours extracted from the logo: blue `#005098`, red `#d81830`, maroon `#a01830`, cyan `#08a0e0`.

---

## 2. The AI models (DONE: running on the lab GPU)

### 2.1 Where they run
**Machine:** a shared campus lab server with an **NVIDIA RTX 2000 Ada (16 GB VRAM)**. Qwen3-14B (Q4, about 9 GB) and bge-m3 (0.6 GB) stay loaded together in about 11 GB. During development we also used a larger RTX 5000 Ada (32 GB) box; because the API is OpenAI-compatible, moving between the two machines was a one-line `.env` change.

**Why a lab GPU and not the OpenAI API?**

| | Local (ours) | OpenAI API |
|---|---|---|
| Cost | free | pay per token |
| Privacy | student data never leaves campus | sent to a US company |
| Works offline / no key | yes | no |
| Shows AI-engineering skill | yes: we deploy and serve models | just an API call |

**Fallback:** if the GPU is short on memory (it is shared with other students' training jobs), the agent can fall back to Qwen3-8B (5 GB), set by `LLM_FALLBACK_MODEL`.

### 2.2 Ollama (the model server)
**What:** a program that loads LLMs onto the GPU and exposes them as a web API on port 11434. That API is **OpenAI-compatible**, so our code uses the standard `openai` Python library pointed at our own server.

**Why Ollama instead of vLLM** (the original plan)? vLLM is faster for many simultaneous users, but on these lab machines we have **no sudo and no Docker access**, and vLLM is hard to install that way. Ollama was already installed and running. For a demo with a handful of users, the speed difference doesn't matter.

**Why "OpenAI-compatible" matters:** to switch to GPT, Claude or vLLM later, we change one URL in `.env`. **No code changes.** The blueprint called this "provider independence".

### 2.3 Qwen3-14B (the language model)
**What:** a 14-billion-parameter open model from Alibaba, strong at reasoning, following instructions, producing structured JSON output and handling multilingual text.

**Quantization (Q4_K_M):** at full precision a 14B model needs about 28 GB. Quantization stores each weight in about 4 bits instead of 16, giving about **9 GB with a small quality loss**. That's what makes it fit on a shared GPU.

**First real test (12 Nov):** we gave it the attendance rule as context and asked "I have 74% in Agentic AI, can I sit the end-sem?" It answered *"No… below the required minimum of 75% (Source: Notification-for-Minimum-Attendance-for-Students.pdf, p1)"*. It used the context, gave the right verdict and cited the source. That took 28 s including the one-time model load; later answers are much faster. (The context in that test was hand-written. In the app, the rule engine will make that decision and the LLM will only phrase it.)

**Why Qwen3-14B?**
- It's the best quality that fits comfortably.
- It has a "thinking" mode we can switch on only for hard tasks (comparing policies).
- It reliably outputs JSON, which our agent steps need.

**Rejected:** Llama-3-8B (weaker at reasoning and JSON); 32B+ models (won't fit alongside the other users).

**Downloaded from Hugging Face, not the Ollama registry,** because the campus network times out on Ollama's registry but allows huggingface.co.

### 2.4 bge-m3 (the embedding model)
**What:** converts a piece of text into a list of **1024 numbers** (a *vector*) that captures its *meaning*. Texts with similar meanings get vectors pointing in similar directions.

**Proof from our test:**
- "What is the minimum attendance required for end-semester exams?" vs "Students must maintain at least 75% attendance…" → similarity **0.72**
- the same question vs "Hostel fee for triple occupancy is ₹1,70,000" → similarity **0.35**

The meaning matched even though the wording differed ("end-semester" vs "end term"). Keyword search alone would miss that.

**Why bge-m3?**
- It's one of the best open embedding models.
- It handles long passages (8k tokens).
- It understands **Hindi and Hinglish**, so students can ask in mixed language later.
- It's tiny (0.6 GB).

### 2.5 The SSH tunnel
The GPU box sits inside the campus network. The command `ssh -N -L 11435:localhost:11434 <gpu-host>` (wrapped in `scripts/tunnel.ps1`, host from `GPU_SSH_HOST`) makes the laptop's `localhost:11435` **forward securely** to Ollama on the GPU box. The app simply calls `localhost` and the traffic travels encrypted over SSH, with no ports opened to the outside world.

---

## 3. Storage (IN PROGRESS)

We keep **two kinds** of knowledge, because they answer different kinds of questions:

| Question | Best answered by |
|---|---|
| "What is the B.Tech CSE Year-2 tuition for 2026-27?" (exact fact) | a **SQL table** lookup: exact, never paraphrased |
| "What happens if I miss the end-sem because I'm sick?" (meaning) | **semantic search** over rulebook passages |

### 3.1 PostgreSQL: structured facts and keyword search
- **Tables:** schools, programmes, eligibility rules, fees, documents, document versions, users, chat history, audit log.
- **Full-text search** (Postgres's built-in `tsvector`) finds exact terms such as clause numbers, "UFM", "condonation" or course codes like "ABAI3063L". Embeddings are weak at these.
- **Why Postgres:** it's already installed and runs on your laptop, it's the industry standard, and it gives reliable relational joins (programme → school → fees).
- **Our own database server, inside the project.** We didn't reuse the system PostgreSQL. `initdb` created a separate database cluster in `data/pg/cluster`, running on **port 5433** with its own user `bennett`. Why:
  - We didn't need the system superuser password, and we don't need admin rights.
  - The project is self-contained: deleting `data/pg/` resets the database completely.
  - It can't damage any other database on the laptop.
- Start or stop it with `.\scripts\db.ps1 start` / `stop` / `status`. It doesn't start automatically after a reboot, so run `start` first.

### 3.2 Qdrant (embedded mode): vectors
- Stores each document chunk's 1024-number vector, plus **metadata**: school, programme, academic year, document version, page number.
- **Why not pgvector?** The original plan was to keep everything in Postgres, but pgvector must be compiled from source on Windows. Qdrant's *embedded mode* is just `pip install qdrant-client`: it stores everything in a local folder and needs no server. If we deploy to a server later, the same code talks to a Qdrant server.
- **Why Qdrant over ChromaDB?** Qdrant's **metadata filtering** is stronger and faster. "Only SoAI or university-wide documents, only the current version" is a filter that runs **inside** the vector search, not after it. That filter is what guarantees **cross-school isolation**: a Law rule can never leak into an AI student's answer.

### 3.3 Hybrid search (how the two combine)
1. Keyword search (Postgres) → top 20 passages.
2. Vector search (Qdrant, filtered by your school and the current versions) → top 20 passages.
3. **Reciprocal Rank Fusion:** merge the two lists, rewarding passages that rank well in *both*.
4. **Reranker** (bge-reranker): rereads the question and each candidate together and picks the best 6–8.

**Why:** embeddings alone miss exact terms, and keywords alone miss paraphrases. Combined, they're much more reliable.

---

> **Limitation we hit:** embedded Qdrant lets only *one* process open its folder at a time. The API server and the ingestion job can't run together, and auto-reload breaks because the old process still holds the lock. Fix for production: run Qdrant as a server, which needs no code change, just a URL.

---

## 4. Ingestion: turning PDFs into searchable knowledge (`backend/app/ingest/`)

### 4.1 Deciding what to index (`classify.py`)
Of 451 downloaded PDFs, only about **113 are useful to students**. The rest are moot-court scoresheets, journal articles, newsletters and 50 MB scanned curriculum books. Indexing everything would *hurt*: search would return noise. So we use:
- an **allowlist** of useful words: rule, policy, calendar, exam, fee, scholarship, hostel, form …
- an **exclude list**: newsletter, moot, score, journal …
- a **size limit** of 15 MB

Each file also gets **metadata**:

| Field | Example | Why |
|---|---|---|
| `school_id` | `SOL`, or empty = university-wide | cross-school isolation |
| `category` | attendance / exam / fees / calendar … | narrows the search to the right kind of document |
| `family` | "scholarship policy" | groups versions of the *same* policy |
| `academic_year` | 2025-26 (from the filename) | decides which version is current |

### 4.2 Versioning: which document is current?
Bennett publishes new versions of the same policy every year: Scholarship Policy 24-25 → 25-26 → 26-27; Academic Calendar 23-24 → 24-25 → 25-26 → 26-27. The pipeline groups them by family, marks the **newest as `is_current`**, and links older ones with `supersedes_id`. **Search only ever looks at current versions.** Old ones are kept, so the admin can compare them, but they're never used in answers.

**Why it matters:** "What's the scholarship for 90%?" must come from the 2026-27 policy, not 2024-25. A plain RAG system would mix all the years together.

### 4.3 Extraction and OCR (`pipeline.py`, `ocr.py`)
- **PyMuPDF** reads each PDF's text layer **page by page**. We keep page numbers so every citation can say "p. 10".
- **62 PDFs (497 pages) are scans with no text layer**, including the Exam Manual, the Discipline Rules, the 2026-27 Scholarship Policy and the attendance notification. These go through **RapidOCR**, an open-source OCR engine on ONNX Runtime that runs on CPU and needs only a pip install.
- RapidOCR glues words together ("Theminimum attendance criteriafor"). **wordninja** splits them back using English word frequencies → "The minimum attendance criteria for".
- OCR results are **cached by file fingerprint**, so each page is only OCR'd once.

**How the OCR actually ran (12 Nov):** single-threaded it would have taken about 2.5 hours. We split the 62 PDFs between the **laptop** and the **lab machine** (20 CPU cores), each working from opposite ends of the list. A bug: ONNX Runtime ignores the usual thread-limit variable, so each worker grabbed every core, and the shared lab machine's load hit 118. We fixed it with `intra_op_num_threads=3` and ran at `nice 19` (lowest priority), because other students share that machine. **Total: 497 pages, done in about 25 minutes.** GPU OCR wasn't possible: the CUDA build of ONNX Runtime needs NVIDIA libraries we can't install without admin rights.

### 4.3b Calendars become a date table (`app/ingest/calendar.py`)
**The problem we saw:** "When does end-sem start?" got the right start date but missed the end date and the practicals. A calendar is a day-by-day table, so chunking spreads one exam period across several passages.

**The fix:** every calendar PDF is parsed into rows of (date, teaching day or holiday, event). Consecutive days with the same event are merged into ranges, so "End Semester Examination (Odd 2026-27)" becomes **10 Dec → 24 Dec 2026**, alongside the practicals (7–9 Dec) and vacation (25 Dec–3 Jan). The agent answers date questions from this table instead of from text fragments. It knows the freshmen and returning-student calendars are separate, and uses only the current year.

### 4.4 Chunking
Each page is cut into passages of about **1000 characters**, about one rule or clause each:
- Cuts happen at **paragraph boundaries**, so a rule isn't split mid-sentence.
- **One paragraph overlaps** between neighbouring chunks, so context isn't lost at the cut.
- The nearest **heading** is remembered as the chunk's `section` ("12. Attendance").

**Why ~1000 characters?** Too small, and a rule loses its context ("…shall not be eligible" — eligible for what?). Too big, and the passage mixes topics, so the match becomes vague and wastes the LLM's context.

**Result:** 6,346 passages from 319 document versions. The OCR'd documents are added on top of that.

---

## 5. The rule engine: the "judge" (`backend/app/rules/engine.py`)

**The most important design decision in the project.** An LLM is a text predictor. It can't be *trusted* to:
- compute a Best-of-3 average correctly every time
- compare 74.0 with 75 reliably
- know which of two contradicting rules applies

So all decisions are made in plain Python, which is **deterministic** (the same input always gives the same output) and **tested**.

### 5.1 Admission eligibility
It reads the official criteria extracted from Bennett's eligibility page (minimum %, compulsory subjects, excluded vocational subjects, IB credits) and computes:
- **Best of 3** = the compulsory subjects (e.g. Physics + Maths) plus the highest remaining *non-vocational* subject
- compares it with the minimum (55% for B.Tech CSE)
- marks programmes with an interview or portfolio as **NEEDS_VERIFICATION**, because we can't evaluate those rounds

### 5.2 Attendance, and a real policy conflict we found
While building this we found a **genuine conflict in Bennett's own documents**:
- *Academic Rules for SCSET (UG), March 2022:* "minimum attendance of **70%**"
- *Notification BU/RO/307/2022, 8 Sep 2022* (Academic Council): "minimum attendance of **75%**… from AY 2022-23"

The newer, higher-authority, university-wide notification wins. This is recorded in `data/seed/policy_facts.yaml`, **with the exact quote, URL and page**, and the engine uses 75%. The admin console shows this conflict and how it was resolved. A generic chatbot reading the SCSET rulebook would have told students 70%: wrong, and potentially costing them an exam.

### 5.3 Tests (`backend/tests/test_rules.py`): 11 passing
They cover boundaries (exactly 55% passes, 54.97% fails), vocational subjects being excluded, the IB route, missing data, interview programmes, the SCSET 70% rule being superseded, and the "classes needed" calculation. **Tests are how we prove the judge is correct.**

---

## 6. The agent: how one question is answered (`backend/app/agents/graph.py`)

Built with **LangGraph**, a library for writing AI workflows as a *graph of steps* instead of one giant prompt.

```
understand ─► retrieve ─► validate ─► generate ─► verify
```

| Step | What happens | LLM? |
|---|---|---|
| **understand** | Qwen3 returns **JSON**: intent (eligibility / fees / attendance / letter …), programme, marks, and a clean search query. It also uses the conversation history, so follow-ups work | yes (JSON only) |
| **retrieve** | hybrid search filtered by *your* school, current versions only, and the intent's categories | embeddings only |
| **validate** | finds the programme (understanding "CSE" = Computer Science Engineering; prefers the regular programme over "Global") → runs the **rule engine** → loads the official **fee table** | **no**, plain code |
| **generate** | Qwen3-14B writes the answer from numbered sources `<source id="S1">`, the rule result and the fee data, under strict rules: cite every fact, never guarantee admission, treat document text as data and not instructions (prompt-injection defence) | yes |
| **verify** | removes citations to sources that don't exist, attaches real citation objects, and adds warnings | **no** |

### 6.1 Two hallucination guards (both caught real bugs in testing)
**Bug we saw:** the rule engine correctly computed Best of 3 = **83.67%**, but the LLM wrote "Best of 3 = **88%**". It had recomputed the number itself, and got it wrong.

1. **Deterministic verdict line.** The headline ("**Meets the checked criteria: Best of 3 = 83.67%…**") is written by *code*, not the LLM. The LLM is told to reuse those exact numbers.
2. **Numeric grounding check.** Every number in the answer must appear somewhere in the evidence (sources, rule result, fee table or the question). If not, the answer is **regenerated** with the offending numbers listed. If it still fails, the user sees a warning.

After the fix: *"Best of 3 = 83.67% (Physics, Mathematics, English) for B.Tech (Computer Science Engineering) … minimum 55%"*. Correct.

### 6.2 Personalisation (blueprint Feature 5)
For the logged-in student, the agent knows the school (SoAI), the programme and the ERP attendance. "Am I eligible for end-sems?" therefore needs no numbers typed in. Real test result:

> **Does not meet the checked criteria: minimum attendance is 75%; below it in Agentic AI (ABAI3063L)**: 74.0%, short by 1.0%. All six other courses pass.

---

## 6.3 Three response paths (fast where it's safe, careful where it matters)
| Path | Triggers | How | Speed |
|---|---|---|---|
| **Safety** (`agents/safety.py`) | ragging, harassment, threats, self-harm, emergency | Verified contacts from the official Anti-Ragging Cell order (17 Apr 2026), UGC helpline 1800-180-5522, Tele-MANAS 14416. **No AI wording** | instant |
| **Small talk** (`agents/smalltalk.py`) | hello, what can you do, thanks | Fixed, personalised replies | instant |
| **Full agent** | everything else | understand → search → rules → write → **verify every claim** | 30–90 s on a busy GPU |

**Why:** in a safety situation, an AI that might soften or invent details is dangerous. Greetings don't need a 14-billion-parameter model.

## 6.4 Claim-by-claim verification (accuracy over speed)
After Qwen writes an answer, a second strict pass labels **every sentence** as *supported*, *unsupported* or *not factual* (advice, questions to the user), against the exact source passages, rule results and data tables. **Unsupported sentences are removed**, and the user is told how many were removed. This roughly doubles GPU time per answer. We accepted that trade-off because accuracy comes first.

## 6.5 More decisions made by code, with page-cited facts (`data/seed/policy_facts.yaml`)
| Topic | Rule engine function | Source |
|---|---|---|
| Admission eligibility | `check_admission` | Eligibility & Selection Criteria page |
| Attendance | `check_attendance` | Notification BU/RO/307/2022, p1 (75%) |
| Scholarship continuation / Academic Scholarship | `check_scholarship` | Scholarship Policy 2026-27, pp. 4–5: SoAI ≥ 8.5, others ≥ 8.0, no backlogs, no UFM, no disciplinary case, top 10% for the Academic Scholarship (10%) |
| Refunds | `check_refund` | Fee Refund Policy 2026-27: full refund until 30 Sep 2026; processing fee ≤ ₹1,000 until 31 Oct; hostel 100/50/25/0% by day |
| Calendar dates | `find_events` | Academic Calendar 2026-27 (date table) |

**Myths in the Reddit test set that the official documents disprove:** "50% attendance is enough" (it's 75%); "₹5k processing fee" (≤ ₹1,000 in the window); "admissions never close" (31 Oct 2026). **One myth that turned out true:** scholarships *are* first-come, first-served (Scholarship Policy 2026-27, p1). We corrected our own test set, because tests must follow the documents, not our assumptions.

There are now **36 unit tests** covering the rule engine, safety, small talk and chat memory.

## 6.6 Chat memory: it remembers within one chat (`merge_memory` in `graph.py`)
**Problem:** a student wrote "Physics 65 and IT 74", then "I got 44 in Maths". The assistant forgot the first message and asked for Physics again.

**Why it happened:** we only showed the LLM the old messages as text and hoped it would copy the marks over. LLMs don't do this reliably.

**Fix: structured memory, handled by code.** After each answer we save the extracted details (marks, programme, intent, CGPA, JEE score…) with the message in Postgres (`chat_messages.meta.memory`). On the next message, `merge_memory` combines them:
- **Facts about the person** (marks, scores, CGPA, dates) are remembered for the whole chat. Marks merge **subject by subject**: "Maths 44" is added to "Physics 65, IT 74". A corrected value ("sorry, Maths was 80") replaces the old one.
- **The topic** (programme, intent) carries over on follow-ups, so "what about BBA" re-checks BBA with the marks you already gave.
- A **new chat** starts empty, and different chats never share memory.

**Fixes found while testing this conversation:**
- **Typos.** "PJYSICS" now matches Physics, using close matching (`difflib`) against known subject names.
- **"Not mentioned" ≠ "not studied".** When a compulsory subject is missing, the engine **asks** for it instead of declaring "not eligible". It adds: *"if you did not study it in Class XII, you do not meet this rule"*.
- **Best of 3 is an average.** With Physics 65, Maths 44 and IT 74, the Best of 3 is **61% ≥ 55%, so the student meets it**. The old version wrongly said Maths 44 disqualified them.
- **Code builds the "Please share" list and the example reply** from the rule engine. The LLM can no longer ask for marks the student already gave.
- **The verdict line is shown only once.** The LLM may not invent next steps such as "interview", and may not say "you are eligible".

## 7. API (`backend/app/main.py`, FastAPI)
- `POST /api/chat/stream`: **Server-Sent Events**. The browser receives live `step` events ("Searching official Bennett documents…", "Checking attendance rules…"), then the final answer. That's why the UI shows the agent "thinking" step by step.
- `POST /api/eligibility`, `POST /api/attendance/check`: the rule engine directly, with no LLM. Instant and exact.
- `GET /api/programmes`, `/api/programmes/{id}`, `/api/schools`, `/api/documents`, `/api/chunks/{id}`, `/api/versions/{id}/file`: catalogue and sources. The last one serves the original PDF so the UI can open it **at the cited page**.
- Admin: upload (always **pending** — *"a document never becomes authoritative just because someone uploaded it"*), approve or reject, version diff, conflicts, audit log.
- Auth: **bcrypt**-hashed passwords and **JWT** tokens; admin routes check the role.
- Interactive API docs are generated automatically at `http://localhost:8000/docs`, which is handy for a viva.

## 8. Frontend (`frontend/`, React + TypeScript + Tailwind)
- **Brand tokens** sampled from the official logo: blue `#005098`, red `#d81830`, maroon `#a01830`, cyan `#08a0e0`. The fonts are Cinzel (matching the serif "BENNETT UNIVERSITY" wordmark), Poppins and Inter.
- **Pages:**
  - **Landing:** the hero uses the real campus photo, a live stats strip and the 9 official school logos.
  - **Chat:** live agent steps, a verdict badge, a "What was checked" card, and citation chips that open a **source drawer** with the exact passage and the original PDF at that page.
  - **Programmes and programme detail:** the official eligibility text and the 2026-27 fee table.
  - **Eligibility checker:** the rule engine directly.
  - **Student dashboard:** your courses, attendance bars with the 75% line, CGPA, and quick actions.
  - **Policy library:** shows the version history.
  - **Admin console.**
- **Why React instead of Streamlit:** the blueprint asked for something that looks like a real institutional product. Streamlit can't do custom branding, routing, side drawers or streaming step indicators.

## 8b. Bugs found in testing, and how each was fixed
Each one has a **regression test**, so it can't silently come back.

| Bug | Cause | Fix |
|---|---|---|
| "82% in PCM" → *Does not meet* | "PCM" was treated as a *subject*, so Physics and Maths looked missing | The engine recognises stream averages (PCM, PCB, PCMB) and an overall %. It **does not guess**: it asks for Physics, Maths and the best other subject, then calculates. Meanwhile it gives an honest provisional hint (Best of 3 ≥ PCM average, because Chemistry counts as the third subject) |
| Chemistry = 450 → "Best of 3 = 191.67%, meets criteria" | No input validation | Marks outside 0–100 are rejected with a clear message, in both the engine and the form |
| LLM said Best of 3 = 88% when it was 83.67% | The LLM recomputed the number itself | Code-written verdict line plus a numeric grounding check that regenerates the answer |
| "B.Tech CSE" matched *CSE Global (2+2)* (60%) instead of B.Tech CSE (55%) | Fuzzy matching didn't understand abbreviations | An abbreviation table (CSE, AI, ECE, BA, BSc …) and a preference for regular programmes over Global/partner variants |
| Enrolled students saw "Check Eligibility" in the top bar | One menu for everyone | **Role-based navigation**: applicants see admission tools; students see Dashboard, Academic Rules, Calendar & Exams, Fees; admins see the console |

**Multi-turn flow (tested):**
- User: "Am I eligible for B.Tech CSE with 82% in PCM?" → *More information needed: please share Physics %, Mathematics %, your best other subject*
- User: "Physics 78, Maths 85, Chemistry 83, English 88" → *Meets: Best of 3 = 83.67% (Physics, Mathematics, English) vs 55%*

The second message carries over the programme from the conversation.

## 8c. Evaluation results (13 Nov 2026)
**Test set:** 31 real student questions in students' own words, from r/BennettUniversityGN (including Hinglish, typos, trick and rule-evasion questions), plus 2 JEE-scholarship questions. Expected answers come only from official documents, **never from Reddit replies**. Each answer is scored on four things:
1. **correct facts:** required numbers and terms are present
2. **myth-free:** it doesn't repeat known wrong claims
3. **cited:** it points to official sources
4. **correct behaviour:** answer, ask for details, or decline, as appropriate

| Run | Score | Avg time / answer | What changed |
|---|---|---|---|
| Baseline | 21/29 (72%) | ~45 s | — |
| After fixes 1 | 28/31 (90%) | ~25 s | Crash fixes, admission deadline, hostel rules, out-of-scope, merit bands, faster prompts |
| **Final** | **31/31 (100%)** | **~23 s** | Never-empty answers, all scholarship conditions listed, criteria stated when asking for marks |

**Bugs the evaluation found (each now has a unit test, 28 in total):**
- "60%" / "below 75" crashed the attendance check
- "cse" matched M.Tech instead of B.Tech
- PhD admission dates were used for a general question
- hostel rules weren't applied to "kettle"
- scholarship percentages arrived as text, so nothing was calculated
- an answer came back empty after verification
- JEE was treated as a Class XII subject
- a scholarship question used the login profile's course instead of asking

**Honest limitation:** we used this same set to find and fix bugs, so 100% here overstates real-world accuracy. A fair claim is that the system answers *these kinds* of questions correctly. The next step is a **fresh, unseen set** of questions written by other students, to measure accuracy on questions we never tuned for.

## 9. How to evaluate it (next step)
A gold test set of 30–50 real student questions, with correct answers and source pages (the user is collecting these), will measure:
- **citation hit rate**: did we cite the right document and page?
- **answer correctness and faithfulness**: no claims beyond the sources (RAGAS)
- **refusal correctness**: out-of-scope questions are declined
