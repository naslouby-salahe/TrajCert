# TrajCert Audit Index

This directory holds the current audit record. The requirement-by-requirement matrix remains canonical in [the repository audit matrix](../Audit%20Matrix.md); it is linked here rather than copied so there is one source of truth.

## Scope

The review covers the mathematical contract, experiment design, statistical claims, dataset scope, implementation wiring, reproducibility, and reviewer-facing limitations. No public scientific `trajcert run` was invoked. The HITL-IoT CSV is an optional external diagnostic input; TrajCert does not bundle a dataset.

## Audit notes

- [Scientific decisions](Scientific%20Decisions.md): contribution boundary, claim language, and decisions made during review.
- [Reviewer audit](Reviewer%20Audit.md): likely objections and actions needed before a paper submission.
- [POC results](POC%20Results.md): reproducible checks of the optional raw HITL-IoT file and configured support gates.
- [Progress](Progress.md): completed checks, implementation changes, and remaining work.

The detailed source ledger and earlier supporting audit notes are in [`docs/.audit/`](../.audit/).
