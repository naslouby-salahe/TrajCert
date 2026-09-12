# Graphify audit

Fresh AST extraction run against the **final** source tree, after every remediation edit
(probe-union refactor, `PlatformName`, `NumericSign`, `ToleranceName`, `SearchPhase` /
`BatchPhasePrefix`, and the `publication_rows` / `config` de-duplications):

```
graphify update . --force --no-cluster
  AST extraction: 218/218 files (100%)
  Rebuilt (no clustering): 3588 nodes, 88887 edges
```

This is the final-source-state graph. No previous Graphify output was reused.

## Dead / unwired production code

Query of the final graph for every production callable or class node with **zero inbound
links** (`source_file` under `src/trajcert/`, `label` ending in `()` or a class name):

```
production callables/classes with zero inbound links: 0
```

No production function or class is unreachable. Every candidate therefore falls under
`FALSE_POSITIVE` — there was nothing to classify as `TRULY_DEAD` and nothing to wire.

Module-file nodes report zero inbound links by construction (they are linked by
`contains` edges from their parent package), and Pydantic validators and `@property`
accessors are not emitted as separately-called nodes; both were previously recorded as
extractor false positives and remain so.

## Wiring spot-check of the refactored chain

`graphify explain _execute_failure_boundary` confirms the failure-boundary workflow is
fully connected after the refactor (degree 25), with:

```
--> evaluate_failure_boundary()            [calls]
--> evaluate_optimizer_node_budget()       [calls]
--> evaluate_terminal_selection_asymmetry()[calls]
--> _failure_boundary_probe()              [calls] [EXTRACTED]
--> _node_budget_level()                   [calls] [EXTRACTED]
```

The newly introduced narrowing helper is reached, and no old option-null path remains.

## Multigraph diagnostic

```
nodes: 3509                raw_edges: 88887
valid_candidate_edges: 87984
missing_endpoint_edges: 0
dangling_endpoint_edges: 903
self_loop_edges: 3
exact_duplicate_edges: 47802
directed_unique_endpoint_pairs: 29000
directed_same_endpoint_collapsed_edges: 58984
undirected_same_endpoint_collapsed_edges: 59012
producer_suppression_sites: 57
```

These are extractor edge-collapse and inferred-endpoint characteristics, not repository
dead-code findings: `missing_endpoint_edges` is 0, and the duplicate/collapse counts are
dominated by repeated `calls`/`references`/`type` edges to numerical-library symbols.
Combined with the zero-orphan query above, no unexplained unreachable or unwired
production code remains.

## Incremental runs

The graph was also rebuilt at intermediate points (`1983` / `1997` nodes for the
`src`-rooted runs, `3588` for the project-rooted run) so that wiring questions during the
refactor were answered against current code rather than the stale graph. The
project-rooted extraction above is the authoritative final result.
