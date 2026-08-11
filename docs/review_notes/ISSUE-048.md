# Review Notes — PR #77

## Code Review
_Source: reviewer-degraded_

- **[Low] Fallback test exercises only half the empty/detached guard**
  Evidence: tests/test_checkpoint_merge_base.py::test_merge_base_falls_back_when_unresolvable monkeypatches vc._merge_base to None and only asserts isinstance(result,set); it never drives _merge_base to genuinely return None in a real orphan/unrelated-history repo, nor asserts the branch's own file resolves through the base fallback.
  Fix: Add a git checkout --orphan (or unrelated-history) fixture where `git merge-base HEAD main` really returns empty; assert vc._merge_base(...) is None and the branch file still resolves. Reviewer confirmed the fallback works out-of-band.

- **[Low] _existing() 'files' parameter is untyped, breaking the module's annotation convention**
  Evidence: scripts/verify_checkpoint.py _existing(wt_path: str, files) -> set[str] — surrounding helpers are fully typed.
  Fix: Annotate files: Iterable[str] (from collections.abc import Iterable).

## Security Findings
_Source: reviewer-degraded_

_No findings._

## Over-Engineering

_No findings._
