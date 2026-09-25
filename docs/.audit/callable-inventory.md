# Callable inventory

Final AST inventory, excluding ten `typing.overload` declaration stubs:

| Measure | Count |
|---|---:|
| Runtime production callables | 854 |
| Production functions | 754 |
| Production class methods | 100 |
| CLI module runtime functions | 12 |
| Actual top-level CLI commands | 7 |
| Runtime-observed safe-CLI union | 360 |
| Graphify static-incoming candidates | 192 |
| Explained dynamic/framework candidates | 192 |
| Unexplained candidates | 0 |
| Confirmed dead production callables | 0 |
| Maximum observed CLI-to-leaf depth | 31 |

The AST inventory counts every function or method defined under `src/trajcert`, then
excludes only overload declarations that are not runtime implementations. The
Graphify candidate count is not subtracted from the runtime union because dynamic
reachability and direct runtime reachability overlap.

The post-fix extraction was refreshed on 2026-09-25 with Graphify 0.9.64. Its no-cluster
graph contained 1,738 nodes and 7,920 edges. The newer extractor identifies three more
static-incoming candidates than the prior saved summary; the added candidates fall in
the already-reviewed property/method, registry, callback, and typed renderer groups.
