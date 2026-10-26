# Changelog

All notable changes to **Citadel** are documented here.

---

## [Unreleased]

Work in progress: grounded answer generation with citations and the `POST /ask` API (Phase 2), the evaluation harness (Phase 3), the chat UI (Phase 4).

---

## [0.1.0] — 2026-10-27

### ✨ Added
- Ingestion of PDF and HTML documents from `data/raw/`, with per-document title, date and regulation overrides in `data/manifest.yaml`
- OCR fallback for PDF pages whose text is garbled or missing
- Readable table extraction, with cell text rebuilt from word positions
- Structure-aware chunking: token-sized, never crossing a page or section, with tables kept whole or split by rows with the header repeated
- Embeddings with `bge-small-en-v1.5`, stored in PostgreSQL + pgvector or a local file store
- Hybrid retrieval (vector + BM25 fused with Reciprocal Rank Fusion) with optional cross-encoder re-ranking
- `citadel` command line: `inspect`, `ingest`, `query`

---

[Unreleased]: https://github.com/akshatgcodes/Citadel/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/akshatgcodes/Citadel/releases/tag/v0.1.0

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
