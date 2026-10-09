# Review Notes — PR #112

## Code Review
_Source: reviewer-degraded_

- **[Medium] Sidecar reader guards have zero kill power in the suite — three mutations survive**
  Evidence: scripts/synthesize_gate_results.py:264-276 (_read_sidecar). Executed mutation probes, each run against tests/test_gate_binding.py + tests/test_gate_delegation.py (the only files exercising this module): (A) delete the `sig_path.resolve().is_relative_to(run_dir_real)` containment check -> 96 passed; (B) delete the `st_size > MAX_SIG_BYTES` cap -> 96 passed; (C) delete the `_HEX_SIG_RE.fullmatch(text)` format check -> 96 passed. The os.replace-failure branch at scripts/synthesize_gate_results.py:368-373 (rename fails -> _BindingRejected('consumed', ...)) is likewise untested. The PR's own AC-5 and review lesson 4 require guards mutation-tested in BOTH directions; the MAC/stale/consumed outcomes are, but the sidecar-internal guards are not.
  Fix: Add negative tests that pin each guard to a mac refusal: (1) .sig as a symlink pointing outside .claude/run/ to a file holding the correct 64-hex digest -> binding-rejected/mac; (2) .sig of MAX_SIG_BYTES+1 bytes whose stripped prefix is a valid digest -> binding-rejected/mac; (3) uppercase-hex and 65-char sidecar bodies -> binding-rejected/mac. For the os.replace branch, make the rename fail (e.g. monkeypatch os.replace to raise OSError) and assert binding-rejected/consumed with no delegated results.

- **[Low] Consumed-marker check runs before containment: filesystem existence probe on attacker-chosen paths and blurred refusal contract**
  Evidence: scripts/synthesize_gate_results.py:307-314 (consumed check) vs :314-320 (containment). Verified live: with KIT_GATE_RESULTS_FILE pointing OUTSIDE .claude/run/, the call raises _BindingRejected('consumed') when a sibling `<path>.consumed` exists anywhere on the filesystem, and GateSynthesisError('must live inside .claude/run/') otherwise — so the reason (binding-rejected vs invalid_results, observable in stdout + telemetry) discloses existence of arbitrary `*.consumed` paths, and `Path.exists()` is evaluated on an uncontained attacker-derived path. Both outcomes degrade safely toward the real gates; the module docstring does document this order, so it is intentional — but the intent is satisfiable with containment first.
  Fix: Move the consumed-marker check to after the containment + is_file checks (still before the MAC and before parse — AC-3's 'checked BEFORE parse' is preserved, and test_consumed_marker_checked_before_parse keeps passing since its fixture lives inside .claude/run/). Update the verification-order line in the _load_results_file docstring and the module docstring to match.

- **[Low] MAX_RESULTS_BYTES is enforced on a pre-read stat, not on the bytes actually read**
  Evidence: scripts/synthesize_gate_results.py:324-329 — `stat = real.stat()` / size check, then `data = real.read_bytes()` as a separate syscall. A writer racing between the two can grow the file arbitrarily; the oversized bytes are then fed to hmac.new() and json.loads() uncapped. Fail direction is safe (forged content still fails the MAC under the unpossessed key; freshness uses the pre-read stat, so a swap can only make a fresh artifact look stale), leaving memory/CPU exhaustion as the only effect — on a branch that is dormant today.
  Fix: After read_bytes(), add `if len(data) > MAX_RESULTS_BYTES: raise GateSynthesisError(...)` (or read via a bounded `f.read(MAX_RESULTS_BYTES + 1)`), making the cap authoritative over the bytes actually processed.

- **[Low] Binding-material strength is not validated at the decide_gate_path boundary**
  Evidence: scripts/synthesize_gate_results.py:439-443 — the keyword-only/no-default signature guarantees binding materials are PRESENT, but nothing rejects weak ones: a future activation wiring passing binding_key=b"" (trivially forgeable HMAC key) or process_start=0.0 (everything fresh) runs silently with binding effectively disabled. Today's only consumer is pinned to a 32-byte key and the module-level start (test_consumer_always_carries_binding_material), so there is no live path — this is hardening for the activation PR the SPEC explicitly defers to.
  Fix: At decide_gate_path entry, refuse non-conforming materials loudly: `if not isinstance(binding_key, (bytes, bytearray)) or len(binding_key) != 32: raise TypeError('binding_key must be 32 bytes')` (and optionally reject process_start <= 0). Extends the 'unbound wiring cannot compile a call' guard from arity to strength.

- **[Low] Coarse-mtime filesystems can spuriously refuse a just-written artifact as stale**
  Evidence: scripts/synthesize_gate_results.py:349-354 compares float st_mtime against a time.time() captured at verify_checkpoint import (scripts/verify_checkpoint.py:25). On filesystems with second-granularity mtime (ext3, FAT, some network mounts), an artifact written in the same second the process started can have st_mtime truncated below process_start and refuse as stale. Fail-closed (real gates run) and unreachable while dormant, but at activation this becomes an intermittent, hard-to-diagnose delegation flake.
  Fix: No code change needed now; record it where the activation PR will see it — e.g. one sentence in the SPEC-058 resolved Open Questions item (producer-side key-handoff design) noting the producer must write the artifact after the consumer process starts and that sub-second mtime granularity is assumed, or compare against floor(process_start) at activation time.

- **[Low] [debt] Debt-ledger harvest: 3 no-trigger KIT-DEBT markers, all pre-existing harvester self-matches (record-only)**
  Evidence: checkpoint --phase debt: total 14 markers, 3 no-trigger (scripts/debt_harvest.py:44, tests/test_debt_harvest.py:27, tests/test_debt_harvest.py:59), 1 malformed (tests/test_debt_harvest.py:35) — all are the harvester's own docstring/format examples and test fixtures; none introduced by or related to the ISSUE-065 diff.
  Fix: No action for this PR; same record-only disposition as ISSUE-036/037/038/039/040/042/044/046/047/056 reviews.

## Security Findings
_Source: reviewer-degraded_

- **[Medium] Consumed-marker existence check runs before containment — filesystem-existence oracle on attacker-chosen paths (incl. arbitrary targets via symlink marker)**
  Evidence: scripts/synthesize_gate_results.py:308-320 — the `consumed_marker.exists()` check (follows symlinks; dangling -> False) executes BEFORE the `real.is_relative_to(run_dir_real)` containment check. PoC confirmed: (a) KIT_GATE_RESULTS_FILE pointed at any path P outside .claude/run/ with an existing `P.consumed` sibling yields the loud `GATE BINDING REJECTED [consumed]` stdout line + reason `binding-rejected`, vs silent `invalid_results` otherwise; (b) a planted symlink `.claude/run/probe.json.consumed -> <target>` probes the TARGET's existence for any absolute path. Always degrades to real gates — one-bit info disclosure per run, readable back via stdout/telemetry (ISSUE-038 class), never a bypass.
  Fix: Check containment BEFORE the consumed marker (the required ordering is only consumed-before-MAC/parse), and use lexists semantics for the marker (`consumed_marker.is_symlink() or consumed_marker.exists()`) so a planted symlink always refuses regardless of target. Pin both with tests: out-of-containment path + .consumed sibling -> invalid_results; symlink marker -> target-independent refusal.

- **[Medium] New sidecar containment guard is unpinned — deleting it leaves all 96 tests green (mutation survives)**
  Evidence: scripts/synthesize_gate_results.py:265-266 (`if not sig_path.resolve().is_relative_to(run_dir_real): return None`). Mutation test during review: removed these two lines, reran tests/test_gate_binding.py + tests/test_gate_delegation.py -> 96/96 passed. Neither suite has any symlink test for artifact, .sig, or .consumed paths (only the pre-existing telemetry symlink tests). No current exploit (the MAC blocks delegation regardless), hence Medium-capped, but the guard is unenforced against future refactors — contrary to the kit's mutation-test-both-directions lesson in a PR whose deliverable IS the binding layer.
  Fix: Add a binding-suite test: `<artifact>.sig` as a symlink to an outside-run-dir file containing the CORRECT hex digest for the artifact under the test key -> assert ("degraded", None, "binding-rejected") naming mac. Verified this direction fails without the guard. Also add artifact-as-symlink-escaping-run-dir -> invalid_results.

- **[Low] Freshness leg is attacker-settable (os.utime) — document it as non-load-bearing so the activation PR cannot lean on it**
  Evidence: scripts/synthesize_gate_results.py:351-354 compares `stat.st_mtime < process_start`; any artifact writer can utime the mtime forward (the suite itself backdates via os.utime, tests/test_gate_binding.py:316). Against a malicious producer freshness buys nothing — replay/forgery resistance rests entirely on the MAC + consume-once. SPEC-058's resolution bullet and the module docstring present freshness as one of three binding legs without stating this asymmetry.
  Fix: One doc sentence in SPEC-058 and the module docstring: mtime is trivially forgeable; freshness is an accident guard only. No code change.

- **[Low] stat-then-read TOCTOU on artifact and sidecar — size cap / regular-file check not enforced at read time (local-race DoS only)**
  Evidence: scripts/synthesize_gate_results.py:321-329 and 267-271: is_file/stat-size then a separate read_bytes/read_text; a concurrent local writer can swap in an oversized file (unbounded read) or FIFO (checkpoint hangs) in the window. No integrity impact — MAC and parse use the exact bytes read. Theoretical: needs an active concurrent local process, outside the planted-content model.
  Fix: Single-fd read: os.open(O_RDONLY|O_NOFOLLOW), fstat the fd for S_ISREG + size, bounded os.read(cap+1) refusing overage; same for the sidecar. Also removes the residual resolve-to-read symlink-swap window.

## Over-Engineering

- **[Low] [delete] Dead `except GateSynthesisError: raise` clause in _load_results_file**
  Evidence: scripts/synthesize_gate_results.py:330-331 — the handler below was narrowed to `except OSError` only, and GateSynthesisError (a ValueError) propagates past it unaided; the re-raise guard only mattered when the old clause caught `ValueError`.
  Fix: Delete the two-line clause.

- **[Low] [shrink] test_gate_binding.py duplicates _sign/_decide helpers already defined in test_gate_delegation.py**
  Evidence: tests/test_gate_binding.py:85-118 vs tests/test_gate_delegation.py:92-106 — byte-for-byte-equivalent helpers with a key kwarg; the binding file already imports tgd for the pins, so the second copies only add drift surface.
  Fix: Reuse tgd._sign(path, key) / tgd._decide(project, key=..., process_start=...).

- **[Low] [shrink] Four identical 2-line _setenv methods across binding test classes**
  Evidence: tests/test_gate_binding.py:228,307,370,444 — the same `monkeypatch.setenv + tgd._probe(monkeypatch, 2)` pair repeated per class.
  Fix: One module-level _setenv(project, monkeypatch, path) helper beside _decide.
