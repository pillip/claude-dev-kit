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
