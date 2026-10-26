# Engineering Decisions — Citadel

---

## Decision 1 — Hybrid retrieval fused with Reciprocal Rank Fusion

**Context:** Student questions mix paraphrase ("can I appeal the decision?") with exact tokens (course codes like `21CSC202J`, clause numbers, "75%"). Embeddings handle the first and blur the second, and BM25 does the opposite.

**Decision:** Run both and fuse the rankings with RRF: `score = Σ 1 / (60 + rank)`.

**Reason:** Cosine similarity (0–1) and BM25 (unbounded) aren't comparable, so a weighted sum needs normalisation that shifts with every query. RRF uses ranks only, has one standard constant, and rewards chunks that both methods rank highly.

**Tradeoff:** It ignores how much better the top result is than the second one. A very confident single-method hit can be outranked by a chunk that both methods rank moderately.

---

## Decision 2 — Real BM25 in memory, not Postgres full-text search

**Context:** Postgres has built-in full-text search, which would keep everything in one query.

**Decision:** Build a `rank_bm25` index in memory from the stored chunks at startup.

**Reason:** `ts_rank` is not BM25: it has no IDF weighting or document-length normalisation, which are the parts that make keyword ranking good. The corpus is a few thousand chunks, so building the index takes milliseconds.

**Tradeoff:** The index lives in each process and must be rebuilt after ingestion. It would not scale to millions of chunks without moving to a search engine.

---

## Decision 3 — `BAAI/bge-small-en-v1.5` for embeddings

**Context:** The embedding model has to run on a laptop CPU during ingestion and at query time.

**Decision:** bge-small (384 dimensions, ~33M parameters), configurable through `EMBED_MODEL`.

**Reason:** It is among the strongest small models on the MTEB retrieval benchmark and clearly ahead of the older `all-MiniLM-L6-v2`. Its query instruction prefix improves short-question retrieval, and it embeds the whole sample corpus in about a minute on CPU.

**Tradeoff:** Larger models such as `bge-base` usually retrieve better at roughly 3× the cost. That comparison is a planned experiment rather than an assumption.

---

## Decision 4 — pgvector, with a local store behind the same interface

**Context:** The choice was between a dedicated vector database (Chroma) and Postgres with pgvector.

**Decision:** pgvector as the production store. A file-backed `LocalStore` and an `InMemoryStore` implement the same four-method `ChunkStore` protocol.

**Reason:**
- Vectors, metadata and filters live in one database that deploys to any managed Postgres.
- The local store means development and experiments don't need a database, and tests need neither models nor a database.
- Collections for different configs share one table per embedding dimension. Because of that, pgvector's iterative index scan is enabled so a collection filter still returns a full top-k.

**Tradeoff:** Two store implementations to keep in sync. The protocol is deliberately small to limit that.

---

## Decision 5 — Chunks never cross a page or a section

**Context:** Answers must cite `[Doc, p. X]`, and the eval harness checks retrieval by expected page.

**Decision:** Chunks are packed within one page and one section only. Size is counted in tokens of the embedding model's own tokenizer, with sentence-level overlap.

**Reason:**
- Every chunk has exactly one page to cite, and its section label is accurate.
- Token counting matches what the model actually truncates at 512, unlike counting characters.

**Tradeoff:** A sentence that runs across a page break is split, and short sections produce small chunks. Fragments under 25 tokens are folded into a neighbour to limit the second problem.

---

## Decision 6 — Detect and OCR garbled pages instead of trusting the text layer

**Context:** Nine pages of the real CSE curriculum PDF look normal on screen, but their text extracts as control characters because of broken font encodings.

**Decision:** Pages where more than 1% of characters are control characters, or with images but no text, are OCR'd with Tesseract. Lines without a word of three or more letters are dropped as noise.

**Reason:** Without the check, those pages would be indexed as noise and silently never retrieved. OCR recovers the actual content: course outcomes, units, mission statements.

**Tradeoff:** OCR is slower (about 1–3 s per page) and noisy on tables. It read `21CSC204J` as `21C0SC204J`, which hurts exact-code lookups on those pages.

---

## Decision 7 — Rebuild table cells from word positions

**Context:** PyMuPDF's built-in table text drops spaces on these PDFs ("OccupationalSafetyandDisasterManagement"), and syllabi are essentially one large table per page.

**Decision:** Use PyMuPDF to find the table grid, but rebuild each cell's text from the words whose centres fall inside it. Rows are written as `cell | cell | cell`, collapsing merged cells. Large tables are split by rows, with the header row repeated in each piece.

**Reason:** Glued words destroy both BM25 matching and embedding quality. Repeating the header row means every piece of a split table still says what its columns are.

**Tradeoff:** Table layout is flattened to text. Very wide grids such as course-outcome matrices remain hard to read.

---

## Decision 8 — Dates only from trustworthy sources

**Context:** Answers should prefer the newest document when two disagree, which needs dates.

**Decision:** Dates come from `data/manifest.yaml`, then the filename, then the first page. PDF creation dates are never used.

**Reason:** The 2026-27 syllabus in the sample corpus has a 2022 creation date. A missing date is safer than a wrong one, because a wrong date would make the model confidently pick the outdated rule.

**Tradeoff:** Many documents end up with no date unless one is added to the manifest.

---

## What I'd do differently in v2

- **Layout-aware table extraction:** the worst OCR pages would be better handled by a layout model than by plain Tesseract output.
- **Chunks that can span a page break:** use a page range with a primary page, so sentences at page breaks stay whole while citations stay exact.

---

## Explicit non-decisions (deferred to v2)

| Feature | Why deferred |
|---|---|
| Incremental ingestion | Re-ingesting a few documents takes about a minute and guarantees no stale chunks. Worth it only at a larger corpus size |
| Automatic crawling of the university site | A hand-curated corpus keeps the eval set valid and avoids indexing irrelevant pages |
| User accounts / chat history | Not needed to answer document questions |

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
