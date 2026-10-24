#!/usr/bin/env python3
"""Require paired evidence for every gate a diff adds (ISSUE-081 / SPEC-081).

"A newly added defence fails OPEN" was measured at High severity in four
consecutive sprints — ISSUE-068/PR #121, ISSUE-076/PR #128, ISSUE-078/PR #133,
ISSUE-072/PR #135. The common shape is a missing **test direction**: every one
tested that its gate FIRES and shipped without a test that it cannot be
DISARMED, or that it holds end to end through the real consumer rather than
only at the helper it was unit-tested against.

This module answers two questions over unified-diff text, with no knowledge of
the repository it came from:

1. **Does this diff add a gate?** A gate is a function in a changed non-test
   source file whose *diff-added* lines contain both a conditional and a
   refusal. The definition deliberately over-detects (SPEC-081); the escape
   hatch is an explicit inline exemption, which is reported rather than
   silently honoured.
2. **Is the gate evidenced in both directions?**
   * ``disarm`` — an added test battery (>= ``MIN_VARIANTS`` input-only
     variants, constant literal expectations) that exercises the gate **and
     asserts a refusal**.
   * ``composite`` — an added battery that asserts a **consumer-level**
     outcome (an exit code / return code / a refusal constant) *in the refusal
     direction under its own operator* and carries an input-side **vacuity
     guard** whose literal is attributable to the gate.

What this module measures, stated exactly (SPEC-081 amendment, decision 1 and
decision 3 — the earlier claim was wider than the code):

* It verifies that **>= MIN_VARIANTS variants exist**, that their
  **parameters feed only the input**, and that **some assertion is
  refusal-shaped**.
* It does **not** verify that the variants are *adversarial-but-plausible*.
  That is semantic, stays the author's judgement, and is only proxied by the
  vacuity guard.
* Direction detection is **lexical and fallible**. Hand-classified on the
  measurement corpus, **16 of 27** ``direction=False`` verdicts were wrong —
  the battery really did assert a refusal, in a form this module cannot read:
  predicate polarity (for a *detector*-shaped gate ``assert detected is True``
  **is** the refusal, and that is not lexically decidable), refusal by
  ``is None``, by an empty collection or verdict string, by probing a
  violation list, or by a finding-kind string. ``any()`` semantics — a gate
  passes when *any* attributed battery is recognised — is what keeps the
  measured false-block rate at 0, not classifier accuracy. The two failure
  modes are therefore reported under **separate** finding kinds
  (``missing-disarm-battery`` vs ``missing-refusal-direction``) because their
  reliability differs enormously, and the second kind's remedy says so and
  names the inline-exemption escape.

Why the vacuity guard carries the attribution: a syntactic checker cannot infer
input *families*, and the two real ISSUE-078 diffs are indistinguishable at
every coarser metric (added blocks referencing the gate 7 vs 8; consumer-driving
blocks 2 vs 2; both already carry consumer-level refusal batteries). The guard
is simultaneously what ties a battery to a gate and what makes the battery
non-vacuous — without it, 8 heading mutations are indistinguishable from 8
copies of a case that already passed.

Usage::

    python3 scripts/verify_gate_evidence.py --diff-file path/to.diff

``--diff-file`` is the ONLY input. A revision-range leg (with its own ``--repo``
and a hard-coded git timeout) and a machine-readable mode were deleted by
SPEC-081's 2026-10-14 amendment, decision 5. The range leg had zero callers and
zero tests, the two-dot semantics this docstring used to advertise PROVABLY
disagreed with the real consumer's merge-base diff (on a branch where the
default branch deleted a gate after the fork point: two-dot ``exit=1 FAIL`` vs
merge-base ``exit=0 PASS``), and its timeout constant carried an untrue
provenance comment. The machine-readable mode's only consumer was the test
written for it, and no acceptance criterion names one. The real consumer is
``verify_checkpoint._gate_evidence_diff``, which computes its own diff with the
merge-base correction the deleted leg lacked.

Exit code, after the TIER SPLIT (SPEC-081 amendment 2026-10-24, decision 6):
the three finding kinds no longer carry the same weight, and ``BLOCKING_KINDS``
below is the single place that says which do.

* **1** when an added gate carries a BLOCKING finding —
  ``missing-disarm-battery``, i.e. no added test battery is attributed to the
  gate at all. That property is decidable from the diff text alone, so it is an
  exit code.
* **0** when the diff adds no gate, when every added gate is evidenced or
  exempted, **and also** when the only findings are ADVISORY —
  ``missing-refusal-direction`` and ``missing-composite-pin``, both of which
  rest on assertion polarity. They are still printed, under their own heading,
  because a demotion that is silent is worse than no demotion; they just do not
  fail the phase. Decision 8 records the residual without softening it: an
  author who writes only arm-direction tests produces an *attributed* battery
  and is therefore surfaced here, not blocked.
* **2** on a REFUSAL TO EVALUATE, which is deliberately a different code from
  the **1** a blocking finding produces. It covers a usage error, a
  ``--diff-file`` whose decoded text holds no ``+++ `` header at all (a PASS
  over unreadable bytes renders byte-identically to a PASS over a clean diff —
  measured: a UTF-16 file printed the gate-free verdict and exited 0), and an
  analysis that blew its wall-clock budget (``AnalysisTimeout``, below).

The PHASE is unchanged: ``("review", "gate-evidence")`` stays out of
``verify_checkpoint.ADVISORY_PHASES``, so this is not the blanket Option G the
2026-10-14 amendment rejected — the obligation remains a non-zero exit for the
decidable property.

The diff text may be in any rendering the real tools produce: git's DEFAULT
C-quoted path for a non-ASCII filename (``+++ "b/scripts/gat\\303\\251.py"``),
``diff.mnemonicPrefix``'s ``i/``/``w/`` prefixes, and plain ``diff -u``'s
TAB-plus-timestamp field. Two bounds keep one added line from parking this
blocking gate — ``_TERNARY_GAP`` and ``_MAX_SCAN_CHARS``, both documented at
their definitions, including the one detection blind spot the second accepts.

Environment knob (SPEC-081 amendment 2026-10-24, AC-9.2):

* ``KIT_GATE_EVIDENCE_TIMEOUT`` — seconds `analyze` may spend before it
  REFUSES rather than finishing. Default ``60``
  (`DEFAULT_TIMEOUT_SECONDS`); unset, non-numeric, zero and negative values
  fall back to that default without crashing, exactly as
  ``KIT_CHECKPOINT_TEST_TIMEOUT`` and ``KIT_SPRINT_QUEUE_GH_TIMEOUT`` do.
  Past the bound `analyze` raises `AnalysisTimeout` and both consumers fail
  CLOSED — the CLI at exit 2, ``verify_checkpoint`` at ``False`` — because a
  half-finished analysis is not a pass. The bound exists because
  ``scripts/checkpoint.sh`` ``exec``s python3 with no timeout and the sprint
  runner's watchdog is 600 s, so an unbounded blocking gate is hangable by
  its own subject. The quadratic that made that reachable is gone too (see
  `_BlockFacts`); the memoisation is the fix and the bound is the guarantee.

The tunables below are module-level and read at call time *on purpose*: the
test suite mutates them one at a time to prove each rule is load-bearing
(ISSUE-081 AC-5). Do not inline them into the functions that read them.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# ── The wall-clock bound (SPEC-081 amendment 2026-10-24, AC-9.2) ─────

#: Seconds `analyze` may spend before it REFUSES rather than finishing.
#: Overridable with the env knob below.
#:
#: 60 is chosen against MEASURED headroom, not picked round. After the
#: `_BlockFacts` hoist the slowest honest input measured for this change is
#: **0.187 s** — a 245 KB diff adding 800 gates and 800 batteries where every
#: battery attributes to every gate, which is roughly 8x this repo's largest
#: real PR — so the default is ~320x the worst honest case. The same input
#: cost 5.089 s before the hoist, and the attempt-3 review measured 32.5 s at
#: 212 KB, so 60 s is also above the pre-fix cost of everything it saw: the
#: bound is a backstop, not a tuning parameter. It stays an order of
#: magnitude under the sprint runner's 600 s no-progress watchdog so the
#: refusal is what the operator sees, not a killed agent.
DEFAULT_TIMEOUT_SECONDS = 60.0

#: THE knob name, as one constant: the failure message, the module docstring
#: and the suite all read it from here rather than re-typing a literal that
#: can drift (review lesson 2 — print the knob name in the failure message it
#: remediates).
GATE_EVIDENCE_TIMEOUT_ENV = "KIT_GATE_EVIDENCE_TIMEOUT"


def _timeout_budget() -> float:
    """Resolve `analyze`'s wall-clock budget at call time.

    Reads ``KIT_GATE_EVIDENCE_TIMEOUT`` (seconds). A valid positive value
    overrides the default; unset, non-numeric, zero and negative values fall
    back to `DEFAULT_TIMEOUT_SECONDS` without crashing — the same semantics
    ``KIT_CHECKPOINT_TEST_TIMEOUT`` and ``KIT_SPRINT_QUEUE_GH_TIMEOUT``
    already have, so an operator who knows one knows all three. Fractional
    seconds are accepted (the sibling knobs' `float` spelling, not `int`), so
    the bound is testable without a multi-second test.
    """
    raw = os.environ.get(GATE_EVIDENCE_TIMEOUT_ENV, "")
    try:
        seconds = float(raw)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS
    # `nan > 0` is False, so NaN lands on the default with everything else.
    return seconds if seconds > 0 else DEFAULT_TIMEOUT_SECONDS


class AnalysisTimeout(Exception):
    """`analyze` hit its wall-clock bound and REFUSED rather than finishing.

    Deliberately NOT a `Finding`: a finding is a verdict about a gate, and the
    analysis that would have produced one did not complete. It is also not a
    second statement of the tier — `BLOCKING_KINDS` stays the only statement
    of which finding KINDS block. Both consumers catch it and fail CLOSED:
    `main` at exit **2**, the code it already uses for "refused to evaluate"
    and visibly distinct from the **1** a blocking finding produces, and
    ``verify_checkpoint.verify_review_gate_evidence`` at `False`.
    """


_TIMEOUT_MESSAGE = (
    "REFUSED (not clean): gate-evidence analysis exceeded its wall-clock "
    "budget after {elapsed:.3f}s of {budget:g}s on a {size}-character diff, "
    "so it did NOT complete — this is NOT a pass. A half-finished analysis "
    "cannot tell a clean diff from one whose gates are unevidenced, and a "
    "blocking review gate that can be parked by its own subject is an "
    "availability defect (SPEC-081 amendment 2026-10-24, AC-9.2). Raise the "
    "bound by exporting `{env}=<seconds>` (default {default:g}; non-numeric, "
    "zero and negative values fall back to that default). If the diff is not "
    "honestly this large, the input SHAPE is the defect — the cost is driven "
    "by the gates x test-batteries product, not by size alone — so report it "
    "rather than raising the bound."
)


class _Deadline:
    """One `analyze()` call's wall-clock budget, POLLED at loop granularity.

    Polled rather than enforced with `signal.alarm` or a watchdog thread, on
    purpose: `analyze` runs in-process inside `verify_checkpoint`, which
    `scripts/checkpoint.sh` `exec`s, so a process-global alarm is
    main-thread-only and would fire inside whatever the caller does next. The
    polls sit where the cost accrues — once after parsing, then once per
    battery and once per gate, which are the two loops whose product was the
    measured quadratic.
    """

    def __init__(self, size: int) -> None:
        self._size = size
        self._budget = _timeout_budget()
        self._start = time.monotonic()

    def check(self) -> None:
        elapsed = time.monotonic() - self._start
        if elapsed <= self._budget:
            return
        raise AnalysisTimeout(
            _TIMEOUT_MESSAGE.format(
                elapsed=elapsed,
                budget=self._budget,
                size=self._size,
                env=GATE_EVIDENCE_TIMEOUT_ENV,
                default=DEFAULT_TIMEOUT_SECONDS,
            )
        )

# ── The finding TIER (SPEC-081 amendment 2026-10-24, decision 6) ─────

#: THE one statement of which finding kinds block. The rendered verdict
#: vocabulary, the CLI exit code and
#: ``verify_checkpoint.verify_review_gate_evidence``'s boolean all DERIVE from
#: this set; none of them may re-state it. A kind that is advisory in the
#: renderer and blocking in the consumer — or the reverse — is a new fail-open
#: of exactly the shape ISSUE-081 exists to stop.
#:
#: Why this kind and ONLY this kind is decidable: ``missing-disarm-battery``
#: fires if and only if ``attributed == []``, which is computed purely from
#: ``_called_names`` (the symbol-name call extraction `_calls` spells by
#: symbol) and ``_attributed_by`` (the name-token match on the vacuity guard
#: that `_attributed` spells by block). It never consults ``_refusal_shaped``,
#: so no
#: polarity judgement can make it fire or not fire; the property it asserts —
#: "no added test battery mentions this gate at all" — is true or false in the
#: diff text and nowhere else.
#:
#: ``unreadable-binary-rendering`` is decidable in the same sense and is a
#: REFUSAL rather than a verdict: git either rendered a non-test ``.py`` path
#: as text or as bytes, and when it rendered it as bytes this module read none
#: of the file, so "no gate detected" would be a claim it has no basis for.
#: One committed ``.gitattributes`` line (``*.py -diff``) produced exactly
#: that pass at exit 0 (SPEC-081 amendment 2026-10-24, AC-9.1).
#:
#: Why the other two only advise: both route through ``_refusal_shaped``, and
#: predicate polarity is NOT decidable for a detector-shaped gate, where the
#: disarm direction is correctly written ``assert detected is True`` — the
#: arm-shaped expectation IS the refusal. Measured over this repo's own 4047
#: assert lines, 598 (14.8%) are credited as refusals, ~40% of them bare
#: ``len()``/``count()`` comparisons; the committed decisive fixture reached
#: exit 0 on batteries whose only "refusal" was ``status_code == 200``.
#:
#: The PHASE is unaffected: ``("review", "gate-evidence")`` stays OUT of
#: ``verify_checkpoint.ADVISORY_PHASES``, so the obligation is still an exit
#: code for the decidable half. What is advisory is a finding KIND.
BLOCKING_KINDS = frozenset(
    {"missing-disarm-battery", "unreadable-binary-rendering"}
)


# ── Tunables (mutation-pinned by tests/test_gate_evidence_contract.py) ──

#: Minimum distinct input variants before a parametrized/looped test counts as
#: a *battery* rather than a single case. 3 is the smallest count at which
#: "varied the input" is a claim rather than a coincidence; SPEC-081's Open
#: Questions schedules re-tuning this on measured false positives only.
MIN_VARIANTS = 3

#: Require a composite battery to carry an input-side vacuity guard. This is
#: also what attributes the battery to a specific gate.
REQUIRE_VACUITY_GUARD = True

#: Require a battery's parameters to feed only the INPUT. A table whose
#: *expected* value is itself a parameter is an outcome mapping, not a
#: direction battery.
REQUIRE_INPUT_ONLY_PARAMS = True

#: Require a composite battery to assert a consumer-level outcome (exit code,
#: return code, or a refusal constant), not merely to mention one.
REQUIRE_CONSUMER_OUTCOME = True

#: Require a battery to assert the gate's REFUSAL, not merely to exercise it.
#: Without this, "disarm battery" degenerates into ">= MIN_VARIANTS variants
#: that mention the gate" — measured: `disarm` was True for 7 of 8 purely
#: arm-only shapes, including the no-guard shape that is the shape of all four
#: historical fail-opens, and the committed `issue_078_pre_fix.diff` reached
#: exit 0 when the only addition was two arm-direction batteries with
#: mechanically zero refusal assertions. The implementation measured
#: end-to-end-ness while the requirement names DIRECTION. 1/8 -> 8/8 with this
#: on; pinned in both directions by `TestDirectionIsWhatIsMeasured`.
REQUIRE_REFUSAL_DIRECTION = True

# ── Vocabulary ───────────────────────────────────────────────────────

#: A refusal: the gate's blocking branch. Matched against *de-stringed* code so
#: prose inside a docstring or a generated skill fragment cannot manufacture a
#: gate. Boolean returns are only a refusal in a predicate-shaped function
#: (see ``_PREDICATE_SHAPE``) — otherwise every accessor would be a gate.
REFUSAL_PATTERNS = (
    re.compile(r"\breturn\s+[1-9]\d*\b"),
    re.compile(r"\bsys\.exit\(\s*[1-9]"),
    re.compile(r"\bos\._exit\(\s*[1-9]"),
    re.compile(r"\braise\s+SystemExit\(\s*[1-9]"),
    re.compile(r"\braise\s+\w*(?:Error|Exception)\b"),
    re.compile(r"\breturn\s+\w*EXIT\w*\b"),
    re.compile(r"\b(?:valid|ok|allowed|permitted|passed)[\"']?\s*[:=]\s*False\b"),
)

#: A boolean return counts as a refusal only here.
_BOOL_REFUSAL = re.compile(r"\breturn\s+(?:True|False)\b")

#: Longest gap a ternary's `if` and `else` may be apart. The third alternative
#: used to be `\bif\b.+\belse\b`, which restarts `.+` from every `if` and can
#: never succeed on a line with no `else` — measured O(n^2): 4x the time per 2x
#: the input, 15.2 s on one 208 KB added line. Nothing bounds this module's
#: wall clock — `scripts/checkpoint.sh` `exec`s python3 with no timeout — so an
#: author-written line was enough to park this blocking gate. (That wall clock
#: is now bounded outright — see ``KIT_GATE_EVIDENCE_TIMEOUT``.) A bounded
#: quantifier makes the scan linear; 400 is far past any real ternary.
#:
#: Its pin, corrected. This used to cite
#: `TestAPathologicalLineCannotHangTheCheckpoint`, which asserts only a
#: wall-clock budget — and a NARROWER bound satisfies that better, so the test
#: could not have been holding this value in place. The claim was false in the
#: same way the `_GIT_TIMEOUT` provenance comment this file already records was,
#: and the mutant measured the consequence: `400 -> 40` left the suite green.
#: The value is now pinned behaviourally by `TestAC5MutationMatrix`'s AC-9.4
#: cases — a real ternary with a 110-character gap must still read as a
#: conditional, a 537-character gap is the documented blind spot, and the
#: load-bearing case narrows THIS pattern rather than re-typing it.
_TERNARY_GAP = 400

_CONDITIONAL = re.compile(
    r"(?:^\s*(?:if|elif|while)\b)|(?:^\s*assert\b)"
    rf"|(?:\bif\b[^\n]{{0,{_TERNARY_GAP}}}?\belse\b)"
)

#: Longest prefix of ONE added line that gate detection regexes. Belt and
#: suspenders with `_TERNARY_GAP`: it makes the per-line cost O(1) no matter
#: what any future pattern here does.
#:
#: The bound TRUNCATES rather than drops, so it fails toward DETECTION — every
#: line-anchored pattern (`^\s*if`, `^\s*assert`) and every refusal inside the
#: first 2 KB of a physical line still arms the gate. The deliberate blind spot
#: it accepts: a gate whose ONLY conditional and ONLY refusal both sit past this
#: offset on a single physical line. That is a minified artefact, not a shape
#: hand-written Python takes, and a 2 KB source line is not a plausible gate.
#: Both directions are pinned by `TestTheScanWindowFailsTowardDetection`;
#: widening this constant must restore the blind-spot gate.
_MAX_SCAN_CHARS = 2048

_PREDICATE_SHAPE = re.compile(
    r"^(?:is|has|was|can|should|must|are)_"
    r"|_is_|_has_"
    r"|^(?:check|verify|validate|ensure|require|assert|guard|refuse|reject"
    r"|allow|permit|detect)"
    r"|_valid|valid$|_ok$",
    re.IGNORECASE,
)

_DEF_RE = re.compile(r"^(\s*)(?:async\s+)?def\s+(\w+)\s*\(")
_HUNK_RE = re.compile(r"^@@[^@]*@@(.*)$")

#: Root identifiers that name the *input* under test. An occurrence whitelist,
#: not a phrasing blacklist: a guard over ``out`` / ``result`` / ``captured``
#: asserts something about the gate's OUTPUT and proves nothing about the
#: fixture, so it must not attribute a battery to a gate.
_INPUT_ROOTS = frozenset(
    {
        "text",
        "content",
        "contents",
        "src",
        "source",
        "raw",
        "body",
        "doc",
        "document",
        "data",
        "diff",
        "diff_text",
        "fixture",
        "payload",
        "rendered",
        "tmpl",
        "template",
        "markdown",
        "blob",
        "generated",
        "sprint_text",
        "file_text",
    }
)

_GENERIC_TOKENS = frozenset(
    {
        "the",
        "and",
        "get",
        "set",
        "has",
        "can",
        "not",
        "for",
        "all",
        "any",
        "run",
        "add",
        "new",
        "one",
        "two",
        "old",
        "was",
        "are",
        "its",
        "use",
        "with",
        "from",
        "this",
        "that",
        "out",
        "value",
        "line",
        "test",
    }
)

_EXEMPT_RE = re.compile(
    r"GATE-EVIDENCE-EXEMPT\(\s*([\w.]+)\s*\)\s*:\s*(?P<reason>.*)"
)

#: What must precede the marker on its line for it to be a real attestation: a
#: ``#`` with no quote character before it. Matched against the line PREFIX, so
#: a dedicated comment line and a trailing comment both qualify, while a marker
#: inside a string literal (or in running prose that happens to contain one)
#: does not. Fails CLOSED on the ambiguous `foo("x")  # GATE-...` shape, which
#: is the safe direction for a waiver.
_COMMENTED_RE = re.compile(r"^[^\"'#]*#")

_VACUITY_RE = re.compile(
    r"\bassert\s+(?P<q>[\"'])(?P<lit>(?:[^\"'\\]|\\.)*)(?P=q)"
    r"\s+(?:not\s+)?in\s+(?P<expr>[^,\n]+)"
)

#: The operator is CAPTURED, not discarded: the composite half has to know
#: whether the consumer-level literal was asserted in the refusal direction,
#: and `returncode != 0` and `returncode != False` say opposite things.
_CONSUMER_RE = re.compile(
    r"\bassert\s+[\w.\[\]\"'() ]*\b"
    r"(?:exit_code|exitcode|returncode|return_code|status_code|rc)\b"
    r"\s*(?P<op>==|!=|is(?:\s+not)?)\s*(?P<expected>[^,\n]+)"
)

_ASSERT_EXPECTED_RE = re.compile(r"(?:\bis\s+(?:not\s+)?|==|!=)\s*([^,\n]+)")

_LITERAL_EXPECTED_RE = re.compile(
    r"^(?:True|False|None|-?\d+|[\"'].*|[\w.]*\b[A-Z][A-Z0-9_]{2,}\b.*)$"
)

# ── Direction vocabulary ─────────────────────────────────────────────
#
# What a battery ASSERTS, not merely that it ran. `_is_battery` above is
# direction-blind by design — it answers "is this a battery", and
# `_LITERAL_EXPECTED_RE` matches `True`/`0`/`None` as readily as `False`/`1`.

#: Operators that INVERT the expected side's polarity. This is the whole reason
#: the test is operator-aware rather than a lookup on the expected value: under
#: `!=`, a SUCCESS literal is the refusal expectation, so `!= 0` counts and
#: `!= False` does not. A rule that inspected only the right-hand side would
#: get the negated form exactly backwards on both.
_NEGATING_OPERATORS = frozenset({"!=", "is not"})

#: One comparison on an assert line, operator INCLUDED. `is not` is listed
#: before `is` so the longer operator wins; `_ASSERT_EXPECTED_RE` above stays
#: as it is because `_is_battery` needs the expected side without the operator.
_COMPARISON_RE = re.compile(
    r"(?P<op>\bis\s+not\b|\bis\b|==|!=)\s*(?P<expected>[^,\n]+)"
)

#: The SUCCESS side of a boolean / exit-code comparison. Under a negating
#: operator this — and only this — is a refusal expectation.
_SUCCESS_LITERAL_RE = re.compile(r"^(?:True|[+-]?0+)$")

_FALSE_LITERAL_RE = re.compile(r"^False$")

#: A non-zero integer literal: `exit 1`, `exit 3`, `return 2`.
_NONZERO_INT_RE = re.compile(r"^[+-]?0*[1-9]\d*$")

#: A SCREAMING_CASE name, same spelling `_LITERAL_EXPECTED_RE` uses.
_SCREAMING_NAME_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")

#: Refusal tokens inside such a name: `sq.ROSTER_BOUNDARY_EXIT`, `FAIL_EXIT`.
_REFUSAL_TOKEN_RE = re.compile(
    r"EXIT|FAIL|ERROR|REFUS|REJECT|BOUNDARY|INVALID|BLOCK"
)

#: A quoted literal, so the refusal vocabulary below is matched against STRING
#: LITERALS only. Against bare expressions it would read `== failures` (a
#: variable) as a refusal expectation on the strength of the author's naming,
#: which is the "it detects the vocabulary, not the refusal" mistake the
#: SPEC-081 amendment killed a candidate rule for.
_STRING_LITERAL_RE = re.compile(r"^[\"'](?P<inner>(?:[^\"'\\]|\\.)*)[\"']$")

#: A refusal VERDICT string: `== "invalid"`, `== "rejected"`.
_REFUSAL_STRING_RE = re.compile(
    r"invalid|rejected|blocked|refused|denied|error|fail|refus|reject",
    re.IGNORECASE,
)

#: The two non-comparison refusal idioms. `assert not <expr>` asserts the
#: falsey direction directly, and both exception expectations assert that the
#: call REFUSED rather than returned.
_ASSERT_NOT_RE = re.compile(r"\bassert\s+not\b")
_RAISES_RE = re.compile(r"\b(?:pytest\.raises|assertRaises(?:Regex)?)\s*\(")


# ── Result types ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Gate:
    symbol: str
    path: str
    line: int


@dataclass(frozen=True)
class Finding:
    symbol: str
    path: str
    line: int
    kind: str
    message: str

    @property
    def tier(self) -> str:
        """``"blocking"`` or ``"advisory"``, DERIVED from `kind`.

        Deliberately not a stored field: a tier that can be passed in at
        construction can disagree with the kind it was computed from, and a
        kind/tier disagreement is the fail-open the split exists to avoid.
        """
        return "blocking" if self.kind in BLOCKING_KINDS else "advisory"


@dataclass(frozen=True)
class Report:
    gates: tuple[Gate, ...]
    #: EVERY finding, both tiers, in detection order. Unchanged by the
    #: 2026-10-24 split so that callers which only want "what did this diff
    #: get told about" keep working; the two properties below are the split.
    findings: tuple[Finding, ...]
    #: ``(path, symbol, reason)``. Path-qualified because an exemption is only
    #: honoured in the file that defines the gate.
    exemptions: tuple[tuple[str, str, str], ...]
    #: Keyed ``(path, symbol)``. A bare-symbol key silently merged two
    #: same-named gates in different files (measured: PR #101 detects 6 gates
    #: and used to yield 5 records).
    evidence: dict[tuple[str, str], dict[str, bool]]

    @property
    def blocking_findings(self) -> tuple[Finding, ...]:
        """The findings that make this phase exit non-zero."""
        return tuple(f for f in self.findings if f.tier == "blocking")

    @property
    def advisory_findings(self) -> tuple[Finding, ...]:
        """The findings that are reported and never block."""
        return tuple(f for f in self.findings if f.tier == "advisory")


# ── Diff parsing ─────────────────────────────────────────────────────

#: C-escape sequences git's ``quote_c_style`` emits in a quoted pathname,
#: besides the three-digit octal form it uses for every byte >= 0x80 and every
#: control character without a named escape.
_C_ESCAPES = {
    "a": 0x07, "b": 0x08, "f": 0x0C, "n": 0x0A, "r": 0x0D,
    "t": 0x09, "v": 0x0B, '"': 0x22, "\\": 0x5C,
}

#: Single-letter prefixes a diff header's path may carry. ``a/``/``b/`` are the
#: default; ``diff.mnemonicPrefix=true`` substitutes ``i/`` (index), ``w/``
#: (worktree), ``c/`` (commit) or ``o/`` (object), and a combined diff uses
#: ``1/``/``2/``. Restricted to these letters so a real top-level directory
#: (``x/thing.py``) is not silently relabelled. Inherent residual ambiguity: a
#: repository whose top-level directory is literally named ``b`` is
#: indistinguishable in this format — it affects the printed LABEL only, never
#: whether the gate is detected (that keys on the ``.py`` suffix).
_GIT_PATH_PREFIXES = frozenset("abiwco12")


def unquote_c_style(field: str, *, errors: str = "replace") -> str:
    """Decode one C-quoted pathname exactly as ``git`` wrote it.

    With ``core.quotePath=true`` — git's DEFAULT — git wraps any pathname
    holding a non-ASCII byte, a control character, a ``"`` or a ``\\`` in double
    quotes and escapes it, so real ``git diff`` emits::

        +++ "b/scripts/gat\\303\\251.py"

    The quotes live INSIDE the header field. Anything that reads the field
    literally sees a path that neither starts with ``b/`` nor ends in ``.py``,
    which made `detect_gates` skip the file outright — measured on this
    module's own pre-fix fixture, which then reported "no gate-adding change".

    THE single decoder for this module and for
    ``verify_checkpoint._untracked_diff_text``, which needs the same decoding
    for ``git ls-files`` output. Verified against real ``git diff`` output
    (git 2.44) for a non-ASCII name — quoted only when ``core.quotePath`` is
    true, i.e. by default — and for names containing ``"``, ``\\`` or a tab,
    which git quotes even when ``core.quotePath`` is false.

    A field that is not quoted, or whose quoting is malformed, is returned
    unchanged: never guess. ``errors`` is handed to the UTF-8 decode — callers
    that only LABEL the path want ``"replace"`` (it cannot raise), the caller
    that hands the path back to the filesystem wants ``"surrogateescape"`` so
    the original bytes round-trip.
    """
    if not field.startswith('"'):
        return field
    out = bytearray()
    index = 1
    closed = False
    while index < len(field):
        char = field[index]
        if char == '"':
            closed = True
            break
        if char != "\\":
            out.extend(char.encode("utf-8", errors="surrogateescape"))
            index += 1
            continue
        index += 1
        if index >= len(field):
            break
        escape = field[index]
        if escape in _C_ESCAPES:
            out.append(_C_ESCAPES[escape])
            index += 1
            continue
        if escape in "01234567":
            digits = ""
            while (
                len(digits) < 3
                and index < len(field)
                and field[index] in "01234567"
            ):
                digits += field[index]
                index += 1
            out.append(int(digits, 8) & 0xFF)
            continue
        # git emits no other escape; keep the character rather than drop it.
        out.extend(escape.encode("utf-8", errors="surrogateescape"))
        index += 1
    if not closed:
        return field
    return out.decode("utf-8", errors=errors)


def _header_path(field: str) -> str:
    """The path a ``--- ``/``+++ `` header names, in any rendering the tools emit.

    Three renderings reach this function, and the ``.py`` filter in
    `detect_gates` keys on the result of all three:

    * ``"b/scripts/gat\\303\\251.py"`` — git's DEFAULT whenever the path needs
      quoting. Unquoted FIRST, because the leading ``"`` otherwise defeats the
      prefix strip.
    * ``scripts/gate.py\\t2026-01-02 10:00:00`` — plain ``diff -u`` appends a
      TAB and a timestamp, and git appends a bare TAB when the path contains a
      space. The field ends at the first TAB either way. (A path that itself
      contains a TAB is quoted, so the two cases never collide.)
    * ``w/scripts/gate.py`` — ``diff.mnemonicPrefix=true``.
    """
    field = field.strip()
    if field.startswith('"'):
        path = unquote_c_style(field)
    else:
        path = field.split("\t", 1)[0].strip()
    if len(path) > 2 and path[1] == "/" and path[0] in _GIT_PATH_PREFIXES:
        path = path[2:]
    return path


def _scannable(line: str) -> str:
    """One added line, truncated to `_MAX_SCAN_CHARS` before any regex sees it."""
    return line if len(line) <= _MAX_SCAN_CHARS else line[:_MAX_SCAN_CHARS]


def _destring(line: str) -> str:
    """Blank string-literal *prose* while keeping identifier-like literals.

    ``"valid": False`` must stay matchable (it is a verdict value), while a
    skill fragment that happens to contain the words of a refusal must not
    manufacture a gate. A literal whose content is a single bare word survives;
    everything else becomes an empty literal.
    """

    def repl(match: re.Match) -> str:
        quote, inner = match.group(1), match.group(2)
        if re.fullmatch(r"\w{1,24}", inner):
            return f"{quote}{inner}{quote}"
        return f"{quote}{quote}"

    return re.sub(r"([\"'])((?:[^\"'\\]|\\.)*?)\1", repl, line)


#: THE definition of "a test file" in this repo, and the one
#: ``verify_checkpoint``'s implement phases now consume as
#: ``vge.TEST_FILE_PATTERN`` / ``vge.TEST_DIR_PATTERN``.
#:
#: It used to exist FOUR times: byte-identically at two ``verify_checkpoint``
#: call sites (``implement/red`` and ``implement/tests-written``), re-typed here
#: as a weaker copy that dropped the SINGULAR directory spelling and the
#: ``__tests__`` convention, and once more as a name-only rule inside
#: ``verify_review_test_quality``'s worktree walk. Measured consequence of the
#: weaker copy: the IDENTICAL helper file was exempt under a plural test
#: directory (``gates=[]``) and a reported GATE under the singular one
#: (``gates=[('assert_guard','test/helpers.py')]``), so any repo laid out the
#: singular way — standard outside Python — paid a fabricated-finding tax on a
#: diff that adds no gate (ISSUE-081 AC-3), and added batteries under those
#: directories never entered ``_blocks``, so evidence for a REAL gate could go
#: missing too. The regexes below are ``verify_checkpoint``'s, verbatim:
#: unifying on the STRONGER oracle classifies more paths as tests, which for
#: gate detection means FEWER fabricated findings.
#:
#: The fourth definition is deliberately NOT unified — see the comment at its
#: own call site in ``verify_checkpoint.verify_review_test_quality`` for the
#: measurement that scopes it out (review lesson 8).
#:
#: Import direction: ``verify_checkpoint`` already depended on this module for
#: ``unquote_c_style``, so the shared definition lives HERE and the dependency
#: edge keeps the direction it had. The inverse was measured to execute
#: ``verify_checkpoint``'s module body TWICE — ``scripts/checkpoint.sh`` ``exec``s
#: it as ``__main__``, so a module-level import of it from here mints a second
#: copy with its own ``_GATE_PROCESS_START``.
TEST_FILE_PATTERN = re.compile(
    r"(?:^|/)(?:test_[^/]+\.py|[^/]+_test\.py"
    r"|[^/]+\.(?:spec|test)\.(?:ts|tsx|js|jsx))$"
)
TEST_DIR_PATTERN = re.compile(r"(?:^|/)(?:tests?|__tests__)/")


def is_test_path(path: str) -> bool:
    """True for paths the suite owns (where every assert has a refusing branch)."""
    return bool(TEST_FILE_PATTERN.search(path) or TEST_DIR_PATTERN.search(path))


def is_scanned_source(path: str) -> bool:
    """True for the paths gate detection reads: non-test Python sources.

    THE one statement of the detector's subject, because three places need
    exactly the same answer: `detect_gates`, `_exemptions`, and the
    binary-rendering refusal, whose whole claim is that it covers *exactly*
    the paths `detect_gates` would have scanned. A fourth re-typed copy of
    this condition is how the test-path classifier came to have four
    disagreeing definitions (SPEC-081 amendment 2026-10-14, decision 5).
    """
    return path.endswith(".py") and not is_test_path(path)


@dataclass
class _FileDiff:
    path: str
    added: list[tuple[int, str]]            # (diff line number, text)
    added_by_def: dict[str, list[str]]      # enclosing def -> added code lines
    def_line: dict[str, int]                # enclosing def -> first added line
    signatures: dict[str, str]              # enclosing def -> its `def` line


def _parse(diff_text: str) -> list[_FileDiff]:
    files: list[_FileDiff] = []
    current: _FileDiff | None = None
    enclosing: str | None = None
    # A ``+++ `` line is a FILE HEADER only when the line before it was the
    # matching ``--- `` header; unified diff always writes the pair adjacently.
    # The anchor is what stops a diff-of-a-diff body line from minting a
    # phantom file that then steals the real file's hunk: an inner ``++ <path>``
    # line renders as ``+++ <path>`` once the outer diff ADDS it. This repo
    # COMMITS ~4.7k lines of `.diff` fixtures, so a PR that edits one IS a
    # diff-of-a-diff; before the anchor the only thing in the way was the
    # trailing space in the literal ``"+++ "``.
    src_header = False

    for number, raw in enumerate(diff_text.split("\n"), start=1):
        line = raw.rstrip("\r")
        after_src_header, src_header = src_header, False

        if line.startswith("--- "):
            src_header = True
            continue
        if line.startswith("diff --git "):
            continue

        if line.startswith("+++ ") and after_src_header:
            path = _header_path(line[4:])
            current = None if path == "/dev/null" else _FileDiff(path, [], {}, {}, {})
            if current is not None:
                files.append(current)
            enclosing = None
            continue
        if current is None:
            continue

        hunk = _HUNK_RE.match(line)
        if hunk:
            hint = _DEF_RE.match(hunk.group(1).lstrip())
            enclosing = hint.group(2) if hint else None
            continue

        if line.startswith("\\"):       # "\ No newline at end of file"
            continue

        if line.startswith("+"):
            body = line[1:]
            found = _DEF_RE.match(body)
            if found:
                enclosing = found.group(2)
                current.signatures[enclosing] = body
                current.def_line.setdefault(enclosing, number)
            current.added.append((number, body))
            if enclosing:
                current.added_by_def.setdefault(enclosing, []).append(body)
                current.def_line.setdefault(enclosing, number)
            continue

        if line.startswith("-"):
            continue

        # context line
        found = _DEF_RE.match(line[1:] if line.startswith(" ") else line)
        if found:
            enclosing = found.group(2)
            current.signatures.setdefault(enclosing, line.lstrip())


    return files


#: The two ways git says "I rendered this file as bytes, not as text".
#: ``Binary files <a> and <b> differ`` is the default; ``GIT binary patch`` is
#: what ``git diff --binary`` emits in its place. Verified against real git
#: 2.44 output for an added, a modified and a deleted file, for a path holding
#: a space, and for a non-ASCII path (which git C-quotes by default).
_BINARY_FILES_PREFIX = "Binary files "
_BINARY_FILES_SUFFIX = " differ"
_GIT_BINARY_PATCH = "GIT binary patch"
_DIFF_GIT_PREFIX = "diff --git "


def _diff_git_b_field(rest: str) -> str:
    """The b-side field of a ``diff --git <a> <b>`` header line.

    Needed only for the ``GIT binary patch`` rendering, which carries no
    ``+++ `` header, no ``Binary files`` line, and therefore no other copy of
    the path. The header is ambiguous in general — git separates the two
    fields with a space and does NOT quote a path merely because it contains
    one — so the split is taken where both fields name the SAME path, which is
    what git writes for everything except a rename. A rename falls through to
    the last space, i.e. to its new name.
    """
    for index, char in enumerate(rest):
        if char != " ":
            continue
        left, right = rest[:index], rest[index + 1:]
        if left and right and _header_path(left) == _header_path(right):
            return right
    return rest.rsplit(" ", 1)[-1]


def _binary_rendered(diff_text: str) -> list[tuple[int, str]]:
    """``(diff line number, path)`` for every file git rendered as BINARY.

    A sibling of `_parse` rather than a field on `_FileDiff`, because that
    list means "files whose TEXT this module can scan" and four parser pins
    depend on a binary-rendered file contributing none. Both route every path
    through `_header_path`, so there is one path decoder here, not two.

    Why a BLOCKING gate has to care (SPEC-081 amendment 2026-10-24, AC-9.1):
    one committed ``.gitattributes`` line, ``*.py -diff``, makes git render
    every ``.py`` file as ``Binary files ... differ``. `_parse` only opens a
    file on a ``--- ``/``+++ `` header pair, so it saw no file at all and
    `analyze` printed the byte-identical ordinary gate-free verdict at exit 0
    — measured on a throwaway two-commit repository. `main`'s "not a unified
    diff" refusal does not fire either, because the non-``.py`` files in the
    same diff still supply ``+++ `` headers. Review lesson 5 applies verbatim:
    workspace-persisted state a gate reads is untrusted input.

    Both markers are recognised only at column 0, where git writes an extended
    header. A ``+``/``-``/`` ``-prefixed copy of either line is diff CONTENT —
    this repo commits ~4.7k lines of ``.diff`` fixtures, so a PR that edits
    one really does carry those bytes — and must not be read as a header.

    A b-side of ``/dev/null`` is a DELETION, and a deleted file adds no gate,
    so it is skipped rather than refused; the ``deleted file mode`` extended
    header is the equivalent signal for the ``GIT binary patch`` rendering,
    which keeps the real path on both sides of its ``diff --git`` line.

    Residual, inherent to the format and disclosed rather than guessed at: an
    UNQUOTED path containing the literal `` and `` makes the ``Binary files``
    line ambiguous. Git quotes a path for a non-ASCII byte, a control
    character, a ``"`` or a ``\\`` — not for a space — so this cannot be
    resolved from the line alone. It affects which path is named, and it fails
    toward naming the wrong path rather than toward silence.
    """
    found: list[tuple[int, str]] = []
    header = ""
    deleted = False
    for number, raw in enumerate(diff_text.split("\n"), start=1):
        line = raw.rstrip("\r")
        if line.startswith(_DIFF_GIT_PREFIX):
            header, deleted = line[len(_DIFF_GIT_PREFIX):], False
            continue
        if line.startswith("deleted file mode "):
            deleted = True
            continue
        if line.startswith(_BINARY_FILES_PREFIX) and line.endswith(
            _BINARY_FILES_SUFFIX
        ):
            body = line[len(_BINARY_FILES_PREFIX):-len(_BINARY_FILES_SUFFIX)]
            path = _header_path(body.rsplit(" and ", 1)[-1])
        elif line == _GIT_BINARY_PATCH and header and not deleted:
            path = _header_path(_diff_git_b_field(header))
        else:
            continue
        if path != "/dev/null":
            found.append((number, path))
    return found


# ── Gate detection ───────────────────────────────────────────────────


# GATE-EVIDENCE-EXEMPT(_is_predicate_shaped): private gate-detection reach; exercised in both directions by the three fixture replays (it is what admits `sprint_status_is_running` and leaves the non-gate diff empty) and killed by the `refusal_vocabulary_emptied` mutant, which disables the boolean-refusal path it guards.
def _is_predicate_shaped(symbol: str, signature: str) -> bool:
    # One whitespace-insensitive test, not two. The branch that used to sit
    # above this one looked for `-> bool` in the signature after substituting
    # U+0020 for U+0020 — a literal no-op, verified to be ordinary spaces on
    # both sides, almost certainly an unfinished edit meant to collapse DOUBLE
    # spaces, and shipped inside a blocking gate. The strip-all form below
    # strictly dominates it on every signature shape (`-> bool`, `->bool`,
    # `->  bool`, `-> bool | None`), so deleting it is behaviour-preserving;
    # pinned shape by shape by `TestTheNoOpSignatureBranchIsGone`.
    if "->bool" in signature.replace(" ", ""):
        return True
    return bool(_PREDICATE_SHAPE.search(symbol))


def detect_gates(files: list[_FileDiff]) -> tuple[Gate, ...]:
    gates: list[Gate] = []
    for file in files:
        if not is_scanned_source(file.path):
            continue
        for symbol, lines in file.added_by_def.items():
            code = [_destring(_scannable(line)) for line in lines]
            if not any(_CONDITIONAL.search(line) for line in code):
                continue
            refusal = any(
                pattern.search(line) for line in code for pattern in REFUSAL_PATTERNS
            )
            if not refusal and _is_predicate_shaped(
                symbol, file.signatures.get(symbol, "")
            ):
                refusal = any(_BOOL_REFUSAL.search(line) for line in code)
            if refusal:
                gates.append(
                    Gate(symbol, file.path, file.def_line.get(symbol, 0))
                )
    return tuple(gates)


# ── Test-side evidence ───────────────────────────────────────────────


@dataclass
class _Block:
    head: str
    lines: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _blocks(files: list[_FileDiff]) -> tuple[list[_Block], str]:
    """Split added TEST lines into per-test blocks, plus the module-level text.

    A block is one added ``def test_*`` plus its body and any decorators that
    precede it — including a decorator's continuation lines, which do not start
    with ``@`` and were the first thing a naive splitter dropped.
    """
    blocks: list[_Block] = []
    module_lines: list[str] = []
    for file in files:
        if not is_test_path(file.path):
            continue
        module_lines.extend(text for _, text in file.added)

        pending: list[str] = []
        depth = 0
        current: _Block | None = None
        for _, text in file.added:
            stripped = text.strip()
            if depth > 0:
                pending.append(text)
                if current is not None:
                    current.lines.append(text)
                depth += text.count("(") + text.count("[") - text.count(")") - text.count("]")
                depth = max(depth, 0)
                continue
            if stripped.startswith("@"):
                pending.append(text)
                if current is not None:
                    current.lines.append(text)
                depth = max(
                    text.count("(") + text.count("[")
                    - text.count(")") - text.count("]"),
                    0,
                )
                continue
            found = _DEF_RE.match(text)
            if found or stripped.startswith("class "):
                name = found.group(2) if found else ""
                if name.startswith("test"):
                    current = _Block(stripped, list(pending) + [text])
                    blocks.append(current)
                else:
                    current = None
                pending = []
                continue
            pending = []
            if current is not None:
                current.lines.append(text)
    return blocks, "\n".join(module_lines)


def _count_bracket_elements(text: str, start: int) -> int:
    """Count top-level elements of the bracketed list opening at ``text[start]``.

    Scans with its own quote state rather than pre-stripping literals: the
    de-stringing pass changes the string's LENGTH, so indices computed against
    the original text no longer address the same characters (measured: this
    silently returned 0 for every named argvalues list).
    """
    depth = 0
    commas = 0
    seen = False
    quote: str | None = None
    last_significant = ""
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'":
            quote = char
            if depth == 1:
                seen = True
                last_significant = char
            index += 1
            continue
        if char in "([{":
            depth += 1
            if depth > 1:
                seen = True
                last_significant = char
            index += 1
            continue
        if char in ")]}":
            depth -= 1
            if depth == 0:
                break
            last_significant = char
            index += 1
            continue
        if depth == 1 and not char.isspace():
            if char == ",":
                commas += 1
            else:
                seen = True
            last_significant = char
        index += 1

    if not seen:
        return 0
    return commas if last_significant == "," else commas + 1


def _argnames(decorator: str) -> list[str]:
    match = re.search(r"parametrize\(\s*[\"']([^\"']+)[\"']", decorator)
    if not match:
        return []
    return [name.strip() for name in match.group(1).split(",") if name.strip()]


def _variant_count(block: _Block, module_text: str) -> int:
    text = block.text
    match = re.search(r"parametrize\(\s*[\"'][^\"']+[\"']\s*,", text)
    if match:
        rest = text[match.end():]
        offset = len(text) - len(rest)
        bracket = re.match(r"\s*[\[(]", rest)
        if bracket:
            return _count_bracket_elements(text, offset + bracket.end() - 1)
        named = re.match(r"\s*([A-Za-z_]\w*)", rest)
        if named:
            return _named_list_length(named.group(1), module_text)
        return 0

    loop = re.search(r"\bfor\s+[\w, ]+\s+in\s+(?!range)", text)
    if loop:
        rest = text[loop.end():]
        if rest.lstrip().startswith("["):
            offset = loop.end() + (len(rest) - len(rest.lstrip()))
            return _count_bracket_elements(text, offset)
        named = re.match(r"\s*([A-Za-z_]\w*)", rest)
        if named:
            return _named_list_length(named.group(1), module_text)
    return 0


def _named_list_length(name: str, module_text: str) -> int:
    """Element count of a named argvalues list, resolved from the diff's own lines.

    A name the diff does not define (a pre-existing table such as
    ``RUNNING_VALUES``) is PRESUMED to be a battery and credited exactly
    ``MIN_VARIANTS``. Counting it as zero would classify every PR that batteries
    against a table the suite already owns as arm-only, which is both wrong and
    the opposite of the behaviour ISSUE-081 wants to encourage. The presumption
    is deliberately confined to the *count*: a presumed battery still has to
    clear the vacuity-guard and consumer-outcome requirements before it can
    satisfy the composite half, so the presumption cannot by itself clear a gate.
    """
    match = re.search(rf"^{re.escape(name)}\s*[:=]", module_text, re.MULTILINE)
    if not match:
        return MIN_VARIANTS
    opening = re.match(r"\s*=?\s*[\[(]", module_text[match.end() - 1:])
    if not opening:
        return MIN_VARIANTS
    return _count_bracket_elements(
        module_text, match.end() - 1 + opening.end() - 1
    )


def _expected_sides(block: _Block) -> list[str]:
    sides: list[str] = []
    for line in block.lines:
        if "assert" not in line:
            continue
        sides.extend(
            match.group(1).strip()
            for match in _ASSERT_EXPECTED_RE.finditer(line)
        )
    return sides


# GATE-EVIDENCE-EXEMPT(_is_battery): private predicate; mutation-pinned in BOTH directions through MIN_VARIANTS=999 on the real fixtures and MIN_VARIANTS=0 on `_SINGLE_CASE_DIFF`, plus REQUIRE_INPUT_ONLY_PARAMS on `_OUTCOME_MAP_DIFF`. It is direction-BLIND on purpose: it answers "is this a battery", and the refusal direction is `_asserts_refusal`'s question.
def _is_battery(block: _Block, module_text: str) -> bool:
    if _variant_count(block, module_text) < MIN_VARIANTS:
        return False
    if not any(
        _LITERAL_EXPECTED_RE.match(side) for side in _expected_sides(block)
    ):
        return False
    if REQUIRE_INPUT_ONLY_PARAMS:
        joined = " ".join(_expected_sides(block))
        for name in _argnames(block.text):
            if re.search(rf"\b{re.escape(name)}\b", joined):
                return False
    return True


def _tokens(name: str) -> set[str]:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    parts = re.split(r"[^A-Za-z0-9]+", spaced)
    return {
        part.lower()
        for part in parts
        if len(part) >= 3 and part.lower() not in _GENERIC_TOKENS
    }


def _guard_literals(block: _Block) -> list[str]:
    """Input-side vacuity-guard literals in this block."""
    literals: list[str] = []
    for line in block.lines:
        for match in _VACUITY_RE.finditer(line):
            expr = match.group("expr")
            root = re.match(r"\s*([A-Za-z_]\w*)", expr)
            if "read_text(" in expr or (root and root.group(1) in _INPUT_ROOTS):
                literals.append(match.group("lit"))
    return literals


def _guard_tokens(block: _Block) -> tuple[frozenset[str], ...]:
    """The NAME TOKENS of each vacuity-guard literal, one frozenset per literal.

    Extracted once per block by `_BlockFacts`, because every consumer of a
    guard literal wants its tokens and `analyze` used to re-derive them for
    every (gate, battery) pair (SPEC-081 amendment 2026-10-24, AC-9.2).
    """
    return tuple(frozenset(_tokens(literal)) for literal in _guard_literals(block))


# GATE-EVIDENCE-EXEMPT(_attributed): private predicate; mutation-pinned through REQUIRE_VACUITY_GUARD, which is the knob that makes attribution load-bearing.
def _attributed(block: _Block, symbol: str) -> bool:
    """True when a vacuity guard in this block names the gate's input.

    The by-BLOCK spelling, which is what the module docstring and
    `BLOCKING_KINDS` name and what the suite probes. `analyze` calls
    `_attributed_by` instead, with the block's guard tokens already extracted
    once — same rule, one extraction.
    """
    return _attributed_by(_guard_tokens(block), _tokens(symbol))


def _attributed_by(
    guard_tokens: tuple[frozenset[str], ...], symbol_tokens: set[str]
) -> bool:
    """THE attribution rule, over tokens already extracted once per block."""
    if not REQUIRE_VACUITY_GUARD:
        return True
    if not symbol_tokens:
        return False
    needed = 2 if len(symbol_tokens) >= 3 else 1
    return any(len(symbol_tokens & tokens) >= needed for tokens in guard_tokens)


#: One CALL in a block: `\b<name>\s*\(`, with the name generalised to `\w+`.
#: Byte-for-byte the pattern `_calls` used to build per (gate, battery) pair
#: with `re.escape`, which is why extracting every name ONCE is equivalent and
#: not merely similar — `TestCallAttributionIsExtractedOncePerBlock` checks
#: that against every pair the committed corpus produces. The `\b` is what
#: makes `_refuse(` and `refuse2(` non-calls of `refuse`, and the greedy `\w+`
#: is what preserves it: on `_refuse(` the capture is `_refuse`, so `refuse`
#: is correctly absent from the set.
_CALLEE_RE = re.compile(r"\b(\w+)\s*\(")


def _called_names(block: _Block) -> frozenset[str]:
    """Every name this block calls, extracted ONCE.

    `_calls` ran a freshly `re.escape`d search over a freshly re-joined
    `block.text` for every (gate, battery) pair: 160 000 searches and 160 000
    joins on a 400-gate diff, which profiled at 0.61 s of a 0.84 s run even
    after the per-block predicates were hoisted (SPEC-081 amendment
    2026-10-24, AC-9.2). `analyze` now tests set membership instead.
    """
    return frozenset(_CALLEE_RE.findall(block.text))


def _calls(block: _Block, symbol: str) -> bool:
    """True when this block calls `symbol`. The by-SYMBOL spelling."""
    return symbol in _called_names(block)


# GATE-EVIDENCE-EXEMPT(_is_non_vacuous): private predicate; mutation-pinned through REQUIRE_VACUITY_GUARD together with _attributed.
def _is_non_vacuous(block: _Block) -> bool:
    """True when the block proves its own fixtures still carry what they claim.

    A battery of 8 mutations with no input-side guard is indistinguishable from
    8 copies of a case that already passed, which is why this is required of a
    composite pin even when the gate is attributed by a direct call.

    The by-BLOCK spelling of `_non_vacuous`, for the same reason `_attributed`
    is the by-block spelling of `_attributed_by`.
    """
    return _non_vacuous(_guard_tokens(block))


def _non_vacuous(guard_tokens: tuple[frozenset[str], ...]) -> bool:
    """THE non-vacuity rule, over tokens already extracted once per block."""
    return (not REQUIRE_VACUITY_GUARD) or bool(guard_tokens)


# GATE-EVIDENCE-EXEMPT(_has_consumer_outcome): private predicate; mutation-pinned through REQUIRE_CONSUMER_OUTCOME on a constructed helper-only diff, and through REQUIRE_REFUSAL_DIRECTION by the `consumer_exit_zero` arm-only shape.
def _has_consumer_outcome(block: _Block) -> bool:
    """A consumer-level outcome asserted in the REFUSAL direction.

    `_CONSUMER_RE` alone accepts `returncode == 0` as readily as `== 1`, so on
    its own it measures that a consumer was driven, never that the consumer
    refused. The literal has to pass `_refusal_shaped` under its own operator.
    """
    if not REQUIRE_CONSUMER_OUTCOME:
        return True
    for raw in block.lines:
        # `_CONSUMER_RE` opens with `\bassert\s+[\w.\[\]"'() ]*\b(?:exit_code|…)`,
        # a permissive char-class star retried from EVERY `assert` start on the
        # line, so a line carrying many `assert` tokens and no outcome token
        # backtracks quadratically: measured 0.017 / 0.070 / 0.255 / 0.99 /
        # 3.96 s at 12 / 24 / 48 / 96 / 192 KB — 4x per 2x, O(n^2), reachable
        # through `analyze()` whenever a battery also carries a registering
        # vacuity guard (otherwise the `composite` conjunct short-circuits
        # before this function and the cost is invisible).
        #
        # `_MAX_SCAN_CHARS` was applied to the SOURCE half only (`detect_gates`),
        # so this, the EVIDENCE half, was left unbounded. Bounded here rather
        # than in `_blocks` on purpose: truncating the shared block text would
        # unbalance `_count_bracket_elements`' bracket scan and could miscount
        # variants in either direction. Fails CLOSED — a consumer outcome past
        # the window is simply not credited, which yields MORE findings.
        line = _scannable(raw)
        match = _CONSUMER_RE.search(line)
        if not match:
            continue
        expected = match.group("expected").strip()
        if not _LITERAL_EXPECTED_RE.match(expected):
            continue
        if REQUIRE_REFUSAL_DIRECTION and not _refusal_shaped(
            match.group("op"), expected
        ):
            continue
        return True
    return False


def _refusal_shaped(operator: str, expected: str) -> bool:
    """Does this comparison assert that the gate REFUSED?

    Operator-aware on purpose. Under ``==``/``is`` a refusal expectation is
    ``False``, a non-zero int literal, a SCREAMING_CASE constant whose name
    carries a refusal token, or a refusal verdict string. Under ``!=``/``is
    not`` it is the opposite: a *success* literal, which is what makes
    ``!= 0`` count and ``!= False`` not count. A rule that inspected only the
    expected value would classify both negated forms backwards.

    Lexical, and therefore fallible in one direction only — it under-credits.
    See the module docstring for the measured 16-of-27 error rate and the five
    mechanisms behind it; `missing-refusal-direction` is the finding kind that
    discloses it to the reviewer, with the exemption escape named inline.
    """
    value = expected.strip()
    if " ".join(operator.split()) in _NEGATING_OPERATORS:
        return bool(_SUCCESS_LITERAL_RE.match(value))
    literal = _STRING_LITERAL_RE.match(value)
    return bool(
        _FALSE_LITERAL_RE.match(value)
        or _NONZERO_INT_RE.match(value)
        or any(
            _REFUSAL_TOKEN_RE.search(name)
            for name in _SCREAMING_NAME_RE.findall(value)
        )
        or (literal and _REFUSAL_STRING_RE.search(literal.group("inner")))
    )


def _refusal_assertions(block: _Block) -> list[str]:
    """Every assertion in this block that reads as a refusal expectation.

    Scans the raw added line, so the vocabulary is matched against comments and
    assertion messages too. Disclosed rather than closed: a trailing
    ``# rc is 1`` on an otherwise arm-only assert line would over-credit the
    direction. That is an **under-detection**, the error direction SPEC-081
    declares safer (it fails to catch, it does not halt an honest review), it
    is visible in the diff, and an author who wants this gate to pass already
    has a one-line documented bypass in `_EXEMPT_RE` — so the vector grants
    nothing an adversary did not already have. Not de-stringed, because
    ``== "invalid"`` is a refusal expectation that `_destring` would keep but
    a longer message it would blank, and mixing the two policies in one pass
    is how the `_count_bracket_elements` index bug happened.
    """
    found: list[str] = []
    for line in block.lines:
        if _RAISES_RE.search(line) or _ASSERT_NOT_RE.search(line):
            found.append(line.strip())
            continue
        if "assert" not in line:
            continue
        for match in _COMPARISON_RE.finditer(line):
            if _refusal_shaped(match.group("op"), match.group("expected")):
                found.append(line.strip())
                break
    return found


def _asserts_refusal(block: _Block) -> bool:
    """True when the battery asserts the gate's DISARM direction, not its arm.

    This is the discriminator the SPEC-081 amendment adopted (Option E). The
    knob is read at call time so the suite can neutralise it and prove the rule
    is load-bearing in both directions.
    """
    return (not REQUIRE_REFUSAL_DIRECTION) or bool(_refusal_assertions(block))


# ── Analysis ─────────────────────────────────────────────────────────

#: The gate-free verdict, as ONE module constant rather than a literal re-typed
#: at every assertion site. The suite guards it in the negative ~10 times ("a
#: disarmed run must not read like a clean one"), and a `not in` guard whose
#: literal has drifted from the implementation passes vacuously — review lesson
#: 4's second clause, and lesson 16's "import the oracle, don't re-type it".
#:
#: It says DETECTED, not "no gate-adding change", because the detector cannot
#: know the latter: a gate is seen only inside an added `def` in a changed
#: non-test `.py` file, so a module-level gate, a gate in one of this kit's
#: eight `.sh` scripts, a gate in a source file whose name matches the
#: test-path heuristics, and a tightened predicate in a `class`-hinted hunk are
#: all invisible — and used to print this line byte-identically. Demonstrated
#: on this branch: commit `7949ccb`, authored to harden this very gate, adds
#: four blocking refusals and the detector reported `gates: []` / exit 0.
#: Widening or bounding each boundary is ISSUE-087's; saying only what is known
#: is this PR's (SPEC-081 amendment, decision 3).
GATE_FREE_VERDICT = (
    "PASS: gate-evidence — no gate DETECTED in the diff. A pass means no gate "
    "was detected, NOT that none was added: detection is bounded to an added "
    "`def` in a changed non-test `.py` file (boundary and carrier: SPEC-081 "
    "amendment decision 3 / ISSUE-087)."
)

#: NOT a missing-evidence finding and deliberately not worded like one: no
#: gate was detected in this file, so "add a battery" would be unactionable.
#: It is a refusal to analyse, and it says which file, what the likely cause
#: is, and what the gate would otherwise have printed instead.
_BINARY_RENDERING_MESSAGE = (
    "REFUSED: {path} is a non-test `.py` source file, but this diff renders "
    "it as BINARY rather than as text, so gate detection could not see the "
    "file's contents at all. The usual cause is a committed `.gitattributes` "
    "line giving the path the `-diff` attribute (e.g. `*.py -diff`), which "
    "makes git print a `Binary files ... differ` line in place of every "
    "added line — measured: one such committed line turned this BLOCKING "
    "phase into the ordinary gate-free verdict at exit 0, with no waiver "
    "printed (SPEC-081 amendment 2026-10-24, AC-9.1). This phase therefore "
    "refuses rather than reporting that no gate was detected, because a diff "
    "it cannot read is indistinguishable from a diff with no gate in it. "
    "Re-render with `git diff --text` (the review checkpoint now does), or "
    "drop the `-diff` attribute for this path."
)

_DISARM_MESSAGE = (
    "{symbol} ({path}:{line}) adds a gate and NO added test battery is "
    "attributed to it at all. Add a test that drives {symbol} over at least "
    "{minimum} input variants (value vocabulary, line shape, encoding, "
    "placement, fencing, duplication) whose parameters feed only the input, "
    "and assert it still REFUSES every one."
)

#: The other half of what used to be one finding. Split because the two modes
#: have wildly different reliability: "no attributed battery at all" was 11 of
#: 11 true positives on the measurement corpus, while THIS one carries the
#: direction classifier's measured 16-of-27 per-battery error rate. A reviewer
#: who cannot tell the two apart cannot calibrate either, so the message states
#: the error rate, the mechanisms, and the escape (SPEC-081 amendment, 1).
_UNDIRECTED_MESSAGE = (
    "ADVISORY, does not block (SPEC-081 amendment 2026-10-24, decision 6): "
    "this kind rests on assertion POLARITY, which is not decidable for a "
    "detector-shaped gate, so it is reported and never fails the phase. "
    "{symbol} ({path}:{line}) has {batteries} added battery/batteries "
    "attributed to it, but none of them is recognised as asserting a REFUSAL "
    "— every expected side reads as success (`is True`, `== 0`, `!= False`), "
    "i.e. the gate is evidenced in the ARM direction only, which is the shape "
    "of all four measured fail-opens. Add one assertion in the refusal "
    "direction: `is False`, a non-zero exit code, a refusal constant, or "
    "`pytest.raises`. CAVEAT, measured, not hypothetical: this check reads "
    "assertion polarity LEXICALLY and misreads it often — hand-classified, 16 "
    "of 27 such verdicts were wrong (SPEC-081 amendment, decision 1). For a "
    "DETECTOR-shaped gate the disarm direction is correctly written `assert "
    "detected is True`, which is not lexically decidable at all; refusal by "
    "`is None`, by an empty collection, by probing a violation list, or by a "
    "finding-kind string are equally invisible here. If your battery already "
    "asserts refusal in a form this check cannot see, that is exactly what the "
    "escape is for: add `# GATE-EVIDENCE-EXEMPT({symbol}): <reason naming the "
    "test that carries the refusal>` as a comment in {path} itself."
)

_COMPOSITE_MESSAGE = (
    "ADVISORY, does not block (SPEC-081 amendment 2026-10-24, decision 6): "
    "the composite half asks whether the consumer-level literal is "
    "refusal-shaped, which runs through the same lexical polarity test as the "
    "direction half and is not decidable for a detector-shaped gate, so it is "
    "reported and never fails the phase. "
    "{symbol} ({path}:{line}) is evidenced at the HELPER only — no composite "
    "battery drives it through its real CONSUMER. ISSUE-078 is the motivating "
    "case: the helper's own assertions all passed while `validate` and "
    "`next-action` disagreed with it on the same bytes. Add a battery of at "
    "least {minimum} input variants that asserts a consumer-level outcome (an "
    "exit code or a refusal constant) and carries an input-side vacuity guard "
    "proving each variant still contains what {symbol} is supposed to catch."
)


def _exemptions(files: list[_FileDiff]) -> tuple[tuple[str, str, str], ...]:
    """Inline attestations, as ``(path, symbol, reason)``.

    Four provenance requirements, every one of them a measured defect rather
    than a precaution (SPEC-081 amendment, decision 4 — review lesson 6: shape
    validation is not provenance):

    * **Non-test files only.** A test that merely QUOTES the marker in a
      fixture string silently exempted the symbol in the string. Found by
      dogfooding this gate on its own diff; pinned by
      `test_an_exemption_quoted_in_a_TEST_file_does_not_count`.
    * **``.py`` files only.** There was no suffix filter at all, so the review
      that *documented* this hole committed `docs/review_notes/ISSUE-081.md`
      with a marker naming a real symbol in its prose — and that line waived
      `main` on this branch's own blocking run, moving it from *evidenced* to
      *waived*. Documenting the vulnerability exploited it.
    * **``#``-commented only.** The marker has to sit in a comment with no
      quote character before the ``#``, so SPEC prose inside a fenced block and
      a docstring sentence are both inert. A one-character reason in a fenced
      code block waived a real gate.
    * **Same file as the gate.** The result is keyed ``(path, symbol)`` and
      `analyze` only honours an exemption whose path is the gate's own path. A
      marker in `NOTES.md` waived two same-named gates in two different files
      at once; every validator script in this repo has a `main`.

    The marker stays *honoured, not refused* — the claim SPEC-081 makes is that
    defeating this gate is VISIBLE. Visibility is why the rendered line carries
    the path as well as the symbol: the accidental waiver above did print, as a
    truncated fragment of review prose that reads like nothing in particular.
    """
    found: list[tuple[str, str, str]] = []
    for file in files:
        if not is_scanned_source(file.path):
            continue
        for _, text in file.added:
            match = _EXEMPT_RE.search(text)
            if not match or not match.group("reason").strip():
                continue
            if not _COMMENTED_RE.match(text[: match.start()]):
                continue
            found.append(
                (file.path, match.group(1), match.group("reason").strip())
            )
    return tuple(found)


@dataclass
class _BlockFacts:
    """Everything `analyze` needs to know about ONE battery, computed ONCE.

    Every field depends on the BLOCK alone, and `analyze` used to recompute
    all of them inside its per-gate loop: `_attributed` called
    `_guard_literals(block)` for every (gate, battery) pair, and
    `_asserts_refusal` / `_is_non_vacuous` / `_has_consumer_outcome` were
    evaluated per gate as well. That is the measured quadratic of SPEC-081's
    2026-10-24 amendment, AC-9.2 — 0.05 / 0.20 / 0.64 / 2.22 s at 50 / 100 /
    200 / 400 gates over the matching battery count, ~3.5x per 2x input, with
    the attempt-3 review measuring 32.5 s at 212 KB on a heavier block shape.
    Size alone is not the trigger: the four committed fixtures concatenated
    are 332.7 KB and cost 0.04 s. The gates x batteries PRODUCT is.

    Deliberately NOT a `functools.lru_cache` on the predicates themselves.
    The tunables at the top of this module are read AT CALL TIME precisely so
    the suite can mutate them one at a time and prove each rule is
    load-bearing (AC-5, `_REAL_MUTANTS` and the mutation matrix). A cache that
    outlived one `analyze()` call would let a verdict computed under the real
    rule survive the mutation, the mutant would "survive", and a fix for a
    performance defect would have installed a new fail-open INSIDE the guard.
    The lifetime is exactly one call — these objects are built from blocks
    this call parsed and are dropped when it returns — and
    `TestTheMemoisationDoesNotOutliveOneCall` is what makes that known rather
    than claimed.
    """

    called_names: frozenset[str]
    guard_tokens: tuple[frozenset[str], ...]
    asserts_refusal: bool
    #: `_is_non_vacuous and _has_consumer_outcome`, kept as ONE field so the
    #: short-circuit the per-gate loop had is preserved: a block with no
    #: registering vacuity guard must still not pay for `_CONSUMER_RE`.
    composite: bool


def _block_facts(block: _Block) -> _BlockFacts:
    guard_tokens = _guard_tokens(block)
    return _BlockFacts(
        called_names=_called_names(block),
        guard_tokens=guard_tokens,
        asserts_refusal=_asserts_refusal(block),
        composite=_non_vacuous(guard_tokens) and _has_consumer_outcome(block),
    )


def analyze(diff_text: str) -> Report:
    """Classify a unified diff: which gates it adds, and what evidences them.

    Raises `AnalysisTimeout` — and returns no report at all — when the work
    exceeds `KIT_GATE_EVIDENCE_TIMEOUT` seconds (default
    `DEFAULT_TIMEOUT_SECONDS`). Both consumers fail CLOSED on it; a
    half-finished analysis is not a pass.
    """
    deadline = _Deadline(len(diff_text))

    files = _parse(diff_text)
    gates = detect_gates(files)

    exemptions = _exemptions(files)
    exempted = {(path, symbol) for path, symbol, _ in exemptions}

    blocks, module_text = _blocks(files)
    # One poll for everything above, which is linear in the diff but is still
    # the only work a gate-free, battery-free diff does.
    deadline.check()

    batteries: list[_BlockFacts] = []
    for block in blocks:
        deadline.check()
        if _is_battery(block, module_text):
            batteries.append(_block_facts(block))

    evidence: dict[tuple[str, str], dict[str, bool]] = {}
    # Refusals come first: they say the subject itself could not be read, so a
    # reviewer should see them before any verdict computed over what remained.
    # Scoped to `is_scanned_source` — EXACTLY the paths `detect_gates` reads —
    # because a `.png`, a genuine binary asset or a binary-rendered test file
    # hides nothing from gate detection, and refusing on one would be a false
    # block on an ordinary PR (AC-3).
    findings: list[Finding] = [
        Finding(
            path,
            path,
            number,
            "unreadable-binary-rendering",
            _BINARY_RENDERING_MESSAGE.format(path=path),
        )
        for number, path in _binary_rendered(diff_text)
        if is_scanned_source(path)
    ]
    for gate in gates:
        deadline.check()
        # Tokenised ONCE per gate rather than once per (gate, battery) pair.
        symbol_tokens = _tokens(gate.symbol)
        attributed = [
            facts
            for facts in batteries
            if gate.symbol in facts.called_names
            or _attributed_by(facts.guard_tokens, symbol_tokens)
        ]
        # DIRECTION, not end-to-end-ness. `attributed` alone answers "is there
        # a >= MIN_VARIANTS battery that mentions this gate", which is what
        # `disarm` used to mean and is not what the requirement names.
        disarm = any(facts.asserts_refusal for facts in attributed)
        composite = any(facts.composite for facts in attributed)
        evidence[(gate.path, gate.symbol)] = {
            "disarm": disarm,
            "composite": composite,
        }

        # Keyed on (path, symbol): a marker in one file must not waive a
        # same-named gate in another. Measured naturally on PR #101, where
        # `main` in verify_design_sweeps.py and `main` in verify_hollow_tests.py
        # collapsed into one record — and every validator script here has a
        # `main`.
        if (gate.path, gate.symbol) in exempted:
            continue
        context = {
            "symbol": gate.symbol,
            "path": gate.path,
            "line": gate.line,
            "minimum": MIN_VARIANTS,
            "batteries": len(attributed),
        }
        if not disarm:
            # Two failure modes, named separately because their reliability is
            # not comparable. See `_UNDIRECTED_MESSAGE`.
            kind, template = (
                ("missing-refusal-direction", _UNDIRECTED_MESSAGE)
                if attributed
                else ("missing-disarm-battery", _DISARM_MESSAGE)
            )
            findings.append(
                Finding(
                    gate.symbol,
                    gate.path,
                    gate.line,
                    kind,
                    template.format(**context),
                )
            )
        elif not composite:
            findings.append(
                Finding(
                    gate.symbol,
                    gate.path,
                    gate.line,
                    "missing-composite-pin",
                    _COMPOSITE_MESSAGE.format(**context),
                )
            )

    return Report(gates, tuple(findings), tuple(exemptions), evidence)


def _pass_line(report: Report) -> str:
    """The PASS summary, qualified by everything that makes it less than clean.

    "N gate(s) carry both directions" is a FALSE claim about a gate that only
    escaped the exit code because its finding is advisory, and about a gate
    that was waived. Both are therefore excluded from the count and named in
    their own suffix — a pass that reads the same whether the rule was
    satisfied, merely advised, or waived is the "legitimate quiet output is
    identical to defeated output" failure.
    """
    exempted = {(path, symbol) for path, symbol, _ in report.exemptions}
    # Counted per (path, symbol), so the numbers match the number of gates
    # actually waived / advised. Keyed on the bare symbol, one marker could
    # waive two same-named gates in two files and still print `1 exempted`,
    # under-reporting the blast radius of the waiver — and this PASS line is
    # the artifact SPEC-081's "defeating it is visible" claim rests on.
    keys = {(gate.path, gate.symbol) for gate in report.gates}
    advised = {(f.path, f.symbol) for f in report.advisory_findings}
    evidenced = sorted(symbol for _, symbol in keys - exempted - advised)
    summary = (
        f"PASS: gate-evidence — no BLOCKING finding. {len(evidenced)} gate(s) "
        f"carry both directions: {', '.join(evidenced) or 'none'}"
    )
    noted = sorted(f"{path}:{symbol}" for path, symbol in advised & keys)
    if noted:
        summary += (
            f" | {len(noted)} ADVISORY, NOT blocking and NOT evidenced: "
            f"{', '.join(noted)}"
        )
    charged = sorted(f"{path}:{symbol}" for path, symbol in exempted & keys)
    if charged:
        summary += (
            f" | {len(charged)} exempted, NOT evidenced: {', '.join(charged)}"
        )
    return summary


def format_report(report: Report) -> list[str]:
    """Render a report as the lines the review checkpoint prints.

    Two sections, and which section a finding lands in is read from
    `BLOCKING_KINDS` through `Finding.tier` — never re-decided here. A kind
    that renders as advisory and exits non-zero (or the reverse) would be a
    new fail-open; the renderer therefore names no kind of its own.
    """
    # Path-qualified so the line reads as a deliberate waiver of a specific
    # gate. The accidental `.md` waiver this fix closed DID print; its reason
    # rendered as a truncated fragment of review prose that no reviewer would
    # read as a waiver, which is why visibility alone was not enough.
    lines = [
        f"EXEMPT: {path}:{symbol} — {reason}"
        for path, symbol, reason in report.exemptions
    ]
    # "No gate detected" is only sayable when nothing else was found either.
    # A refusal fires with `gates == ()` by construction — the whole point is
    # that the file could not be read — so an early return keyed on gates
    # alone would print the gate-free verdict over the refusal and return 0.
    if not report.gates and not report.findings:
        lines.append(GATE_FREE_VERDICT)
        return lines

    blocking, advisory = report.blocking_findings, report.advisory_findings

    if blocking:
        # The kind names are read off THIS report's findings, not off
        # `BLOCKING_KINDS`: once the tier holds more than one kind, printing
        # the whole set names kinds the report does not contain and sends a
        # reviewer looking for a finding that is not there. And they are
        # "finding(s)", not "gate(s)" — `unreadable-binary-rendering` is about
        # a file in which NO gate was detected, which is exactly why it
        # refuses.
        kinds = sorted({finding.kind for finding in blocking})
        lines.append(
            f"FAIL: gate-evidence — {len(blocking)} finding(s) in the "
            f"BLOCKING tier ({', '.join(kinds)}) (ISSUE-081 / SPEC-081)"
        )
        lines.extend(f"  - [{f.kind}] {f.message}" for f in blocking)
        # Only when some blocking finding is actually waivable. The inline
        # marker is collected from the gate's OWN file's added lines, so it
        # cannot waive a file whose lines this module never saw — offering it
        # there would be a remedy that silently does nothing. Derived from
        # whether the finding names a detected gate rather than from its kind,
        # because a kind literal here would be a second statement of the tier.
        waivable = {(gate.path, gate.symbol) for gate in report.gates}
        if any((f.path, f.symbol) in waivable for f in blocking):
            lines.append(
                "  Opt out only with an inline `# GATE-EVIDENCE-EXEMPT("
                "<symbol>): <reason>` in the diff, justified in the PR body."
            )
    else:
        lines.append(_pass_line(report))

    # Printed whether or not the blocking tier fired: an advisory finding that
    # only appears on an otherwise-clean run would be invisible exactly when a
    # reviewer is already reading a failure.
    if advisory:
        lines.append(
            f"ADVISORY: gate-evidence — {len(advisory)} finding(s), REPORTED "
            f"and NOT BLOCKING. These kinds rest on assertion polarity, which "
            f"is not decidable for a detector-shaped gate (there, `assert "
            f"detected is True` IS the refusal), so they advise rather than "
            f"block — SPEC-081 amendment 2026-10-24, decision 6."
        )
        lines.extend(f"  - [{f.kind}] {f.message}" for f in advisory)
    return lines


# ── CLI ──────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify that a diff's added gates carry paired evidence"
    )
    parser.add_argument(
        "--diff-file", required=True, help="unified diff to analyze"
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    path = Path(args.diff_file)
    if not path.is_file():
        print(f"ERROR: diff file not found: {path}", file=sys.stderr)
        return 2

    diff_text = path.read_text(encoding="utf-8", errors="replace")
    # Fail CLOSED on input that is not a diff, the same treatment the
    # missing-file path above already gets. `errors="replace"` cannot raise, so
    # a UTF-16 (or raw-byte) file decoded to mojibake, `_parse` found no file
    # headers, and this printed `GATE_FREE_VERDICT` and exited 0 — a PASS over
    # unreadable bytes, byte-identical to a PASS over a clean diff. One `+++ `
    # header is the minimum `_parse` needs to see any file at all, so its
    # absence means nothing could have been detected either way.
    if "+++ " not in diff_text:
        print(
            f"ERROR: {path} decoded to {len(diff_text)} characters with no "
            f"`+++ ` header — not a unified diff (wrong encoding, or not a "
            f"diff at all). Refusing rather than reporting no gate.",
            file=sys.stderr,
        )
        return 2

    # Fail CLOSED on a refusal to evaluate, at the exit code this CLI already
    # uses for one — a timed-out analysis produced no verdict, so it must not
    # render as a PASS and must not be confused with a blocking FINDING
    # either. `BLOCKING_KINDS` keeps exit 1 to itself.
    try:
        report = analyze(diff_text)
    except AnalysisTimeout as timeout:
        print(f"ERROR: {timeout}", file=sys.stderr)
        return 2

    for line in format_report(report):
        print(line)

    # Derived from `BLOCKING_KINDS` via `Finding.tier`, exactly like the
    # rendered section above and like the real consumer's boolean. Three
    # readings of one constant, never three statements of the tier.
    return 1 if report.blocking_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
