# Over-Engineering / Minimality axis — PR #68 / ISSUE-043

Lean already. Ship.

The 120-line / 5-case guard is proportionate: it maps 1:1 to the 3 ACs plus 2 hygiene invariants, each catching a distinct future regression (re-add, re-wire, tracked artifact, missing ignore, over-broad ignore). The hand-rolled _iter_files rglob scan and substring match are self-contained and portable — not worth replacing with git grep. The 19-line module docstring is load-bearing (documents the .sh-extension rationale that prevents a maintainer from "simplifying" BANNED into a find_kit_root false-positive). No removable lines.
