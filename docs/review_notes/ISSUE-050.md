# Review Notes — PR #79

## Code Review
_Source: reviewer-degraded_

- **[Low] Effort test silently skips validation when frontmatter effort is absent (hollow-pass vector)**
  Evidence: tests/test_readme_consistency.py test_agents_table_effort_match_frontmatter: `if fm_effort and fm_effort != row['effort']` — the leading `fm_effort and` means an agent that loses its effort line goes unvalidated. The Tools test correctly has no such guard. Latent today because test_agent_effort.py guarantees every agent declares effort.
  Fix: Drop the `fm_effort and` guard; compare unconditionally so a future agent missing effort fails loud, consistent with the Tools test.

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

- **[Low] [shrink] _agent_table_names() re-walks the table that _agent_table_rows() already walks**
  Evidence: tests/test_readme_consistency.py _agent_table_names and _agent_table_rows both locate the header, skip the separator, and iterate rows.
  Fix: Reduce _agent_table_names to set(_agent_table_rows()). ~12 removable lines.
