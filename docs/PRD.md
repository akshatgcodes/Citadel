# Citadel — Product Requirements Document

**Status:** Draft (Phase 1 of 5 built)
**Owner:** Akshat Gupta
**One-liner:** Ask questions about your university's regulations, syllabi and circulars, and get answers that cite the exact document and page.

---

## 1. Problem

The rules that decide a student's attendance, exams, credits and discipline are spread across long PDFs and web pages: regulations, a 91-page curriculum, per-course syllabi, and circulars that update earlier rules. Finding one answer means knowing which document to open and reading it page by page. General-purpose chatbots answer confidently from general knowledge about "universities", which is often wrong for a specific institution and gives no source to check.

---

## 2. Goals (v1 / MVP)

1. Ingest PDFs and HTML pages from a folder, including scanned or badly encoded pages and tables, into chunks that keep document title, page, section and date.
2. Retrieve relevant chunks with hybrid search (vector + BM25), configurable top-k and optional re-ranking.
3. Answer only from retrieved chunks, cite every factual claim as `[Doc Title, p. X]`, and say "I couldn't find this in the available documents." when the answer isn't there.
4. Expose `POST /ask` returning the answer, citations with snippet text, retrieval scores, latency and token usage.
5. Provide a chat UI where clicking a citation shows the source snippet.
6. Measure quality with an evaluation harness and report the numbers.

---

## 3. Non-Goals (explicit scope cuts)

- **Personal advice** — Citadel reports what documents say. For consequential decisions (detention, grade appeals, fee disputes) it points the student to the relevant office.
- **Answering from outside knowledge** — even "obviously true" facts are excluded unless a document states them. Being wrong with confidence is worse than saying "not found".
- **User accounts and chat history** — not needed to answer document questions. Deferred until there is a reason to personalise.
- **Automatic crawling of the university website** — documents are added to `data/raw/` by hand, so the corpus is known and the eval set stays valid.

---

## 4. Users

**Primary:** Students who need a quick, sourced answer about an academic rule, course or circular.

**Secondary:** Recruiters and interviewers evaluating this as a portfolio project. They need the design decisions and measured accuracy to be easy to find.

---

## 5. User Stories

1. *As a student,* I ask "what happens if I'm not satisfied with the disciplinary committee's decision?" so that I get the appeal steps with the section they come from.
2. *As a student,* I ask about a course by its code (`21CSC202J`) so that I get that course's details, not a similar course.
3. *As a student,* I click a citation so that I can read the exact passage the answer came from.
4. *As a student,* I ask something the documents don't cover so that I'm told so plainly instead of getting a made-up answer.
5. *As a student,* I ask about a rule that a newer circular changed so that I'm told which version is current and both are cited.
6. *As the maintainer,* I add a new PDF and re-run ingestion so that the system knows about it without code changes.
7. *As the maintainer,* I run the eval harness on two configs so that I can see which one is more accurate, and at what latency and cost.

---

## 6. Functional Requirements

### 6.1 Ingestion

- Load `.pdf`, `.html` and `.htm` files from `data/raw/`.
- Detect pages whose text layer is garbled or missing and OCR them.
- Keep tables readable (row-by-row text), and never split a table that fits in one chunk.
- Chunk with configurable size and overlap, measured in tokens.
- Store per chunk: document title, page, section, date, regulation version.
- Allow per-document title, date and regulation overrides in `data/manifest.yaml`.

### 6.2 Retrieval

- Modes: vector-only, BM25-only, hybrid (RRF).
- Configurable top-k and optional cross-encoder re-ranking.
- Report per-stage scores and timings for every result.

### 6.3 Answer generation (Phase 2)

- Use only the retrieved chunks. Cite every factual claim as `[Doc Title, p. X]`, or `[Doc Title, §Section]` for HTML pages.
- Reply with the exact refusal sentence when the answer isn't in the chunks.
- Point out conflicting documents and prefer the most recent, saying so.
- Treat document text as data, never as instructions.

### 6.4 API and UI (Phases 2 and 4)

- `POST /ask` returns answer, citations (with snippets), retrieval scores, latency and token usage.
- Chat interface with clickable citations that show the source snippet.

### 6.5 Evaluation (Phase 3)

- Test set in `eval/questions.jsonl`: question, expected answer, expected source doc/page. Bootstrapped by script from the documents, then reviewed by hand. About 50 questions, including about 10 unanswerable ones.
- Metrics: hit rate@k and MRR, faithfulness / hallucination rate (LLM-as-judge plus a hand-checked sample), answer correctness, refusal accuracy, p50/p95 latency, cost per query.
- Compare configs (chunk size, k, hybrid vs vector-only, re-ranking on/off) in one table.

---

## 7. Non-Functional Requirements

- **Security:** API keys come from `.env` only and are never committed. Source documents are git-ignored.
- **Cost:** the LLM is called only to answer or to judge, never during ingestion or retrieval.
- **Reproducibility:** each retrieval config is stored as its own collection, so results can be re-run and compared.
- **Portability:** runs without a database (local store) for development, and with PostgreSQL + pgvector when deployed.

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| Retrieval hit rate@k, MRR | Measured on the reviewed test set and reported per config |
| Hallucination rate | Measured by LLM-as-judge, with judge agreement checked against a hand-labelled sample |
| Refusal accuracy | Measured on the unanswerable questions |
| Latency p50 / p95, cost per query | Measured and reported per config |

Numeric targets will be set after the first baseline run, so they reflect the real corpus rather than guesses.

---

## 9. Risks & Open Questions

- **OCR noise** — OCR'd tables misread codes (`21CSC204J` → `21C0SC204J`), which hurts exact lookups on those pages.
- **Optimistic eval** — questions generated from chunks reuse the chunks' wording, which flatters BM25. Mitigated by paraphrased generation, manual review and some hand-written questions.
- **Free-tier rate limits** — Groq limits could slow full eval runs. Mitigated by caching LLM responses.
- **Open question** — where the API will be hosted, and whether the database stays local or moves to a managed Postgres.

---

## 10. v2 Candidates

- Layout-aware table extraction for the pages OCR handles badly.
- Metadata filters in the UI (regulation version, document type, date).
- Scheduled ingestion of new circulars from the university website.

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
