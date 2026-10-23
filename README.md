# Citadel

Retrieval-augmented question answering over a university's academic documents
(regulations, syllabi, circulars), with cited sources and an evaluation harness that
measures retrieval quality, faithfulness, correctness, refusals, latency and cost.

> **Status:** Phase 1 (ingestion + retrieval) done. Next: Phase 2 (answer generation + API),
> Phase 3 (eval harness), Phase 4 (React UI), Phase 5 (experiments + report).

## How it works

```
data/raw/*.pdf|*.html
   │  PyMuPDF (text, fonts, tables) ─ Tesseract OCR for garbled/scanned pages
   │  trafilatura (HTML main content → sections)
   ▼
blocks (page, section, text|table)
   │  structure-aware chunker (token-sized, page/section-bounded, tables kept whole)
   ▼
chunks + metadata (doc title, page, section, date, regulation)
   │  bge-small-en-v1.5 embeddings
   ▼
pgvector (or local numpy store)          in-memory BM25 index
          └──────────── RRF fusion ────────────┘
                          │ optional cross-encoder re-rank
                          ▼
                    top-k chunks → (Phase 2) LLM answer with [Doc, p. X] citations
```

## Setup

Requirements: Python 3.11–3.13 (managed by [uv](https://docs.astral.sh/uv/)), Tesseract
for OCR, and optionally PostgreSQL with pgvector.

```bash
brew install tesseract            # OCR for scanned / broken-font PDF pages
brew install pgvector             # only if using Postgres
uv sync                           # creates .venv with all dependencies
cp .env.example .env              # then edit
```

Storage backend (`VECTOR_STORE` in `.env`):

- `local`: vectors saved as numpy files under `data/processed/`. No database needed.
- `pgvector`: set `DATABASE_URL`, then `createdb citadel`. The extension and tables are
  created on first use.

## Usage

Put PDFs / saved HTML pages in `data/raw/`. Optionally give documents short titles or
dates in `data/manifest.yaml` (titles appear in every citation).

```bash
uv run citadel inspect                      # what extraction finds: pages, OCR, tables, sections
uv run citadel ingest                       # extract → chunk → embed → store
uv run citadel ingest --chunk-size 256 --overlap 32   # another config, stored side by side
uv run citadel query "What is the appeal process for disciplinary action?"
uv run citadel query "credits for 21CSC202J" --mode bm25 -k 3
uv run citadel query "hours in unit 4 of occupational safety" --rerank
uv run pytest                               # unit tests (no models or database needed)
```

`data/processed/<collection>/chunks.jsonl` holds every chunk for inspection. A
*collection* is one embedding model + chunk size + overlap, e.g.
`bge-small-en-v1.5__cs400_ov60`.

## Project layout

```
backend/citadel/
  config.py            all settings, from env / .env
  models.py            Document, Block, Chunk, RetrievedChunk
  cli.py               citadel inspect | ingest | query
  ingest/              pdf_loader, html_loader, metadata, chunker, pipeline
  store/               embedder, base (protocol + in-memory/local), pgvector_store
  retrieval/           bm25, fusion (RRF), reranker, retriever
tests/                 chunking, metadata and retrieval tests
data/raw/              source documents (git-ignored)
data/manifest.yaml     optional per-document title/date/regulation overrides
```

## Design decisions

**FastAPI over Flask** (Phase 2). The `/ask` response is a typed contract (answer,
citations, scores, latency, token usage). Pydantic models give validation and OpenAPI docs
for free, and async suits waiting on the LLM API.

**pgvector over Chroma.** Vectors, metadata and filters live in one Postgres database that
deploys anywhere (e.g. Neon). Collections for different experiment configs share one table
per embedding dimension. Because several collections share an HNSW index, pgvector's
iterative index scan is turned on so a collection filter still returns a full top-k.
A file-backed local store implements the same interface for running without a database.

**`BAAI/bge-small-en-v1.5` embeddings.** 384 dimensions and ~33M parameters, so it is fast
on a laptop CPU. It is among the strongest small models on the MTEB retrieval benchmark,
and clearly ahead of the older `all-MiniLM-L6-v2`. It uses a query instruction prefix
(passages are embedded without one). `bge-base` is a planned experiment arm.

**Hybrid retrieval with Reciprocal Rank Fusion.** Embeddings handle paraphrase ("can I
appeal?" ↔ "if a student is not satisfied with the decision…"). BM25 handles exact tokens
that embeddings blur: course codes like `21CSC202J`, clause numbers, percentages.
Vector cosine scores and BM25 scores aren't on comparable scales, so they are fused by rank:
`score = Σ 1/(60 + rank)`. There are no weights to tune.

**Real BM25, in memory.** Postgres `ts_rank` is not BM25 (no IDF saturation or length
normalisation). With a few thousand chunks, building `rank_bm25` at startup takes
milliseconds.

**Optional cross-encoder re-ranking** (`ms-marco-MiniLM-L-6-v2`). It re-scores the top 20
fused candidates by reading query and passage together. On the sample corpus it moved the
correct chunk from 3rd/4th to 1st in ~160 ms on CPU. Whether that's worth the latency is
measured in Phase 5.

**Chunking rules.**
- Size is counted in tokens of the embedding model's own tokenizer, because the model
  truncates at 512 tokens, not characters.
- Chunks never cross a page boundary, so every chunk has exactly one page to cite. The
  cost is an occasional sentence split at a page break.
- Chunks never cross a section, so the section label is accurate.
- Sentences are packed with ~60 tokens of overlap.
- Tables stay whole when they fit. Larger tables are split by rows, and each piece repeats
  the header row.
- Fragments under 25 tokens (a lone heading, scraps of rotated table headers) are folded
  into a neighbouring chunk.
- Each chunk is embedded with a `Title > Section` header, so "minimum 75%" is still found
  by a query about "attendance".

**Extraction problems handled (found in the real documents):**
- *Broken font encodings.* 9 pages of the CSE curriculum render fine but extract as
  control characters. Pages with >1% control characters are detected and OCR'd, as are
  pages with images but no text (scans).
- *Glued table words.* PyMuPDF's table cell text drops spaces on these PDFs
  ("OccupationalSafetyandDisasterManagement"). Cells are rebuilt from word positions
  instead.
- *Syllabi are one giant table per page.* Rows become `cell | cell` lines, and merged
  cells are de-duplicated. A course header (`Course Code … Course Name …`) sets the
  section for all pages of that syllabus, because sub-headings such as numbered book
  lists are noise.
- *Saved web pages are mostly menus.* trafilatura keeps only the main content.
- *Wrong dates.* PDF creation dates are never used (a 2026-27 syllabus here was "created"
  in 2022). Dates come from the manifest, filename or first page, or are left empty.

**Citations.** PDFs cite the PDF page index (`p. 3`), which is what you type into a PDF
viewer. The page number printed on the page can differ (it is part of a larger book).
HTML pages have no pages, so they cite the section: `[Code of Conduct for Students, §7. APPEAL PROCESS]`.

## Known limitations

- OCR'd tables are noisy (e.g. `21CSC204J` read as `21C0SC204J`), which hurts exact-code
  lookups on those pages. The eval harness will quantify this.
- Heading detection is heuristic. Section labels on unusual layouts may be missing or coarse.
