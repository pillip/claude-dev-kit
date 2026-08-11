# Minimality review (over-engineering axis)

PR #73 (ISSUE-045) — TESTS-ONLY (742 test lines + 161-line fixture).

Reviewed for unnecessary complexity only (correctness handled in code-review.md).
This axis never overrides test coverage/correctness.

Assessment:
- `_png_bytes` (test_figma_verify_family.py:54-66) is a stdlib-only PNG encoder.
  It looks like a candidate for `stdlib`/`native` (use Pillow), but it is
  load-bearing: the tests must run without Pillow (this repo's `.venv` has none),
  and the module under test has an explicit no-Pillow fallback. Keep.
- `design_data` module-scoped fixture is shared across ~20 tests — no duplication.
- Helpers `_write_skill`, `_shots`, `_chunk` each have >1 caller — no YAGNI.
- No dead code, no speculative abstraction, no single-caller indirection, no
  reinvented stdlib, no redundant fixtures. Assertions are one behavior each.

Lean already. Ship.
