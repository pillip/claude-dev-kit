# gate_evidence fixtures — provenance

Frozen, unedited `git diff` output from this repository's own history. ISSUE-081's
acceptance criteria require replaying real PR diffs, not hand-written imitations of
them, so these files are committed verbatim. They are **committed** rather than
regenerated at test time because `.github/workflows/ci.yml` uses
`actions/checkout@v4` at its default `fetch-depth: 1`, where none of the SHAs below
are reachable.

Regenerate (from a full clone) with exactly these commands — the output must be
byte-identical:

| Fixture | Command | Resolved SHAs |
|---|---|---|
| `issue_078_pre_fix.diff` | `git diff a4338e2..d328a6c^` | `a4338e28d2bbedb75c5a9b64d5983f4d67e63e66..0d0cae14ed5d1fdeda2c430af2b98a0be63c297c` |
| `issue_078_post_fix.diff` | `git diff a4338e2..d328a6c` | `a4338e28d2bbedb75c5a9b64d5983f4d67e63e66..d328a6c030adf7b247c9823514bf57ab9790d24e` |
| `issue_074_non_gate.diff` | `git diff 404ef8f~1..404ef8f` | `a4338e28d2bbedb75c5a9b64d5983f4d67e63e66..404ef8f9d9bee01ddb1a39d7c8b3693e118b8735` |
| `issue_056_colliding_main.diff` | `git diff 73b9202^..73b9202` | `2cfd8754a3ccd0b331161e56cb1702629901b31a..73b92027e70f98db14922f033d468980b9bc9560` |

## What each fixture is

- **`issue_078_pre_fix.diff`** — PR #133 (ISSUE-078) as it stood **before** its review
  fix: the branch at `0d0cae1`, diffed against its fork point `a4338e2`. It adds the
  gate `sprint_status_is_running` (the arming predicate) plus `check_roster_boundary`
  to `scripts/sprint_queue.py`. The arming predicate is evidenced **only at the
  helper**: `tests/test_sprint_queue_watermark.py` gains value-vocabulary batteries
  (`RUNNING_VALUES`, `RUNNING_LINES`) and a single-case test,
  `test_status_running_outside_meta_is_not_detected_and_is_not_refused`, that records
  the fail-open as intended (`exit_code == 0`, `out["valid"] is True`) on a fixture it
  itself asserts contains `- Status: running`. Measured consequence after merge: exit
  0 / `valid: true` / `state: "not-running"` for 22 of 23 inputs containing the line
  `- Status: running`, while `next-action` on the same bytes returned `PIPELINE` for
  three out-of-scope issues.

- **`issue_078_post_fix.diff`** — the same branch at `d328a6c`, i.e. **with** the
  review fix. Adds `_META_HEADING_MUTATIONS` (8 cases) and
  `TestMetaHeadingMutationsStillArmTheCheck::test_heading_mutation_with_an_absent_field_is_still_refused`,
  a parametrized battery that drives the real consumers (`replay.run` →
  `next-action`, `replay.run_validate` → `validate`) and asserts a constant refusal
  across every variant, guarded for vacuity by
  `assert "- Status: running" in text` plus
  `assert "- Status: running" not in _meta_block(text)`.

- **`issue_074_non_gate.diff`** — PR #132 (ISSUE-074), a real, substantial
  (1122-insertion) PR that adds **no** gate: it reconciles a prose contract across
  `agents/*.md` and `skills/issue/SKILL.md{,.tmpl}` and adds
  `tests/test_registry_lock_contract.py`. Its source half contains no Python at all,
  which is why it is the no-false-positive-tax pin: an ordinary PR must leave the
  review output untouched.

- **`issue_056_colliding_main.diff`** — PR #101 (ISSUE-056), the diff that promoted four
  model-executed verification sweeps to deterministic validators. It is here for one
  measured property that no hand-written diff would be believed for: it adds **six**
  gates across two new scripts, and **two of them are both named `main`** — one in
  `scripts/verify_design_sweeps.py`, one in `scripts/verify_hollow_tests.py`. Keyed on
  the bare symbol, the evidence map collapsed them and yielded **5** records for 6
  gates, so a disarm battery written for one file's `main` satisfied the other's and
  one exemption marker waived both. Every validator script in this repo has a `main`.
  Pinned by `TestEvidenceIsKeyedByPathAndSymbol`.

## Do not edit

Editing a fixture breaks the claim these tests make, which is that the mechanism
separates two **real** diffs that shipped. Tests that need a variant mutate a copy in
memory (see `_mutated_diff` in `tests/test_gate_evidence_contract.py`); the files on
disk stay as git produced them.
