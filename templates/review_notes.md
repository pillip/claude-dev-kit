# Review Notes

## Code Review

### Findings

<!-- Per finding:
#### [severity] [title]
- **File**: [path:line]
- **Issue**: [what's wrong]
- **Impact**: [why it matters]
- **Fix**: [concrete suggestion]

Severity: Critical | High | Medium | Low
-->

### Summary
- Blocking issues: [count]
- Suggestions: [count]

## Security Findings

### Findings

<!-- Per finding:
#### [severity] [title]
- **Category**: Injection | Auth | Sensitive Data | Input Validation | Dependencies | XSS | Misconfiguration
- **File**: [path:line]
- **Issue**: [what's wrong]
- **Attack vector**: [how it could be exploited]
- **Fix**: [concrete suggestion]
-->

### Summary
- Critical/High: [count]
- Medium/Low: [count]

## Over-Engineering

### Findings

<!-- One line per finding:
[path:line]: [tag] [what to cut] → [replacement]

Tags: delete (dead/speculative) | stdlib (reinvented stdlib) | native (dep doing the platform's job) | yagni (abstraction with one impl) | shrink (same logic, fewer lines)

Minimality axis only — NOT correctness. Never recommend cutting validation, error handling, security, accessibility, or explicitly-requested work.
If nothing to cut, write exactly: Lean already. Ship.
-->

### Summary
- Net removable lines: [count]
