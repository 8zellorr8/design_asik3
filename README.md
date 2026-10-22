# DAA Assignment 3: Graph Algorithms in Java

Java 17 implementation of all six assignment algorithms. The solution uses only the Java standard library and requires no downloaded packages. Python runs the checking and benchmark scripts.

## Requirements

- JDK 17 or later, with `java` and `javac` on PATH.
- Python 3.12 or later, with `python` on PATH.

## Build and run

Run from the project root:

```sh
python tools/run.py --setup
python tools/run.py --input tests/own_inputs.jsonl
```

`--setup` compiles the Java sources and verifies the `ping` request. `--input` compiles and executes a UTF-8 JSON Lines file. Each request produces one JSON result line.

After compilation, start the program directly:

```sh
java -Xmx384m -cp .build/Java Main
```

Example input:

```json
{"task":"kruskal","n":4,"edges":[[0,1,4],[1,2,2],[0,2,3]]}
```

## Algorithms

| Task | Implementation |
|---|---|
| `dsu` | Path compression and union by size |
| `kruskal` | Edge sorting and DSU minimum spanning forest |
| `prim` | Adjacency lists and a priority queue, restarting for every component |
| `scc` | Iterative Kosaraju DFS and deduplicated condensation edges |
| `topo` | Iterative three-state DFS with whole-graph cycle detection |
| `dag` | Whole-graph cycle check, topological relaxation and route reconstruction |

Weights and totals use the types required by the assignment; costs and distances use `long`. Deep DFS traversals use explicit stacks. Algorithm state is reset for every request.

## Checks

```sh
python -m unittest discover -s tools -p "test_*.py"
python tools/run.py --check
python tests/run_own_tests.py --full
python tests/benchmark.py --validate-only
```

The public checker covers 36 cases and repeats the batch in one process. Own tests cover 766 cases containing 714 distinct requests, 2,298 mixed requests, alternative and invalid witnesses, direct route-helper calls and nine maximum-size cases. Full-limit inputs have 100,000 vertices and 250,000 edges or operations.

GitHub Actions runs these checks with Java 17 and Python 3.12. The production code is Java; Python files are test and launch utilities.

## Benchmark

```sh
python tests/benchmark.py
```

The benchmark validates Kruskal and Prim on the same graphs at three sizes, then records three warm-ups and five samples per method and size. Compilation and input/output are excluded from measured algorithm time.

## Submission files

```text
.github/workflows/public.yml   GitHub Actions checks
.gitignore                    Generated-file exclusions
submission.json               Java language selection
README.md                     Build, run and submission guide
ANALYSIS.md                   Correctness, complexity, tests and benchmark analysis
src/Java/                     Algorithms and JSON Lines entry point/adapters
tools/                        Public cases, semantic validator and Java launcher tests
tests/                        Own tests, helper, benchmark and recorded evidence
```

The compressed files in `tests/` preserve the required large inputs, expected answers and actual outputs. Generated `.build/`, cache files and `.git/` are excluded from the submission archive.

See [ANALYSIS.md](ANALYSIS.md) for proofs, route examples, measured results and sources. See [tests/README.md](tests/README.md) for independent expected-answer explanations and reproduction commands. The [original assignment specification](https://github.com/RZhaniya/daa-assignment-3-graphs/tree/76c1d91daa90ceadcb225f5408d54d4bfcf397f9) remains available online.

Commit the project contents to your repository and check **Actions > Public checks**. Submit the exact commit URL in Moodle's **Online text** field and click **Submit assignment**. For a private repository, provide the instructor access.
