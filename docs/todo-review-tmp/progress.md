# Forensic review — final progress

## 0. Workspace state (verified before any edit)

The brief assumed an uncommitted working tree holding the previous agent's work. That
assumption did **not** hold, and this was established before touching a file:

* `git status` → `nothing to commit, working tree clean`; branch `main`.
* `git diff`, `git diff --stat`, `git diff --name-status`, `git diff --cached` → all empty.
* `git stash list` → empty; no untracked files.
* The work was present as three local commits: `351ec22`, `7509eea`, `db67419` (HEAD).
* Source mtimes (2026-09-12 22:00:02–22:00:04) match `db67419`'s commit time (21:59:45),
  so HEAD **is** that work verbatim. Nothing was lost.
* Per the user's decision, git history was left untouched and the audit targets the code.

No destructive command (`reset --hard`, `checkout --`, `restore`, `clean`, `stash`) was run.

## 1. Baseline gates at HEAD (before any edit)

| Gate | Result |
|---|---|
| `basedpyright` (strict, `typeCheckingMode=all`) | 0 errors |
| `tools/source_audit.py` | clean |
| `lint-imports` | 3 contracts kept, 0 broken |
| `semgrep --config semgrep` | clean |
| `ruff check src` | **95 errors** — all `E501` from the appended TODO comments |
| `ruff format --check src` | **21 files would be reformatted** — same cause |
| `pytest` | blocked by a missing `pytest-randomly` in the venv; fixed with `uv sync --extra quality` |

The appended TODO comments therefore *broke* two mandatory gates. Repairing that was the
first act of remediation.

## 2. Marker reconstruction and classification

213 pre-existing markers in three auto-generated templates (149 "should be constant",
55 "do not use primitives", 9 "should be enum"). Each was classified individually because
the template text is not a reliable statement of intent. Full detail in
`original-todo-ledger.md`; summary:

* **149 "constant"** — false positives on mathematical identities (`alpha / 2.0`,
  `(lower + upper) / 2.0`, `rng.integers(0, 2, …)`) and matplotlib styling. Extracting
  constants would violate CLAUDE.md §2 and the project's own `RULE_CONSTANT`.
* **55 "primitives"** — 54 misworded (valid `NewType` domain contracts, all in real use);
  **1 genuine defect cluster**: `FailureBoundaryProbe`.
* **9 "enum"** — 6 false positives (digit literals, already-named constants);
  **3 genuine**: `sys.platform` string comparisons, `NumericSign`.

## 3. Genuine defects fixed

1. `FailureBoundaryProbe = FiniteFloat | PositiveInt` → union of per-axis domain types
   (`Probability`, `TimingContrast`, `InformationNats`, `RiskOffset`, `BandCount`,
   `EventCount`, `OuterMaxNodes`); `FailureBoundaryCoordinate` collapsed from four mutually
   exclusive optionals to one required typed `level`; all six `int(...)`/`float(...)`/
   `str(...)` coercions removed and replaced by explicit fail-fast axis narrowing.
2. `PlatformName` enum + `current_platform()` replacing three raw `sys.platform == "win32"`.
3. `NumericSign` → two-member `StrEnum`.
4. `ToleranceName` → two-member `StrEnum` (`ROOT_ABSOLUTE`, `IDENTITY_ABSOLUTE`).
5. `SearchPhase` → three-member `StrEnum`, plus `BatchPhasePrefix` + `batch_phase()` so the
   two dynamic telemetry phases are no longer built from free-form strings.
6. Duplicated governed tolerance `1e-12` → `_EXACT_AGREEMENT_*` constants.
7. Hardcoded duplicated `0.01` principal-coverage-stress margin → authoritative configured
   `CoverageStressCaseConfig`.
8. `1000.0` unit conversion duplicated at 7 sites → `_runtime_milliseconds()` routed
   through `UnitsConfig.nanoseconds_per_millisecond`.
9. `FailureMessage` carried two concepts (exception messages *and* persisted scientific
   interpretation text, including success sentences such as "the theorem holds"). Split:
   `ScientificInterpretation` now types the six reporting sites; `FailureMessage` remains
   only for genuine failure paths. See `unresolved.md` item 1.

## 4. Verification (final)

| Check | Result |
|---|---|
| `ruff format --check src` | passes, 80 files |
| `ruff check src` | **All checks passed** |
| `basedpyright` strict | **0 errors, 0 warnings** |
| `tools/source_audit.py src/trajcert` | clean (exit 0) |
| `semgrep --config semgrep` | clean (exit 0) |
| `lint-imports` | 3 kept, 0 broken |
| `vulture` at the configured policy (`--min-confidence 100`) | clean (exit 0) |
| `complexipy src/trajcert` | all functions within `max_complexity = 10` |
| `pytest` | **855 passed** (unit + integration + e2e + architecture) |
| Graphify final extraction | 3588 nodes / 88887 edges; **0** production callables or classes with zero inbound links |
| TODO/FIXME/HACK/XXX in `src/` | 0 |

## 5. Method-reliability note

During this session the working tree was observed to lose, between tool calls, edits that
had been written and verified. `types.py` was reset to the pre-remediation state at least
once, as were `paths.py`, `provenance.py`, `plan.py`, `config.py` and
`failure_boundaries.py`. The cause was not identified (the test suite was excluded by
re-running it with an integrity check before and after: sources were unchanged by the run).
Every edit was therefore re-applied and then re-verified, and the final state's source
files were confirmed byte-identical to a checksummed snapshot, with the full suite re-run
against that snapshot and no markers or typings regression. The user was informed.

## 6. Known gaps

* `tools/source_audit.py` skips `types.py` for primitive checks and cannot see
  union-of-primitive aliases; this is why the `FailureBoundaryProbe` defect survived an
  architecture test suite that includes `test_primitive_leaks.py`. Per the user's decision
  the scanner was left untouched; the gap is documented in `type-audit.md`.
* `FailureMessage` dual meaning — **resolved** by splitting out
  `ScientificInterpretation`; see `unresolved.md` item 1.
