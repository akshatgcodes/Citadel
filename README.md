<p align="center">
  <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24"
       fill="none" stroke="#4c6ef5" stroke-width="1.5"
       stroke-linecap="round" stroke-linejoin="round">
    <path d="M10 5V3"/>
    <path d="M14 5V3"/>
    <path d="M15 21v-3a3 3 0 0 0-6 0v3"/>
    <path d="M18 3v8"/>
    <path d="M18 5H6"/>
    <path d="M22 11H2"/>
    <path d="M22 9v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9"/>
    <path d="M6 3v8"/>
  </svg>
</p>

<h1 align="center">Citadel</h1>

<p align="center">
  <strong>Ask questions about your university's regulations, syllabi and circulars, and get answers that cite the exact document and page.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/status-in_progress-4c6ef5?style=flat-square" alt="Status: in progress">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/pgvector-336791?style=flat-square" alt="pgvector">
  <img src="https://img.shields.io/badge/Hugging_Face-FFD21E?style=flat-square&logo=huggingface&logoColor=black" alt="Hugging Face">
  <img src="https://img.shields.io/badge/license-GPL--3.0-4c6ef5?style=flat-square" alt="License">
</p>

---

## What is Citadel?

University rules live in long PDFs: regulations, 90-page curricula, scanned circulars that quietly replace last year's rule. Citadel is a retrieval-augmented generation (RAG) system that answers student questions **only** from those documents, cites every claim as `[Doc, p. X]`, and says "I couldn't find this" instead of guessing. It ships with an evaluation harness, so its accuracy is a measured number rather than a claim.

> **Status:** Phase 1 of 5 is done (ingestion + hybrid retrieval). Answer generation, the API, the eval harness and the chat UI are in progress. See the [roadmap](#roadmap).

---

## What you get

- **Messy PDFs handled** — pages with broken font encodings or scans are detected and OCR'd, syllabus tables are rebuilt cell by cell, and saved web pages are stripped down to their main content.
- **Hybrid search** — embeddings find paraphrases ("can I appeal?"), BM25 finds exact tokens (`21CSC202J`, "75%"), and Reciprocal Rank Fusion merges the two. An optional cross-encoder re-ranks the top results.
- **Citable chunks** — every chunk keeps its document title, page, section, date and regulation version, so answers can point to a precise source.
- **Built to be measured** — every embedding model + chunking config is stored side by side, so experiments can compare them on the same questions.

---

## Stack

| Layer | Tech |
|---|---|
| Ingestion | PyMuPDF · Tesseract OCR · trafilatura |
| Retrieval | sentence-transformers (`bge-small-en-v1.5`) · rank-bm25 · cross-encoder re-ranker |
| Database | PostgreSQL + pgvector (HNSW) · local numpy store for running without a database |
| AI | Groq, model set by env var (Phase 2) |
| Tooling | uv · pytest · ruff · mypy · GitHub Actions |

---

## Engineering Decisions

**Why hybrid search instead of embeddings alone?**
Embeddings blur exact tokens: a query for course `21CSC202J` can match any course page. BM25 nails those tokens but misses paraphrases. Fusing them by rank (RRF) avoids comparing their incompatible score scales and needs no weights to tune.

**Why do chunks never cross a page?**
So every chunk has exactly one page to cite and citations can be checked automatically. The cost is an occasional sentence split at a page break.

**Why detect "garbled" pages instead of trusting the PDF's text layer?**
Nine pages of the real CSE curriculum display correctly but extract as control characters. Without the check they would be silently indexed as noise. They're now detected by their share of control characters and OCR'd.

**What would you do differently in v2?**
Use a layout-aware model for tables instead of OCR on the worst pages: OCR reads course code `21CSC204J` as `21C0SC204J`, which breaks exact-code lookups on those pages.

More in [docs/DECISIONS.md](docs/DECISIONS.md).

---

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Ingestion, chunking, hybrid retrieval, re-ranking | ✅ Done |
| 2 | Grounded answers with citations (Groq) · FastAPI `POST /ask` | ⏳ Next |
| 3 | Eval harness: hit rate@k, MRR, faithfulness, correctness, refusals, latency, cost | ⏳ |
| 4 | React chat UI with clickable citations | ⏳ |
| 5 | Config experiments + written report with measured numbers | ⏳ |

---

## Docs

| Document | Description |
|---|---|
| [PRD](docs/PRD.md) | Product requirements — goals, user stories, non-goals |
| [Architecture](docs/ARCHITECTURE.md) | System design, data flow, component breakdown |
| [Decisions](docs/DECISIONS.md) | Every major technical decision and why |
| [Setup](docs/SETUP.md) | Local dev setup and env vars |
| [Deploy](docs/DEPLOY.md) | Deployment status and plan |
| [Contributing](CONTRIBUTING.md) | How to propose changes |
| [Changelog](CHANGELOG.md) | What changed in each release |
| [Security](SECURITY.md) | How to report a vulnerability |

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
