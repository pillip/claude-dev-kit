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

## Running Tests

```bash
python3 -m pytest              # all tests
python3 -m pytest -x           # stop on first failure
python3 -m pytest --tb=short   # shorter tracebacks
```
