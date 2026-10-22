# Assignment 3: Java solution and verification

## Build and interface

The selected language in `submission.json` is Java. All submitted Java sources use Java 17-compatible syntax and the standard library. No third-party graph algorithm or downloaded dependency is used. All production code is in `src/Java/`. Python is used only for the launch tools, independent test driver and benchmark orchestration. The launcher and GitHub Actions checks target Java only.

Run these commands from the repository root with JDK 17+ and Python 3.12+ on PATH:

```sh
python tools/run.py --setup
python tools/run.py --check
python -m unittest discover -s tools -p "test_*.py"
python tests/run_own_tests.py --full
python tests/benchmark.py --validate-only
python tests/benchmark.py
```

The launcher compiles with `javac --release 17 -encoding UTF-8` into `.build/Java`. Direct compilation and execution are also possible:

```sh
javac --release 17 -encoding UTF-8 -d .build/Java src/Java/*.java
java -Xmx384m -cp .build/Java Main
```

For PowerShell, replace the last shell wildcard command with:

```powershell
$sources = (Get-ChildItem src/Java/*.java).FullName
javac --release 17 -encoding UTF-8 -d .build/Java $sources
java -Xmx384m -cp .build/Java Main
```

`Main` reads UTF-8 JSON Lines and emits exactly one JSON result per input line. The `ping` request still returns `{"status":"ready"}`. All graph state belongs to the current method call; there are no mutable static caches, retained adjacency lists or persistent DSU arrays. Therefore a request cannot change a later request's result. Input/output failures are caught at the process boundary and reported to standard error. The supplied input and JSON conversion logic is retained. Valid assignment inputs are assumed, as specified by the template.

Let `n` be the number of vertices, `m` the number of edges, `q` the number of union operations and `c` the number of connected components. Edge IDs always refer to positions in the original input, including after sorting. Weights fit `int`, but costs and distances use `long`. A forest or DAG path has at most `n-1` edges, so its absolute cost is at most `99999 * 10^9 = 99,999,000,000,000`, safely within signed 64-bit range. Nullable `Long` values distinguish unreachable distances from finite values such as `-1`.

## DSU

Initially each vertex is its own root with size one. `find` follows parent pointers to the representative and compresses the traversed path. To unite two sets, find their representatives, attach the smaller tree to the larger tree, update the surviving root's size and decrease the component count. Update the largest component size only after a successful merge. Append the current pair `[components, largest]` after every operation, including unsuccessful unions.

Invariant: the parent structure is a forest; two vertices have the same representative exactly when prior successful unions connect them. Each root's size is the number of vertices it represents, the component counter is the number of roots and `largest` is the maximum represented size. Compression preserves each vertex's representative. A merge joins exactly two components and changes their total size to the sum. Induction over operations proves every returned state is correct.

Self-unions and repeated unions leave the partition unchanged. With `n=0`, the largest size is zero and the states array is empty. With positive `n` and no operations, there is no initial output state. Union by size prevents unbalanced growth, and path compression gives amortised `O(n + q alpha(n))` time. The DSU arrays use `O(n)` memory and the returned states use `O(q)`, for `O(n+q)` total memory.

## Kruskal minimum spanning forest

Create an ordering of original edge IDs by increasing weight, breaking equal weights by ID for reproducibility. Start a fresh DSU, examine each edge in sorted order and select it only when its endpoints currently have different representatives. Add its original ID and its weight to the result. The final number of DSU components includes isolated vertices.

Invariant: selected edges form a forest that can be extended to a minimum spanning forest. An accepted edge is a minimum-weight edge across a cut between current components; the cut property allows it in an optimum extension. Equivalently, if an optimum extension does not contain that edge, adding it produces a cycle and exchanging a no-lighter edge preserves optimality. Rejected edges join vertices already connected by the forest and would form a cycle. After all edges have been considered, every original edge has endpoints in the same final DSU component. Thus the forest spans every original component, has `n-c` edges and has minimum total cost.

Self-loops are rejected because their endpoints have the same representative. Parallel edges and ties are handled by ordinary sorting and union tests. Negative edges require no special rule. A zero-vertex graph returns cost zero, no edges and zero components. Time is `O(n + m log(m+1))`, including sorting and DSU operations. Input conversion, ordering, DSU and the output take `O(n+m)` memory. Sorting IDs preserves the input edge order and does not change the caller's data.

## Prim minimum spanning forest

Build undirected adjacency lists with original edge IDs. For every unvisited start vertex, increment the component count, visit the start and place its outgoing crossing edges in a min-priority queue. Repeatedly remove the lightest candidate. Discard candidates whose destination has already been visited. Otherwise select the edge, visit its destination and add that vertex's outgoing edges leading to unvisited vertices. Restart from the next unvisited vertex after the queue is exhausted.

Invariant: selected edges within the current component form a tree on the visited vertices. The queue contains all edges crossing from visited vertices to as-yet unvisited vertices, possibly with stale candidates whose destinations have since been visited. Discarding a stale candidate cannot remove a crossing edge. The next accepted candidate has minimum weight across the visited/unvisited cut and is safe by the cut property. It adds one new vertex, so it cannot create a cycle. An exhausted queue means no unvisited vertex is reachable from the current tree. The outer loop therefore produces one minimum tree per component and counts isolated vertices too.

Loops are never selected, because their destination is already visited. Parallel edges, equal weights and negative weights remain valid queue candidates. A fresh queue and visited array are used per request. An empty graph produces an empty forest. Every adjacency entry is considered a constant number of times and the lazy heap holds `O(m)` candidates. Total time is `O(n + m log(m+1))` and memory is `O(n+m)`. This implementation is independent of Kruskal and does not call it.

## Kosaraju strongly connected components

Build outgoing adjacency lists and the transpose. Run DFS over every vertex in the original graph and record a vertex only when all its outgoing neighbours have been processed. The implementation writes each completed vertex into `order[--orderPosition]`, directly producing decreasing finish order. Scan that order and run DFS on the transpose from each still-unlabelled vertex. Give one label to all vertices found in a second-pass traversal. Finally scan the original edges, remove internal SCC edges and insert distinct ordered label pairs into a hash set before producing the condensation array.

First-pass invariant: every active DFS frame stores both its vertex and the next neighbour position. A vertex is appended only after its entire suspended traversal is complete. For two distinct SCCs with an edge from `A` to `B`, the largest finish time in `A` is greater than the largest finish time in `B`. Thus the next unlabelled vertex in decreasing finish order lies in a source SCC of the remaining original condensation graph. That SCC is a sink in the remaining transpose, so its second-pass traversal cannot escape into a different unlabelled SCC. Every member is reached because an SCC remains strongly connected after transposition. This proves that equal labels correspond exactly to maximal mutually reachable sets.

Scanning every original edge includes every required cross-component pair; hashing removes duplicates without adding missing or internal edges. Pair encoding uses both labels without collisions before hashing. Isolates receive separate labels, loops remain internal and duplicate edges do not create duplicate condensation pairs. Empty input gives two empty arrays. Both DFS passes and both adjacency constructions are linear. Hash deduplication gives expected `O(n+m)` time; memory, including graph, transpose, explicit stacks and results, is `O(n+m)`.

## Three-state DFS topological ordering

States are unvisited, active and finished. Start a DFS at every unvisited vertex. Each explicit frame remembers its next neighbour, exactly as a recursive call would. An edge to an unvisited vertex pushes a new frame; an edge to an active vertex reports a cycle; an edge to a finished vertex is safe. When a frame has no remaining neighbours, finish the vertex and write it into `order[--orderPosition]`. This directly constructs reversed finish order, which is returned only if the entire graph is acyclic.

Invariant: active vertices are exactly the current DFS ancestor path. Therefore an edge to an active vertex closes a directed cycle. Conversely, DFS cannot finish exploring a directed cycle without encountering an edge to an active ancestor. When no cycle is found, for every edge `u -> v`, `v` finishes before `u`, either through that DFS descent or because `v` was already finished. Reversing finish order consequently places `u` before `v`. Each vertex is discovered and finished once, so the result is a permutation of all vertices.

The outer loop checks disconnected and isolated components. A self-loop immediately detects a cycle. Duplicate edges to finished vertices are harmless. A zero-vertex graph is acyclic with an empty order. Any cycle discards the partial traversal and returns `false` with an empty order. Retained neighbour positions prevent rescanning high-degree vertices. Time and memory are `O(n+m)`.

## DAG shortest paths and route reconstruction

Run the same three-state topological traversal over the entire weighted graph, using only endpoints for the cycle test. If any component is cyclic, immediately return `acyclic=false` and two empty arrays. Otherwise initialize every distance to `null`, every parent edge to `-1` and the source distance to zero. Traverse vertices in topological order. Skip unreachable vertices. For each outgoing edge of a reachable vertex, compute `distance[u] + weight` in `long`; replace the destination's distance and original parent edge ID only if this candidate strictly improves its distance.

Invariant: when a vertex is processed, its distance is the true shortest distance from the source, or it is unreachable. Every predecessor has already been processed, so all possible last edges of a path to that vertex have already been relaxed. This proves the invariant inductively in topological order. Negative weights do not invalidate it because there are no cycles. A chosen parent edge ends at the destination and comes from a reachable earlier vertex; following parent edges strictly decreases the topological position and eventually reaches the source. Equal candidates leave an already valid witness unchanged. The source retains distance zero and parent `-1`: a reachable incoming edge to it would create a cycle.

Cycles unreachable from the source are still rejected. Disconnected reachable and unreachable regions, negative finite distances, parallel edges and tied shortest routes are supported. DAG inputs always have at least one vertex. The topological pass, initialization and relaxation take `O(n+m)` time and memory, including the output.

`Algorithms.reconstructRoute(source, target, edges, parentEdge)` follows original edge IDs backwards from target to source, collects vertices and reverses the result. It returns `[source]` for the source and an empty list for an unreachable target. The caller supplies a parent array from a successful DAG result. Endpoint and edge-ID checks reject invalid chains; a bound on the number of traversed vertices prevents an infinite loop for a malformed cyclic witness. For a valid route of `L` vertices, only its `L-1` parent edges are examined. Time and output space are `O(L)`, with no full-graph search or fresh `O(n)` visited array per helper call.

## Deep graphs, state reset and verification

All graph DFS traversals use heap-allocated arrays as explicit stacks. There is no recursive graph call and no dependence on Java's call-stack capacity. A chain of 100,000 vertices therefore fits the same linear memory bound as any other graph. First-pass and topological frames retain their progress instead of restarting a neighbour scan. All algorithm arrays, queues, counters and hash sets are local to an invocation. Repeated mixed requests exercise those reset guarantees through the real JSON Lines process.

Detailed test inputs, justified expected answers, captured actual outputs and reproduction commands are kept under `tests/`. The public checker validates non-unique answers semantically; additional independent tests compare optima and witnesses, rather than requiring one arbitrary ordering or SCC labelling.

The custom runner uses seed `314159`. Its independent small-graph references are repeated component traversal for DSU, exhaustive forest enumeration for MST optimum cost, transitive closure for SCC membership, Kahn's algorithm for whole-graph cycle detection and Bellman-Ford relaxation for DAG distances. These differ from the submitted algorithms. The supplied public validator then checks the returned witnesses against those independently computed answers.

| Executed check | Result | Evidence |
|---|---|---|
| Launch and ping | PASS | `tests/public-setup.txt` |
| Public cases | 36/36 PASS | `tests/public-checks.txt` |
| Two complete public batches in one process | PASS | `tests/public-checks.txt` |
| Own cases | 766 PASS: 46 boundary cases and 720 seeded random cases, containing 714 distinct requests | `tests/own_inputs.jsonl`, `own_expected.jsonl`, `own_actual.jsonl` |
| Own mixed request stream | 2,298 PASS: cases, reversed cases, cases in one process | `tests/mixed_actual.jsonl.gz`, `own_results.json` |
| Semantic validator experiments | 41 PASS: 11 valid/alternative witnesses accepted and 30 invalid witnesses rejected | `tests/certificate_checks.jsonl` |
| Direct route-helper calls | 6 PASS | `tests/route_helper_actual.jsonl` |
| Full limits | 9/9 PASS at `n=100000`, `m` or `q=250000` | `tests/*_full.{input,expected,actual}.jsonl.gz`, `own_results.json` |
| Java launcher/transport and validator unit tests | 10/10 PASS, no skipped tests | `tests/tool-checks.txt`; `python -m unittest discover -s tools -p "test_*.py"` |

The full-limit suite covers DSU; both MST algorithms; SCCs as a chain of two-vertex components and a single deep cycle; topological ordering of a long chain with extra forward edges and rejection of a deep cycle; a negative-weight DAG chain and a cycle entirely unreachable from its source. Expected results follow directly from those constructions, with detailed proofs in `tests/README.md`. Each full-limit case has its actual input and output saved using deterministic gzip compression, not only a success message. These correctness checks include JVM startup, JSON parsing and output; their elapsed times are not the algorithm-only benchmark below.

All code is compiled with `--release 17`. Own JSON and helper tests use a small `-Xss256k` stack and a `-Xmx384m` heap to check iterative traversal under the public launcher's memory cap. Local checks used Python 3.14.3; the custom runner records its Python and Java versions in `tests/own_results.json`. Local Java runtime is Oracle JDK 25.0.1. The GitHub Actions workflow is configured to run all checks using Java 17; its remote result is separate from these recorded local runs.

### Actual route-helper calls

`tests/RouteHelperTest.java` calls the helper directly, verifies source and target, checks every selected edge's direction and adds its weight using `long`. The following calls and results were captured in `tests/route_helper_actual.jsonl`.

For `basicEdges = {{0,1,3},{0,2,8},{1,2,-7},{2,3,4}}`, the computed parent array is `basicParents = {-1,0,2,3,-1}`:

| Java call | Actual vertex sequence | Selected original edge IDs | Weight |
|---|---|---|---|
| `Algorithms.reconstructRoute(0, 3, basicEdges, basicParents)` | `[0,1,2,3]` | `[0,2,3]` | `3 + (-7) + 4 = 0` |
| `Algorithms.reconstructRoute(0, 0, basicEdges, basicParents)` | `[0]` | `[]` | `0` |
| `Algorithms.reconstructRoute(0, 4, basicEdges, basicParents)` | `[]` | `[]` | No route; recorded cost is `null` |

For `tiedEdges = {{0,1,5},{0,1,2},{0,2,1},{2,1,1},{1,3,0},{2,3,1},{0,1,2}}`, the computed parents are `tiedParents = {-1,1,2,5}`:

| Java call | Actual vertex sequence | Selected original edge IDs | Weight |
|---|---|---|---|
| `Algorithms.reconstructRoute(0, 3, tiedEdges, tiedParents)` | `[0,2,3]` | `[2,5]` | `1 + 1 = 2` |
| `Algorithms.reconstructRoute(0, 3, tiedEdges, new int[]{-1,6,2,4})` | `[0,1,3]` | `[6,4]` | `2 + 0 = 2` |
| `Algorithms.reconstructRoute(0, 3, tiedEdges, new int[]{-1,3,2,5})` | `[0,2,3]` | `[2,5]` | `1 + 1 = 2` |

Edges 1 and 6 are equal-weight parallel edges. The second call deliberately selects ID 6, proving that reconstruction follows the chosen original ID instead of searching for any edge between two vertices. The last two parent arrays describe valid tied shortest-path witnesses supplied explicitly to the helper. All six direction and cost checks passed.

## Kruskal and Prim benchmark

The full measured report is [tests/benchmark-report.md](tests/benchmark-report.md), with original nanoseconds, input fingerprints and exact process arguments in [tests/benchmark-results.json](tests/benchmark-results.json). Run `python tests/benchmark.py --validate-only` for correctness alone or `python tests/benchmark.py` to repeat measurements. Compilation happens before the measured process and is excluded.

The generator in `tests/Benchmark.java` uses `java.util.Random`, base seed `20261022` and per-graph seed `base + 31*n + m`. Each graph has three nontrivial components and one isolate. Each component contains a planted random tree with weights from `-1000000000` to `-999900001`; additional edges stay inside that component and have nonnegative weights, including possible loops and parallel edges. The complete edge array is shuffled. Removing one planted tree edge defines a cut on which it is uniquely cheapest, so every optimum contains every planted edge. Summing those known weights establishes the optimum independently of either implementation. Before timing, separate breadth-first traversals verify input/selected connectivity, and checks establish edge-ID uniqueness, no loops, `n-c` selected edges and the expected total cost.

| n | m | Graph seed | Verified optimum | Components |
|---:|---:|---:|---:|---:|
| 1,000 | 4,000 | 20296022 | -995949415446 | 4 |
| 10,000 | 40,000 | 20611022 | -9995504392833 | 4 |
| 100,000 | 250,000 | 23611022 | -99991006962082 | 4 |

The experiment ran on 22 October 2026, Windows 11 (10.0.26100), Intel Core i5-11400H at 2.70 GHz, 12 logical processors and 15.73 GiB physical RAM. Compiler: `javac 25.0.1 --release 17`; runtime: Oracle Java HotSpot 64-Bit Server VM `25.0.1+8-LTS-27`; JVM flags: `-Xms256m -Xmx384m`.

`System.nanoTime()` measures the interval immediately surrounding a typed `Algorithms.kruskal(n, edges)` or `Algorithms.prim(n, edges)` call. Both receive the identical preconstructed array; unchanged input is verified before and after measurement. The measured interval includes sorting or adjacency construction, all algorithm allocations and result-map construction. It excludes compilation, JVM startup, input generation/copying, parsing, validation, checksum consumption and all input/output. After an untimed correctness call, each method receives three additional warm-up calls per size. Five samples are collected in one JVM, alternating which method runs first. Returned results are consumed into a volatile checksum after timing. No explicit garbage collection is requested.

All values below are milliseconds, in repetition order. Medians are calculated from the original nanoseconds.

| n / m | Method | Sample 1 | Sample 2 | Sample 3 | Sample 4 | Sample 5 | Median |
|---|---|---:|---:|---:|---:|---:|---:|
| 1,000 / 4,000 | Kruskal | 1.4134 | 1.3231 | 1.4857 | 1.4738 | 1.3199 | 1.4134 |
| 1,000 / 4,000 | Prim | 1.5676 | 1.6367 | 1.8400 | 1.5484 | 1.6014 | 1.6014 |
| 10,000 / 40,000 | Kruskal | 28.5685 | 29.0456 | 12.8960 | 11.4775 | 11.3841 | 12.8960 |
| 10,000 / 40,000 | Prim | 13.5952 | 13.6105 | 14.1985 | 14.7533 | 14.2452 | 14.1985 |
| 100,000 / 250,000 | Kruskal | 141.8891 | 126.9997 | 135.6400 | 120.8570 | 117.7643 | 126.9997 |
| 100,000 / 250,000 | Prim | 164.2663 | 149.5645 | 141.1871 | 147.2450 | 141.7660 | 147.2450 |

At n=1,000, Kruskal had the smaller median by a factor of 1.13. At n=10,000, Kruskal had the smaller median by a factor of 1.10. At n=100,000, Kruskal had the smaller median by a factor of 1.16. Prim builds two undirected adjacency entries per edge and manages a lazy heap; these implementation costs can affect the measured constants. The individual samples show runtime variation, so all samples and medians are retained. These observations do not establish a universal ranking. Both implementations have the derived `O(n + m log(m+1))` bound and `O(n+m)` memory; three measurements cannot prove those bounds.

Limitations: these are three sparse graphs from one structured generator, one JVM, five repetitions and three warm-ups. Dense graphs, other weight distributions and other shapes can behave differently. JIT, garbage collection, CPU frequency, scheduling, caches and background activity can still influence measurements. CPU affinity and operating-system isolation were not configured. The local benchmark describes Java 25 execution, while source/API compatibility targets Java 17.

## Sources

The contracts, allowed algorithms, complexity targets, examples and rubric come from the [assignment template](https://github.com/RZhaniya/daa-assignment-3-graphs), base commit `76c1d91daa90ceadcb225f5408d54d4bfcf397f9`, and the accompanying [assignment PDF](https://github.com/RZhaniya/daa-assignment-3-graphs/blob/76c1d91daa90ceadcb225f5408d54d4bfcf397f9/docs/Assignment_3_EN.pdf). The supplied JSON/input adapters, public checker and launch tools originate from that template. The launcher and its regression tests were narrowed to Java; the public cases and semantic validation logic remain unchanged. No external algorithm implementation was copied and no third-party graph library is used.

All reported tests and measurements were run against the submitted files. Public checks establish observed pass/fail results; they do not assign a grade or submit anything to Moodle.
