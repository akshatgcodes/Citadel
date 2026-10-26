# Deploying Citadel

> **Status:** not deployed yet. Citadel currently runs locally (see [SETUP.md](SETUP.md)).
> Hosting will be chosen once the API (Phase 2) and the chat UI (Phase 4) exist, and this
> guide will then be filled in with the real platform, domain and rollback steps.

---

## What a deployment will need

| Piece | Requirement |
|---|---|
| API | A Python host that can load the embedding model (~130 MB) in memory |
| Database | PostgreSQL with the `pgvector` extension (`VECTOR_STORE=pgvector`) |
| Ingestion | Runs offline with `citadel ingest`, pointed at the production `DATABASE_URL`. The web server never ingests |
| Secrets | `GROQ_API_KEY`, `DATABASE_URL`, set in the host's dashboard, never committed |

On Linux the project installs CPU-only PyTorch (configured in `pyproject.toml`). This keeps the install small enough for typical hosts.

---

## Monitoring & dependencies

- **Dependencies:** Dependabot opens weekly update PRs (Python via `uv`, plus GitHub Actions). Minor and patch updates auto-merge once CI passes. Major updates wait for review.
- **CI:** every push and PR runs a compile check, ruff and pytest (see `.github/workflows/ci.yml`).
- **Report:** a weekly maintenance report is emailed (see `.github/workflows/maintenance-report.yml`).

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
