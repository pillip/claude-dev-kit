# Contributing to claude-kit

Thanks for your interest in contributing!

## Getting Started

1. Fork the repo and clone it
2. Run the test suite to verify your setup:
   ```bash
   python3 -m pytest
   ```

## Branch Strategy

- `main` is the default branch
- Create feature branches: `feature/<description>`
- Hotfixes: `hotfix/<description>`

## Commit Conventions

- Format: `type(scope): subject`
- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`
- Example: `feat(sprint): add pipeline drain validation`

## Pull Request Process

1. Create a feature branch from `main`
2. Make changes with tests
3. Run `python3 -m pytest` and ensure all tests pass
4. Run `python3 scripts/gen_skills.py --dry-run` to verify skill templates are up to date
5. Open a PR with a clear title and description
6. Wait for CI checks to pass

## Code Style

- Follow the project's existing conventions
- Python: formatted with ruff
- JS/TS: formatted with prettier (if applicable)
- Keep PRs focused: one issue = one PR

## Adding a New Agent

1. Create `agents/<name>.md` with frontmatter (name, description, tools, model)
2. Update `README.md` agent table if needed

## Adding a New Skill

1. Create `skills/<name>/SKILL.md.tmpl` with frontmatter and `{{PREAMBLE}}` token
2. Run `python3 scripts/gen_skills.py` to generate `SKILL.md`
3. Never edit `SKILL.md` directly -- always edit the `.tmpl` file

## Marking Tech Debt (KIT-DEBT)

When you intentionally defer a simplification or take a shortcut, mark it inline so it
becomes a *tracked* obligation instead of silent rot. Every marker must carry a
**ceiling** (the constraint that makes the shortcut acceptable today) and an
**upgrade trigger** (the condition that forces a revisit):

```python
# KIT-DEBT(ceiling=<=100 items, trigger=list grows unbounded or p95 > 50ms): linear scan; fine at current scale
```
```js
// KIT-DEBT(ceiling=single region, trigger=multi-region rollout): hardcoded endpoint
```

- A marker **without** `trigger=` is flagged `no-trigger` ("later means never") — avoid it.
- Harvest the ledger any time with `python3 scripts/debt_harvest.py` (use `--json` for tooling).
- `/review` runs this as a non-blocking advisory phase and surfaces no-trigger markers in the review notes.

## Running Tests

Install the dev extras first so optional test dependencies (e.g. PyYAML, used by
the pack-manifest tests) are present — otherwise those tests **skip** with a reason:

```bash
pip install -e '.[dev]'        # or: uv sync
```

```bash
python3 -m pytest              # all tests
python3 -m pytest -x           # stop on first failure
python3 -m pytest --tb=short   # shorter tracebacks
```
