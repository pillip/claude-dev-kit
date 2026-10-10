"""Suite-wide fixtures.

Hermetic-env guard (review hardening, PR #100 / ISSUE-058): the gate
helper ``verify_checkpoint._run_verify_gates`` consults the delegation
layer, which reads ``KIT_GATE_RESULTS_FILE`` / ``KIT_RUN_ID`` from the
ambient environment. Any test that reaches it — directly or transitively —
would otherwise exercise an env-dependent branch it does not control
(e.g. a developer dogfooding the activation flow with
``KIT_GATE_RESULTS_FILE`` exported). Scoped suite-wide, not per-file,
because the consult sits inside a shared helper.
"""

import pytest


@pytest.fixture(autouse=True)
def _hermetic_gate_delegation_env(monkeypatch):
    monkeypatch.delenv("KIT_GATE_RESULTS_FILE", raising=False)
    monkeypatch.delenv("KIT_RUN_ID", raising=False)


@pytest.fixture(autouse=True)
def _hermetic_sprint_dispatch_env(monkeypatch):
    """Clear ``KIT_SPRINT_DISPATCH_ABOVE_WATERMARK`` suite-wide (ISSUE-069).

    The knob widens ``sprint_queue.py``'s autonomous dispatch scope to Board
    issues above the pinned roster boundary, so a value leaking in from a
    developer's shell — or from an earlier test that set it — flips a
    fail-closed default. Scoped suite-wide, not per-file, for the same reason
    as the gate-delegation guard above: the consult sits inside a SHARED helper
    (``cmd_next_action``, reached by every sprint-queue test file, not only the
    one whose fixtures currently emit a ``Roster-Watermark`` field), so the
    reachability argument for a narrower scope holds only for today's fixtures.
    """
    monkeypatch.delenv("KIT_SPRINT_DISPATCH_ABOVE_WATERMARK", raising=False)
