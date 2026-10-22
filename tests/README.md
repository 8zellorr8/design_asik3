# Own tests and recorded evidence

Run these commands from the repository root with Python 3.12+ and a JDK 17+:

```sh
python -m unittest discover -s tools -p "test_*.py"
python tests/run_own_tests.py --full
python tools/run.py --setup
python tools/run.py --check
python tools/run.py --input tests/own_inputs.jsonl
```

The unit-test command checks the Java launcher, JSON transport and semantic validator. The custom runner compiles the Java submission and direct helper tests with `javac --release 17` into `.build/tests`, checks all results, writes the actual evidence and fails immediately on an error. No packages are downloaded. Compilation has a 60-second timeout; each Java input batch has a 20-second timeout. `python tests/run_own_tests.py` runs the same small, mixed, certificate and helper checks without the nine large cases. It records `own_results_quick.json` and leaves the full-run summary intact.

Every Java process launched by the custom runner uses `-Xmx384m -Xss256k`. The heap cap matches the supplied launcher. Large traversals also demonstrate that graph depth does not require a large Java call stack. The source implementation remains Java; Python is only the independent test driver and oracle.

## Files and results

| File | Contents |
|---|---|
| `tool-checks.txt` | Actual successful output from all 10 Java launcher/transport and validator unit tests |
| `run_own_tests.py` | Deterministic generators, independent expected-value calculations, semantic checks and execution commands |
| `own_inputs.jsonl` | 46 boundary requests followed by 720 generated requests |
| `own_expected.jsonl` | Independently computed expectations, matched by line number |
| `own_actual.jsonl` | Actual Java output for those 766 requests |
| `mixed_actual.jsonl.gz` | All 2,298 outputs from one process: requests, reversed requests, requests again |
| `certificate_checks.jsonl` | 41 actual checker experiments, including the complete input, expectation, submitted witness and acceptance result |
| `RouteHelperTest.java` | Six direct Java helper calls with assertions for endpoints, selected original edge IDs, direction and weight |
| `route_helper_actual.jsonl` | Actual helper call results |
| `*.input.jsonl.gz` | The nine large generated inputs, stored losslessly |
| `*.expected.jsonl.gz` | Corresponding analytical expectations |
| `*.actual.jsonl.gz` | Corresponding actual Java outputs |
| `own_results.json` | Full-run outcome, counts, commands, runtime versions and elapsed times |
| `benchmark-results.json`, `benchmark-report.md` | Separate measured Kruskal/Prim benchmark evidence |

The recorded full run passed 766 cases containing 714 distinct requests, all 2,298 mixed requests, all 41 certificate experiments, all six direct helper calls and all nine full-limit cases. See `own_results.json` for the exact measurements. Full-case elapsed times include JVM startup, input parsing, algorithm execution and output transfer; they are timeout checks, not the separate algorithm benchmark.

Expected files deliberately contain only the reference fields needed by the semantic checker: DSU states, optimal forest cost/component count, SCC partition, topological acyclicity, or DAG acyclicity/distances. They do not require one particular valid witness. `tools/public_validate.py` checks the actual witnesses against these independently obtained references.

## Boundary expectations

Line numbers below refer to `own_inputs.jsonl` and the matching expected/actual files, starting at 1. Pairs of forest cases use the same graph for Kruskal and Prim. Pairs of unweighted directed cases use the same graph for SCC and topological ordering.

| Lines | Input feature | Independently justified result |
|---|---|---|
| 1, 46 | Ping before and after algorithm requests | `status=ready` |
| 2–6 | Empty inputs for DSU, Kruskal, Prim, SCC and topo | Empty arrays; zero forest cost/components; empty graph is acyclic |
| 7–8 | One DSU vertex, no operations or repeated self-unions | `[]`, or `[[1,1],[1,1]]` |
| 9 | Six vertices; repeated unions, self-unions, merges of unequal groups | `[[5,2],[5,2],[4,3],[3,3],[3,3],[2,5],[2,5],[1,6]]` |
| 10–15 | Forest isolates, empty edge sets and negative self-loops | Cost zero; component counts 1, 4 and 1 respectively; no loop is selected |
| 16–17 | Disconnected forest, parallel edges, negative edges and one isolate | The component on 0,1,2 costs -1; the component on 3,4 costs -7; vertex 5 is isolated. Total -8, three components |
| 18–19 | Equal-weight alternatives | Any spanning tree has three edges of weight 1, so optimum cost 3 |
| 20–23 | Positive and negative chains beyond 32 bits | Each chain's four edges are mandatory. Costs are 4,000,000,000 and -4,000,000,000 |
| 24–29 | Directed singleton, five isolates, singleton self-loop | Isolates are separate SCCs; only the self-loop case is cyclic |
| 30–31 | Duplicate cross edges, two nontrivial SCCs, internal self-loop and isolate | SCCs `{0,1}`, `{2,3}`, `{4}`, `{5}`; condensation contains exactly `{0,1}->{2,3}` and `{2,3}->{4}`; cyclic |
| 32–33 | DAG with cross edges to already finished vertices and duplicates | Four singleton SCCs; valid topological order `[0,2,1,3]`; no cycle |
| 34–35 | Directed cycle in a disconnected component | SCCs `{0}`, `{1}`, `{2}`, `{3,4}`; only condensation edge `{0}->{1}`; cyclic |
| 36–37 | DAG singleton and nonzero source among isolates | `[0]`, or `[null,null,0,null,null]`; source parent is -1 |
| 38 | Reachable negative edges and an unreachable vertex | Distances `[0,3,-4,0,null]`; route to 3 costs `3-7+4=0` |
| 39 | Parallel edges and tied shortest routes | Distances `[0,2,1,2]`; multiple parent edge arrays are valid |
| 40 | Nonzero source, finite distance -1, unreachable incoming edge | Distances `[-1,-5,0,null]`; edge 3->1 cannot be relaxed from an unreachable vertex |
| 41–43 | Source self-loop, unreachable two-vertex cycle and unreachable self-loop | All return `acyclic=false` with empty distance/parent arrays |
| 44–45 | Positive and negative weighted DAG chains | Distances are `[0,B,2B,3B,4B]` with `B=1,000,000,000` or `B=-1,000,000,000` |

## Independent random references

The seed is `314159`. There are 120 iterations, each creating one DSU case, one undirected graph submitted to both forest algorithms, one directed graph submitted to both SCC and topo, and one DAG with a shuffled vertex order. Requests are shuffled before execution. Graphs have 1–7 vertices, with duplicates, loops, negative and tied weights possible. Undirected graphs have at most 11 edges, so exhaustive forest enumeration is feasible.

- DSU: after each operation, rebuild the undirected graph and count connected groups using graph traversal. Group sizes give the largest component. This does not use union-find.
- Forests: obtain the original connected groups using graph traversal, then enumerate every subset containing `n-components` non-loop edges. A subset that connects the same groups must be a forest, because a connected graph on each group requires at least its size minus one edges. Minimize its total weight. This does not use Kruskal or Prim.
- SCC: compute the complete reachability relation using Boolean Floyd–Warshall. Vertices belong to the same SCC exactly when each reaches the other. The minimum vertex in each mutual-reachability group is a reference label. This does not use Kosaraju.
- Topo: count vertices removed by Kahn's indegree process. All vertices are removed exactly when the graph is acyclic. This does not use DFS finish order.
- DAG: establish acyclicity with Kahn's algorithm, then use Bellman–Ford relaxation for at most `n-1` rounds to obtain distances. This does not use the submission's topological relaxation.

These reference computations produce `own_expected.jsonl` before the Java process runs. The repeated batch is `cases + reverse(cases) + cases`, so different sizes and task kinds repeatedly follow one another in a single process. All expected values are checked on all three passes.

## Semantic checks and deliberate witness mutations

The checker verifies forest cost, connectivity, edge count, original IDs, uniqueness and absence of cycles; SCC equivalence classes and exact duplicate-free condensation; every topological vertex and precedence relation; and shortest distances together with incoming edge direction, weight equality and parent chains ending at the source.

The 41 recorded experiments accept 11 valid witnesses and reject 30 invalid ones:

- Both forest tasks accept two different tied optimum trees. They reject repeated IDs, loops, wrong edge-weight sums, out-of-range IDs, nonoptimal cost, and a cycle that leaves a vertex disconnected.
- SCC accepts arbitrary relabeling, including a label equal to the maximum signed 64-bit integer. It rejects merging or splitting SCCs, and missing, duplicate, internal or reversed condensation edges.
- Topo accepts both valid orders of two independent starting vertices. It rejects a precedence violation, repeated or missing vertices, and a nonempty order returned for a cycle.
- DAG accepts the original parents, alternative tied routes and an alternative parallel edge ID. It rejects a backwards edge, predecessor vertices mistaken for edge IDs, a nonshortest edge, a missing reachable parent, parents assigned to the source or an unreachable vertex, `-1` in place of unreachable `null`, and nonempty arrays for a cyclic graph.

The complete candidate witnesses and actual Boolean outcomes are retained in `certificate_checks.jsonl`, rather than only reporting an aggregate pass count.

## Full published limits and analytical expectations

Every case below has exactly `n=100000` and `m=250000` (or `q=250000` for DSU). `large_cases()` in `run_own_tests.py` is the complete deterministic generator; no external input or random seed is needed for these cases.

| File prefix | Construction and proof of expected result |
|---|---|
| `dsu_full` | First join consecutive vertices along the chain. After its zero-based operation `i`, components are `n-i-1` and largest is `i+2`. After `n-1` operations all vertices are connected; every remaining self/repeated union leaves `[1,n]` |
| `kruskal_full`, `prim_full` | A chain has all `n-1` edges of weight `-1,000,000,000`. Added edges are loops or positive parallel edges. A spanning tree needs `n-1` edges, every usable weight is at least `-1,000,000,000`, and the chain attains that lower bound: cost `-99,999,000,000,000`, one component |
| `scc_pairs_full` | A forward chain plus the reverse edge inside every adjacent pair. Exactly vertices `2i` and `2i+1` are mutually reachable: no edge goes to an earlier pair. Reference label is `vertex//2`; condensation is the chain of 50,000 labels. Loops and duplicate pair edges add no new reachability |
| `scc_ring_full` | A directed cycle visits every vertex. Every vertex reaches every other, so there is one SCC and no condensation edge. Duplicate ring edges change nothing |
| `topo_chain_full` | A chain of depth 100,000 plus only forward edges. Every edge increases the vertex number; the chain forces order `[0,1,...,99999]` |
| `topo_cycle_full` | The full directed ring contains a cycle, so `acyclic=false` and the order is empty |
| `dag_chain_full` | Chain edge weights are `-B`, with `B=1,000,000,000`; additional edges go forward with weight `+B`. The chain reaches vertex `i` with `-iB`. An additional edge `a->b` gives `-aB+B`, strictly greater than `-bB`, so no shortcut improves the chain. Expected distance is `-iB` |
| `dag_unreachable_cycle_full` | Vertex 0 is an isolated source; vertices 1 through 99,999 form a directed cycle. The entire graph must be rejected although the cycle is unreachable from the source |

The large files are gzip-compressed to keep complete inputs, analytical references and real outputs reasonably small. To inspect one result:

```sh
python -c "import gzip; print(gzip.open('tests/dag_unreachable_cycle_full.actual.jsonl.gz','rt',encoding='utf-8').read())"
```

To rerun one stored large case after the runner has compiled Java:

```sh
python -c "import gzip,sys; sys.stdout.write(gzip.open('tests/topo_chain_full.input.jsonl.gz','rt',encoding='utf-8').read())" | java -Xmx384m -Xss256k -cp .build/tests Main
```

## Actual direct route-helper calls

`RouteHelperTest.java` calls `Algorithms.reconstructRoute(source, target, edges, parentEdge)` directly. Unreachable targets return `[]`. Each selected ID is checked against the original edge array, both endpoints must match the consecutive route vertices, and the sum uses `long`.

For edges `[[0,1,3],[0,2,8],[1,2,-7],[2,3,4]]`, the actual DAG parents are `[-1,0,2,3,-1]`:

| Call | Actual route | Selected original IDs | Verified total |
|---|---|---|---|
| `reconstructRoute(0,3,edges,parentEdge)` | `[0,1,2,3]` | `[0,2,3]` | `3-7+4=0` |
| `reconstructRoute(0,0,edges,parentEdge)` | `[0]` | `[]` | 0 |
| `reconstructRoute(0,4,edges,parentEdge)` | `[]` | `[]` | No route, recorded cost `null` |

For edges `[[0,1,5],[0,1,2],[0,2,1],[2,1,1],[1,3,0],[2,3,1],[0,1,2]]`:

| Parent array passed to the helper | Actual route from 0 to 3 | IDs | Verified total |
|---|---|---|---|
| Actual DAG output `[-1,1,2,5]` | `[0,2,3]` | `[2,5]` | `1+1=2` |
| Valid alternative `[-1,6,2,4]` | `[0,1,3]` | `[6,4]` | `2+0=2` |
| Valid alternative `[-1,3,2,5]` | `[0,2,3]` | `[2,5]` | `1+1=2` |

The explicitly selected parallel edge ID 6 confirms that reconstruction uses edge IDs rather than predecessor vertex numbers. The six actual call records are in `route_helper_actual.jsonl`.

## Benchmark

Run `python tests/benchmark.py` for the separate same-graph Kruskal/Prim experiment. Its command line, generator and seed, correctness checks, warm-up, individual measurements, medians, timing boundary, runtime and hardware are recorded by that runner. See `benchmark-report.md`, `benchmark-results.json` and the root `ANALYSIS.md` for the measured results and limitations.
