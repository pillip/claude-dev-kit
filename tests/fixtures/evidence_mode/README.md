# ISSUE-061 golden section fixtures (frozen pre-merge capture)

Each file lists, one per line, the markdown headings found inside the **first
fenced code block after the `## Output Structure` heading** of an agent file,
extracted with the fence-aware parser in
`tests/test_evidence_mode_consolidation.py`
(`headings_in_output_structure_fence` / `split_evidence_mode_section`).

- `<stem>_greenfield_sections.txt` — captured from `agents/<stem>.md` on
  pre-merge main. The greenfield template is unchanged by SPEC-061, so these
  can be re-derived from the live files at any time with the same parser.
- `<stem>_evidence_sections.txt` — captured from the scan twins
  (`agents/scan-planner.md`, `agents/scan-qa-designer.md`,
  `agents/scan-architect.md`, `agents/scan-data-modeler.md`,
  `agents/scan-analyst.md`) at commit `776ac73`, immediately before the
  ISSUE-061 merge deleted those files. These are **FROZEN**: the oracle no
  longer exists in the tree, so never regenerate them — the retired twins
  restore from git history if a re-capture is ever genuinely needed.
