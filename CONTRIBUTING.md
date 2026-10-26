# Contributing to Citadel

Thanks for taking the time to contribute! Bug reports, fixes, docs improvements and feature ideas are all welcome.

---

## Before you start

- **Found a bug?** Open a [bug report](../../issues/new?template=bug_report.yml). Search existing issues first.
- **Have an idea?** Open a [feature request](../../issues/new?template=feature_request.yml) before writing code, so we can agree on the approach.
- **Found a security issue?** Don't open a public issue. Follow [SECURITY.md](SECURITY.md).
- Small fixes (typos, docs, obvious bugs) can go straight to a pull request.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Local setup

Full instructions are in [docs/SETUP.md](docs/SETUP.md). Short version:

```bash
git clone https://github.com/<your-username>/Citadel   # your fork
cd Citadel
uv sync
cp .env.example .env
uv run citadel inspect
```

---

## Workflow

1. **Fork** the repo and create a branch from `main`:

   | Branch prefix | Use for |
   |---|---|
   | `feat/` | new feature, e.g. `feat/export-pdf` |
   | `fix/` | bug fix, e.g. `fix/login-redirect` |
   | `docs/` | documentation only |
   | `chore/` | tooling, config, dependencies |
   | `refactor/` | code change with no behaviour change |

2. **Make your change.** Keep it focused, one feature or fix per PR.
3. **Check it locally** before pushing:

   ```bash
   uv run ruff check . && uv run mypy backend && uv run pytest
   ```

4. **Open a pull request** against `main`. The PR template will guide you.

---

## Commit messages

Commits follow an emoji-prefixed format:

```
<emoji> [#issue] [scope:] <message in present tense, lowercase>
```

| Emoji | Type | Example |
|---|---|---|
| ✨ | New feature | `✨ #12 add csv export` |
| 🐛 | Bug fix | `🐛 auth: fix redirect loop on logout` |
| 🎊 | Improvement | `🎊 speed up dashboard load` |
| ♻️ | Refactor | `♻️ extract scoring into its own module` |
| 📚 | Docs | `📚 add deploy guide` |
| 🧪 | Tests | `🧪 cover empty-state api response` |
| 🔨 | Chore / config | `🔨 bump node to 22 in ci` |
| 👆 | Dependency update | `👆 upgrade next to 16.1` |
| 🔒 | Security | `🔒 validate webhook signature` |
| 💀 | Code deletion | `💀 remove unused legacy route` |

Breaking changes add a line `🚨 BREAKING CHANGE: <what breaks>` in the commit body.

---

## Code style

- Run the formatter/linter before committing. CI runs the same checks.
- Follow the existing file structure and patterns.
- Python: snake_case modules and functions, type hints and a docstring on every public function. `ruff format` for formatting.
- New retrieval or chunking behaviour needs a test in `tests/` that runs without models or a database (use `InMemoryStore` and a fake embedder, as `tests/test_retrieval.py` does).
- No secrets in code. Use env vars and add new ones to `.env.example`.
- Update docs when behaviour, setup or env vars change.

---

## Pull request checklist

- [ ] Branch is up to date with `main`
- [ ] Lint, typecheck and tests pass locally
- [ ] Commits follow the format above
- [ ] Docs / `.env.example` / `CHANGELOG.md` updated if needed
- [ ] PR description explains **what** and **why**

PRs are reviewed as soon as possible. Feedback is about the code, never the person.

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
