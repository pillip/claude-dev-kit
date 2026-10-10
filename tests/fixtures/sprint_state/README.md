# ISSUE-076 sprint_state fixtures (frozen real-executor capture)

- `issue_progress_with_h3_subsection.md` — a **byte-identical copy** (sha256
  `8166e829…f840a`) of `docs/sprint_state.archive-2026-10-10-retro.md` as
  committed at `fd322a3`. It is the real file a phase executor wrote while
  closing the ISSUE-066..068 sprint, and it is the file that produced the
  ISSUE-076 false negative live on 2026-10-11:

  ```
  $ python3 scripts/sprint_queue.py validate --action SHIP \
      --targets ISSUE-066,ISSUE-067,ISSUE-068
  {"valid": false, "stuck": ["ISSUE-066","ISSUE-067","ISSUE-068"],
   "errors": ["ISSUE-066: Phase is '0 (6 medium, 8 low)', expected 'shipped'", ...]}
  ```

  The structural feature under test is the `### Review outcomes` h3 subsection
  table (6 columns, same `ISSUE-NNN` first cell) that sits below the 5-column
  `## Issue Progress` table. The pre-fix capture terminated only on an h2, so
  that h3 table's rows were parsed as roster rows and `cells[4]` read the
  "High unresolved" column instead of "Phase".

This fixture is **FROZEN**. It is deliberately a copy rather than a read of the
live doc: the test must keep exercising the real 2026-10-11 writing pattern
even if the archive doc is later edited, moved, or pruned — and conversely, the
test asserts parser behaviour, never the archive's accuracy as a record.
Re-capture only from `git show fd322a3:docs/sprint_state.archive-2026-10-10-retro.md`.
