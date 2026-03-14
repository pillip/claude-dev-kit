# Contributing Guide

## Branch Strategy
- `main` is protected — do not push directly
- Create feature branches: `feature/<description>`
- Hotfixes: `hotfix/<description>`

## Commit Conventions
- Format: `type(scope): subject`
- Types: `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`
- Example: `feat(auth): add OAuth2 login flow`

## Pull Request Process
1. Create a feature branch from `main`
2. Make changes with tests
3. Open a PR with a clear title and description
4. PR body must include `Closes #<issue_number>`
5. Wait for CI checks to pass
6. Request review from a team member

## Code Style
- Follow the project's existing conventions
- Run linters before committing
- Keep PRs focused: one issue = one PR
