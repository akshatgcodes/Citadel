# Local Setup — Citadel

> There is no live demo yet. This guide is for running Citadel locally.

---

## Prerequisites

- Python 3.11–3.13 and [uv](https://docs.astral.sh/uv/) (uv can install Python for you)
- Tesseract, for OCR of scanned or badly encoded PDF pages: `brew install tesseract`
- Optional: PostgreSQL with pgvector (`brew install postgresql@18 pgvector`). Without it, use the local store.

---

## 1. Clone and install

```bash
git clone https://github.com/akshatgcodes/Citadel
cd Citadel
uv sync                     # creates .venv with all dependencies (Python 3.12 via .python-version)
```

The first `ingest` or `query` downloads the embedding model (~130 MB) from Hugging Face. Re-ranking downloads a ~90 MB cross-encoder.

---

## 2. Environment variables

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `VECTOR_STORE` | `pgvector` | `pgvector`, or `local` to keep vectors in `data/processed/` with no database |
| `DATABASE_URL` | `postgresql://localhost:5432/citadel` | Postgres connection string (only for `pgvector`) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `400` / `60` | Chunk size and overlap, in tokens |
| `EMBED_MODEL` | `BAAI/bge-small-en-v1.5` | Any sentence-transformers model |
| `RERANK_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder used when re-ranking |
| `TOP_K` / `RETRIEVAL_MODE` / `RERANK` | `5` / `hybrid` / `false` | Retrieval defaults (`vector`, `bm25` or `hybrid`) |
| `GROQ_API_KEY` | – | Phase 2. From [console.groq.com/keys](https://console.groq.com/keys) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Phase 2. Any Groq chat model |

Every field in `backend/citadel/config.py` can be set this way.

---

## 3. Database setup

Skip this if `VECTOR_STORE=local`.

```bash
createdb citadel
```

The `vector` extension, tables and indexes are created automatically on first use.

---

## 4. Add documents and run

Put PDFs and saved web pages (`.html`) in `data/raw/`. Optionally give them short titles, dates or a regulation version in `data/manifest.yaml`. Titles appear in every citation.

```bash
uv run citadel inspect                                   # per file: pages, OCR'd pages, tables, sections
uv run citadel ingest                                    # extract → chunk → embed → store
uv run citadel ingest --chunk-size 256 --overlap 32      # another config, stored side by side
uv run citadel query "What is the appeal process for disciplinary action?"
uv run citadel query "credits for 21CSC202J" --mode bm25 -k 3
uv run citadel query "hours in unit 4 of occupational safety" --rerank
```

Every chunk is written to `data/processed/<collection>/chunks.jsonl` for inspection. A collection is one embedding model + chunk size + overlap, e.g. `bge-small-en-v1.5__cs400_ov60`.

---

## 5. Checks

```bash
uv run pytest               # unit tests, no models or database needed
uv run ruff check .
uv run mypy backend
```

---

## 6. Deploy to production

Not deployed yet. See [DEPLOY.md](DEPLOY.md).

---

## Known local-only limitations

- OCR needs the `tesseract` binary on `PATH`. Without it, garbled or scanned pages are skipped with a warning.
- The first run needs internet access to download models. After that, they are cached in `~/.cache/huggingface`.

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
