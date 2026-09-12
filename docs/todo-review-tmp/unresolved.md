# Unresolved items requiring the user's decision

## 1. `FailureMessage` dual meaning — RESOLVED

```text
File                  src/trajcert/types.py
Symbol                FailureMessage
Original TODO         "do not use primitives. Fix by introducing a proper error type or
                       message class and identify and fix why architecture tests didn't
                       catch this"
Observed defect       A structured error record already existed
                      (experiments/models.py: FailureDiagnostic{exception_class, message,
                      traceback} inside FailureRecord), so that half of the TODO was
                      already satisfied. The real defect was that the SAME alias carried
                      two unrelated concepts:
                        (a) exception/validation failure text — runner.FailureMessage(str(exc)),
                            scaling worker `failure`, analysis vector-validation messages;
                        (b) persisted scientific interpretation text — the publication row
                            fields `scientific_consequence` and `scientific_interpretation`
                            and the `_state_interpretation` table.
                      Use (b) was actively misnamed: those sentences state success as often
                      as failure ("the theorem holds under configured conditions", "risk
                      upper is within the configured budget" for ScientificState.CERTIFIED).
User decision         Split the alias; keep FailureMessage for exception/error messages and
                      introduce a distinct alias for the interpretation text.
Action taken          Added `ScientificInterpretation = NewType("ScientificInterpretation",
                      str)` to types.py and re-typed the six reporting sites
                      (publication_rows.py: the two row fields, the theorem-consequence
                      builder and its two constructors, and `_state_interpretation` plus its
                      constructor). FailureMessage now appears only in genuine failure
                      paths: experiments/models.py FailureDiagnostic, experiments/runner.py,
                      experiments/scaling.py worker envelope, analysis/vectors.py,
                      analysis/bootstrap.py, analysis/sign_flip.py.
Verification          855 tests pass; ruff, strict basedpyright, source_audit, semgrep,
                      lint-imports, vulture and complexipy all clean. Persisted string
                      values are unchanged, so no artifact is invalidated.
Status                RESOLVED
```

## 2. Scanner gap — RESOLVED_NO_CHANGE (documented)

```text
File                  tools/source_audit.py
Symbol                _AuditVisitor._check_primitive_leak
Original TODO         "...and identify and fix why architecture tests didn't catch this"
Observed issue        types.py is skipped entirely (line 239), and the primitive rule only
                      matches annotations literally containing int|float|str|Any|object, so
                      `FailureBoundaryProbe = FiniteFloat | PositiveInt` was invisible to
                      tests/architecture/test_primitive_leaks.py.
User decision         Leave the scanner untouched; rely on the fixed source.
Status                RESOLVED_NO_CHANGE, recorded in type-audit.md as a known limitation.
```

## 3. Error-record struct is already correct

`FailureDiagnostic` + `FailureRecord` in `experiments/models.py` already form the structured
error record the TODO asked for. No new record type was invented; only the misnamed
interpretation text was separated out (item 1).
