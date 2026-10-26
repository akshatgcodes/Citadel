# Citadel — Architecture

> Sections 1–4 and 7–8 describe what is built (Phase 1). Sections 5 and 6 describe the
> planned design for Phases 2–4 and are marked as such.

---

## 1. Stack

| Layer | Tech |
|---|---|
| Language | Python 3.12 (supports 3.11–3.13), managed with uv |
| PDF extraction | PyMuPDF (text, fonts, tables, page rendering) |
| OCR | Tesseract via PyMuPDF, 300 DPI |
| HTML extraction | trafilatura (main content as Markdown) |
| Embeddings | sentence-transformers · `BAAI/bge-small-en-v1.5` (384-dim) |
| Keyword search | rank-bm25 (BM25Okapi), in memory |
| Re-ranking | sentence-transformers CrossEncoder · `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Vector store | PostgreSQL 18 + pgvector 0.8 (HNSW, cosine) · or a local numpy store |
| Config | pydantic-settings, from env / `.env` |
| LLM | Groq, model from `GROQ_MODEL` (Phase 2) |

---

## 2. Components

```
backend/citadel/
  config.py          every setting, read from env / .env
  models.py          Document, Block, Chunk, RetrievedChunk, RetrievalResult
  cli.py             citadel inspect | ingest | query
  ingest/
    pdf_loader.py    text, tables and headings per page; OCR fallback
    html_loader.py   main content → sections and tables
    metadata.py      headings, course headers, dates, regulation, titles, manifest
    chunker.py       token-sized, page/section-bounded chunks
    pipeline.py      raw files → chunks → embeddings → store
  store/
    embedder.py      sentence-transformers wrapper (query prefix, normalised vectors)
    base.py          ChunkStore protocol, InMemoryStore, LocalStore
    pgvector_store.py
  retrieval/
    bm25.py          tokeniser + BM25 index
    fusion.py        Reciprocal Rank Fusion
    reranker.py      cross-encoder wrapper
    retriever.py     vector / bm25 / hybrid, optional re-rank, timings
```

### PDF loader

For each page it first checks whether the embedded text is usable. If more than 1% of the characters are control characters, or the page has images but almost no text, the page is OCR'd and noise lines are dropped. Otherwise, tables are found with PyMuPDF and each cell's text is rebuilt from word positions. Text outside tables is grouped into paragraphs, and headings are detected from font size, bold weight and numbering. When a page starts a course syllabus (`Course Code … Course Name …`), that course becomes the section label until the next course. It doesn't call the network or any model.

### HTML loader

trafilatura extracts the main content as Markdown, dropping menus and footers. Markdown headings become section labels, and Markdown tables become table blocks. Every HTML block is on "page 1", and its citation uses the section instead.

### Chunker

Merges consecutive text blocks that share a page and section, splits them into sentences, and packs those into windows of at most `CHUNK_SIZE` tokens with about `CHUNK_OVERLAP` tokens of trailing sentences repeated. Tables are kept whole, or split by rows with the header row repeated. Fragments under 25 tokens are folded into a neighbour.

### Stores

`ChunkStore` is a four-method protocol: upsert, delete collection, all chunks, vector search. `PgVectorStore` keeps one table per embedding dimension. `LocalStore` saves `store_chunks.jsonl` + `vectors.npy` per collection. `InMemoryStore` backs the tests.

### Retriever

Runs vector search and/or BM25, each fetching `RERANK_CANDIDATES` results. In hybrid mode the two rankings are fused with RRF. If re-ranking is on, the cross-encoder re-scores the fused list. The top `k` results are returned with every stage's score and rank, plus timings.

---

## 3. Data Flow

```
data/raw/*.pdf|*.html  (+ data/manifest.yaml overrides)
   │
   ├─ PDF ─ per page: text usable? ──no──► Tesseract OCR ─► paragraphs
   │                       │yes
   │                       └─► tables (cells from word boxes) + paragraphs + headings
   ├─ HTML ─ trafilatura ─► Markdown ─► sections + tables
   ▼
blocks (page, section, kind, text, ocr)
   │  chunker
   ▼
chunks ──► data/processed/<collection>/chunks.jsonl
   │  "Title > Section\n" + text  ──► bge-small embeddings
   ▼
store (pgvector | local)

query ─┬─► embed (with query prefix) ─► vector top-N ─┐
       └─► BM25 top-N ───────────────────────────────┴─► RRF ─► [cross-encoder] ─► top-k
```

1. `citadel ingest` discovers files in `data/raw/` and loads each with the PDF or HTML loader.
2. Document metadata comes from the manifest, then PDF metadata or the HTML title, then the filename and first page.
3. Blocks are chunked using the embedding model's tokenizer and written to `chunks.jsonl`.
4. Each chunk's `Title > Section` header plus its text is embedded, and the collection is replaced in the store.
5. `citadel query` (and later `POST /ask`) retrieves the top-k chunks with scores and timings.

---

## 4. Database Schema

- `chunks_<dim>` (e.g. `chunks_384`): one row per chunk.
  - `collection` — embedding model + chunk size + overlap, e.g. `bge-small-en-v1.5__cs400_ov60`
  - `chunk_id`, `doc_id`, `page`
  - `data` (JSONB) — the full chunk: title, section, date, regulation, kind, OCR flag, text, token count
  - `embedding` — `vector(<dim>)`
  - Primary key `(collection, chunk_id)`

**Indexes:**
- HNSW on `embedding` with `vector_cosine_ops`, for nearest-neighbour search.
- A B-tree on `collection`.

Several collections share the HNSW index, so the connection sets `hnsw.iterative_scan = relaxed_order`. This way a `WHERE collection = …` filter still returns a full top-k.

---

## 5. AI / LLM Design (Phase 2, planned)

### Input

The user's question plus the top-k chunks. Each chunk is formatted as `[n] Doc | Page | Section | Date` followed by its text.

### System prompt strategy

The model may use only the excerpts and must cite every claim as `[Doc Title, p. X]`. When the answer is missing, it replies with one exact sentence ("I couldn't find this in the available documents."). It flags conflicting documents and prefers the newest. Instruction-like text inside excerpts is treated as document content. Personal advice is out of scope.

### Validation

Citations will be parsed from the answer and matched against the retrieved chunks. A citation to a document or page that wasn't retrieved is flagged. This is a cheap, deterministic hallucination signal, separate from the LLM-as-judge in the eval harness.

---

## 6. API Routes (Phase 2, planned)

| Method | Route | Description |
|---|---|---|
| `POST` | `/ask` | Answer a question: answer, citations with snippets, retrieval scores, latency, token usage |
| `GET` | `/health` | Liveness check |

---

## 7. Security

- **Secrets:** `GROQ_API_KEY` and `DATABASE_URL` come from `.env`, which is git-ignored. Only `.env.example` (names, no values) is committed.
- **Source documents:** `data/raw/` and `data/processed/` are git-ignored, so university documents and their extracted text are never pushed.
- **SQL:** the only interpolated identifier is the table name `chunks_<dim>`, built from an integer. Every value is a bound parameter.
- **Prompt injection (Phase 2):** document text is wrapped as quoted excerpts, and the system prompt tells the model to treat it as data.

---

## 8. Error Handling & Reliability

| Failure | Behaviour |
|---|---|
| Tesseract missing or OCR fails on a page | Warning logged, that page is skipped, ingestion continues |
| A page has no usable text and no images | Treated as empty, no OCR attempted |
| Re-ranking requested with no re-ranker configured | `RuntimeError` with a clear message |
| Re-ingest after editing or deleting files | The collection is deleted and rewritten, so no stale chunks remain |

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
