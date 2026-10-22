import argparse
import copy
import gzip
import itertools
import json
import platform
import random
import subprocess
import sys
import time
from collections import Counter, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
BUILD = ROOT / ".build" / "tests"
SEED = 314159
sys.path.insert(0, str(ROOT / "tools"))
from public_validate import check


def encode(value):
    return json.dumps(value, separators=(",", ":"))


def save_lines(path, values):
    text = "".join(encode(value) + "\n" for value in values)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    else:
        path.write_text(text, encoding="utf-8")


def connected_groups(n, pairs):
    adjacency = [[] for _ in range(n)]
    for left, right in pairs:
        adjacency[left].append(right)
        adjacency[right].append(left)
    remaining = set(range(n))
    groups = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        group = {start}
        pending = [start]
        while pending:
            for other in adjacency[pending.pop()]:
                if other in remaining:
                    remaining.remove(other)
                    group.add(other)
                    pending.append(other)
        groups.append(group)
    return groups


def reference(request):
    task = request["task"]
    if task == "ping":
        return {"status": "ready"}
    n = request["n"]
    if task == "dsu":
        states = []
        prefix = []
        for operation in request["operations"]:
            prefix.append(operation)
            groups = connected_groups(n, prefix)
            states.append([len(groups), max(map(len, groups), default=0)])
        return {"states": states}
    edges = request["edges"]
    if task in ("kruskal", "prim"):
        groups = connected_groups(n, [(a, b) for a, b, _ in edges])
        count = n - len(groups)
        candidates = [index for index, edge in enumerate(edges) if edge[0] != edge[1]]
        best = None
        for ids in itertools.combinations(candidates, count):
            selected = [(edges[index][0], edges[index][1]) for index in ids]
            if len(connected_groups(n, selected)) == len(groups):
                cost = sum(edges[index][2] for index in ids)
                if best is None or cost < best:
                    best = cost
        return {"cost": best if best is not None else 0, "components": len(groups)}
    if task == "scc":
        reach = [[a == b for b in range(n)] for a in range(n)]
        for a, b in edges:
            reach[a][b] = True
        for middle in range(n):
            for start in range(n):
                if reach[start][middle]:
                    for end in range(n):
                        reach[start][end] |= reach[middle][end]
        labels = [min(b for b in range(n) if reach[a][b] and reach[b][a]) for a in range(n)]
        return {"component": labels}
    adjacency = [[] for _ in range(n)]
    indegree = [0] * n
    for edge in edges:
        adjacency[edge[0]].append(edge[1])
        indegree[edge[1]] += 1
    pending = deque(vertex for vertex in range(n) if indegree[vertex] == 0)
    visited = 0
    while pending:
        vertex = pending.popleft()
        visited += 1
        for other in adjacency[vertex]:
            indegree[other] -= 1
            if indegree[other] == 0:
                pending.append(other)
    acyclic = visited == n
    if task == "topo" or not acyclic:
        return {"acyclic": acyclic}
    distance = [None] * n
    distance[request["source"]] = 0
    for _ in range(n - 1):
        changed = False
        for a, b, weight in edges:
            if distance[a] is not None:
                candidate = distance[a] + weight
                if distance[b] is None or candidate < distance[b]:
                    distance[b] = candidate
                    changed = True
        if not changed:
            break
    return {"acyclic": True, "distance": distance}


def boundary_cases():
    requests = [{"task": "ping"}]
    for task in ("dsu", "kruskal", "prim", "scc", "topo"):
        requests.append({"task": task, "n": 0, "operations" if task == "dsu" else "edges": []})
    requests.extend([
        {"task": "dsu", "n": 1, "operations": []},
        {"task": "dsu", "n": 1, "operations": [[0, 0], [0, 0]]},
        {"task": "dsu", "n": 6, "operations": [[0, 1], [1, 0], [1, 2], [3, 4], [4, 4], [2, 4], [5, 5], [4, 5]]},
    ])
    forests = [
        (1, []),
        (4, []),
        (1, [[0, 0, -1000000000], [0, 0, 3]]),
        (6, [[0, 0, -99], [0, 1, 8], [0, 1, -3], [1, 2, 2], [0, 2, 2], [3, 4, -7], [3, 4, -7]]),
        (4, [[0, 1, 1], [1, 2, 1], [0, 2, 1], [2, 3, 1], [1, 3, 1]]),
        (5, [[i, i + 1, 1000000000] for i in range(4)]),
        (5, [[i, i + 1, -1000000000] for i in range(4)]),
    ]
    for n, edges in forests:
        for task in ("kruskal", "prim"):
            requests.append({"task": task, "n": n, "edges": edges})
    directed = [
        (1, []),
        (5, []),
        (1, [[0, 0]]),
        (6, [[0, 1], [1, 0], [1, 2], [0, 2], [1, 2], [2, 3], [3, 2], [3, 4], [4, 4]]),
        (4, [[0, 1], [0, 2], [2, 1], [1, 3], [2, 3], [0, 1]]),
        (5, [[0, 1], [3, 4], [4, 3]]),
    ]
    for n, edges in directed:
        for task in ("scc", "topo"):
            requests.append({"task": task, "n": n, "edges": edges})
    requests.extend([
        {"task": "dag", "n": 1, "source": 0, "edges": []},
        {"task": "dag", "n": 5, "source": 2, "edges": []},
        {"task": "dag", "n": 5, "source": 0, "edges": [[0, 1, 3], [0, 2, 8], [1, 2, -7], [2, 3, 4]]},
        {"task": "dag", "n": 4, "source": 0, "edges": [[0, 1, 5], [0, 1, 2], [0, 2, 1], [2, 1, 1], [1, 3, 0], [2, 3, 1], [0, 1, 2]]},
        {"task": "dag", "n": 4, "source": 2, "edges": [[2, 0, -1], [0, 1, -4], [3, 1, -100]]},
        {"task": "dag", "n": 1, "source": 0, "edges": [[0, 0, 0]]},
        {"task": "dag", "n": 5, "source": 0, "edges": [[0, 1, 1], [3, 4, -1], [4, 3, 0]]},
        {"task": "dag", "n": 4, "source": 0, "edges": [[0, 1, 1], [3, 3, 0]]},
        {"task": "dag", "n": 5, "source": 0, "edges": [[i, i + 1, 1000000000] for i in range(4)]},
        {"task": "dag", "n": 5, "source": 0, "edges": [[i, i + 1, -1000000000] for i in range(4)]},
        {"task": "ping"},
    ])
    return requests


def random_cases():
    rng = random.Random(SEED)
    requests = []
    for _ in range(120):
        n = rng.randrange(1, 8)
        operations = [[rng.randrange(n), rng.randrange(n)] for _ in range(rng.randrange(17))]
        requests.append({"task": "dsu", "n": n, "operations": operations})
        weighted = [[rng.randrange(n), rng.randrange(n), rng.randrange(-9, 10)] for _ in range(rng.randrange(12))]
        for task in ("kruskal", "prim"):
            requests.append({"task": task, "n": n, "edges": weighted})
        directed = [[rng.randrange(n), rng.randrange(n)] for _ in range(rng.randrange(17))]
        for task in ("scc", "topo"):
            requests.append({"task": task, "n": n, "edges": directed})
        order = list(range(n))
        rng.shuffle(order)
        dag_edges = []
        if n > 1:
            for _ in range(rng.randrange(17)):
                a, b = sorted(rng.sample(range(n), 2))
                dag_edges.append([order[a], order[b], rng.randrange(-9, 10)])
        requests.append({"task": "dag", "n": n, "source": rng.randrange(n), "edges": dag_edges})
    rng.shuffle(requests)
    return requests


def large_cases():
    n, limit = 100000, 250000
    operations = [[i, i + 1] for i in range(n - 1)]
    operations.extend([[i % n, (i * 37 + 11) % n] if i % 3 else [i % n, i % n] for i in range(limit - len(operations))])
    states = [[n - i - 1, i + 2] for i in range(n - 1)] + [[1, n]] * (limit - n + 1)
    yield "dsu_full", {"task": "dsu", "n": n, "operations": operations}, {"states": states}
    weighted = [[i, i + 1, -1000000000] for i in range(n - 1)]
    for i in range(limit - len(weighted)):
        a = i % (n - 1)
        weighted.append([a, a, -1000000000] if i % 5 == 0 else [a, a + 1, 1000000000])
    for task in ("kruskal", "prim"):
        yield task + "_full", {"task": task, "n": n, "edges": weighted}, {"cost": -(n - 1) * 1000000000, "components": 1}
    pairs = [[i, i + 1] for i in range(n - 1)]
    pairs.extend([[i + 1, i] for i in range(0, n, 2)])
    pairs.extend([[i % n, i % n] if i % 2 else [2 * (i % (n // 2)), 2 * (i % (n // 2)) + 1] for i in range(limit - len(pairs))])
    yield "scc_pairs_full", {"task": "scc", "n": n, "edges": pairs}, {"component": [i // 2 for i in range(n)]}
    ring = [[i, (i + 1) % n] for i in range(n)]
    ring.extend([[i % n, (i + 1) % n] for i in range(limit - n)])
    yield "scc_ring_full", {"task": "scc", "n": n, "edges": ring}, {"component": [0] * n}
    forward = [[i, i + 1] for i in range(n - 1)]
    for i in range(limit - len(forward)):
        a = (i * 37) % (n - 1)
        b = a + 1 + ((i * 13) % (n - a - 1))
        forward.append([a, b])
    yield "topo_chain_full", {"task": "topo", "n": n, "edges": forward}, {"acyclic": True}
    yield "topo_cycle_full", {"task": "topo", "n": n, "edges": ring}, {"acyclic": False}
    dag_edges = [[a, b, -1000000000 if index < n - 1 else 1000000000] for index, (a, b) in enumerate(forward)]
    yield "dag_chain_full", {"task": "dag", "n": n, "source": 0, "edges": dag_edges}, {"acyclic": True, "distance": [-i * 1000000000 for i in range(n)]}
    outside_cycle = [[i, i + 1, -1] for i in range(1, n - 1)] + [[n - 1, 1, 0]]
    outside_cycle.extend([[1, 2, 0]] * (limit - len(outside_cycle)))
    yield "dag_unreachable_cycle_full", {"task": "dag", "n": n, "source": 0, "edges": outside_cycle}, {"acyclic": False}


def certificate_experiments():
    records = []
    def verify(name, request, answer, expected, accepted):
        observed = check(request, answer, expected)
        if observed != accepted:
            raise AssertionError("certificate test failed: " + name)
        records.append({"case": name, "input": request, "expected": expected, "answer": answer,
                        "expected_acceptance": accepted, "actual_acceptance": observed, "passed": True})
    for task in ("kruskal", "prim"):
        request = {"task": task, "n": 3, "edges": [[0, 1, 1], [1, 2, 1], [0, 2, 1], [0, 0, -9], [0, 2, 5]]}
        expected = {"cost": 2, "components": 1}
        for name, answer, accepted in [
            ("valid_original", {"cost": 2, "components": 1, "edge_ids": [0, 1]}, True),
            ("valid_alternative", {"cost": 2, "components": 1, "edge_ids": [2, 0]}, True),
            ("duplicate_id", {"cost": 2, "components": 1, "edge_ids": [0, 0]}, False),
            ("selected_loop", {"cost": 2, "components": 1, "edge_ids": [0, 3]}, False),
            ("wrong_weight_sum", {"cost": 2, "components": 1, "edge_ids": [0, 4]}, False),
            ("out_of_range_id", {"cost": 2, "components": 1, "edge_ids": [0, 5]}, False),
            ("non_optimal", {"cost": 6, "components": 1, "edge_ids": [0, 4]}, False),
        ]:
            verify(task + "_" + name, request, answer, expected, accepted)
        disconnected = {"task": task, "n": 4, "edges": [[0, 1, 1], [1, 2, 1], [2, 0, 1], [2, 3, 1]]}
        verify(task + "_cycle_and_missing_vertex", disconnected,
               {"cost": 3, "components": 1, "edge_ids": [0, 1, 2]}, {"cost": 3, "components": 1}, False)
    request = {"task": "scc", "n": 5, "edges": [[0, 1], [1, 0], [1, 2], [0, 2], [2, 3], [3, 2]]}
    expected = {"component": [0, 0, 2, 2, 4]}
    valid = {"component": [17, 17, 99, 99, 42], "condensation": [[17, 99]]}
    verify("scc_alternative_labels", request, valid, expected, True)
    alternative = {"component": [9223372036854775807, 9223372036854775807, 0, 0, 7], "condensation": [[9223372036854775807, 0]]}
    verify("scc_signed64_labels", request, alternative, expected, True)
    for name, field, value in [
        ("merged_components", "component", [17, 17, 17, 17, 42]),
        ("split_component", "component", [17, 18, 99, 99, 42]),
        ("missing_condensation", "condensation", []),
        ("duplicate_condensation", "condensation", [[17, 99], [17, 99]]),
        ("internal_condensation", "condensation", [[17, 99], [17, 17]]),
        ("reversed_condensation", "condensation", [[99, 17]]),
    ]:
        bad = copy.deepcopy(valid)
        bad[field] = value
        verify("scc_" + name, request, bad, expected, False)
    request = {"task": "topo", "n": 4, "edges": [[0, 2], [1, 2], [2, 3]]}
    expected = {"acyclic": True}
    for name, order, accepted in [
        ("original", [0, 1, 2, 3], True),
        ("alternative", [1, 0, 2, 3], True),
        ("precedence_violation", [0, 2, 1, 3], False),
        ("duplicate_vertex", [0, 0, 2, 3], False),
        ("missing_vertex", [0, 1, 2], False),
    ]:
        verify("topo_" + name, request, {"acyclic": True, "order": order}, expected, accepted)
    cycle = {"task": "topo", "n": 2, "edges": [[0, 1], [1, 0]]}
    verify("topo_cyclic_nonempty_order", cycle, {"acyclic": False, "order": [0, 1]}, {"acyclic": False}, False)
    request = {"task": "dag", "n": 5, "source": 0, "edges": [[0, 1, 2], [0, 2, 1], [2, 1, 1], [1, 3, 0], [2, 3, 1], [0, 1, 2], [0, 3, 20]]}
    expected = {"acyclic": True, "distance": [0, 2, 1, 2, None]}
    valid = {"acyclic": True, "distance": expected["distance"], "parent_edge": [-1, 0, 1, 3, -1]}
    verify("dag_original", request, valid, expected, True)
    for name, parents, accepted in [
        ("alternative_tied_paths", [-1, 2, 1, 4, -1], True),
        ("alternative_parallel_edge", [-1, 5, 1, 3, -1], True),
        ("wrong_direction", [-1, 0, 1, 1, -1], False),
        ("predecessor_instead_of_edge", [-1, 0, 0, 1, -1], False),
        ("nonshortest_edge", [-1, 0, 1, 6, -1], False),
        ("missing_reachable_parent", [-1, 0, 1, -1, -1], False),
        ("parent_for_source", [0, 0, 1, 3, -1], False),
        ("parent_for_unreachable", [-1, 0, 1, 3, 2], False),
    ]:
        answer = copy.deepcopy(valid)
        answer["parent_edge"] = parents
        verify("dag_" + name, request, answer, expected, accepted)
    wrong = copy.deepcopy(valid)
    wrong["distance"][4] = -1
    verify("dag_minus_one_is_not_null", request, wrong, expected, False)
    cycle = {"task": "dag", "n": 3, "source": 0, "edges": [[1, 2, 0], [2, 1, 0]]}
    verify("dag_cyclic_nonempty_arrays", cycle, {"acyclic": False, "distance": [0, None, None], "parent_edge": [-1, -1, -1]}, {"acyclic": False}, False)
    return records


def compile_java():
    BUILD.mkdir(parents=True, exist_ok=True)
    command = ["javac", "--release", "17", "-encoding", "UTF-8", "-d", BUILD.relative_to(ROOT).as_posix()]
    command.extend(path.relative_to(ROOT).as_posix() for path in sorted((ROOT / "src" / "Java").glob("*.java")))
    command.append((TESTS / "RouteHelperTest.java").relative_to(ROOT).as_posix())
    subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
    return command


def run_batch(requests, expected, timeout=20):
    payload = "".join(encode(request) + "\n" for request in requests)
    start = time.perf_counter()
    result = subprocess.run(["java", "-Xmx384m", "-Xss256k", "-cp", BUILD.relative_to(ROOT).as_posix(), "Main"], input=payload,
                            cwd=ROOT, text=True, encoding="utf-8", capture_output=True, timeout=timeout, check=True)
    elapsed = time.perf_counter() - start
    lines = result.stdout.splitlines()
    if len(lines) != len(requests):
        raise AssertionError(f"Expected {len(requests)} JSON output lines, received {len(lines)}. stderr: {result.stderr}")
    answers = [json.loads(line) for line in lines]
    for index, (request, answer, target) in enumerate(zip(requests, answers, expected)):
        if not check(request, answer, target):
            raise AssertionError(f"Case {index} ({request['task']}) failed: {encode(answer)[:500]}")
    if result.stderr:
        raise AssertionError("Unexpected standard error: " + result.stderr)
    return answers, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    compile_command = compile_java()
    certificate_records = certificate_experiments()
    save_lines(TESTS / "certificate_checks.jsonl", certificate_records)
    cases = boundary_cases() + random_cases()
    targets = [reference(request) for request in cases]
    mixed = cases + list(reversed(cases)) + cases
    mixed_targets = targets + list(reversed(targets)) + targets
    save_lines(TESTS / "own_inputs.jsonl", cases)
    save_lines(TESTS / "own_expected.jsonl", targets)
    actual, mixed_seconds = run_batch(mixed, mixed_targets)
    save_lines(TESTS / "own_actual.jsonl", actual[:len(cases)])
    save_lines(TESTS / "mixed_actual.jsonl.gz", actual)
    helper = subprocess.run(["java", "-Xmx384m", "-Xss256k", "-cp", BUILD.relative_to(ROOT).as_posix(), "RouteHelperTest"],
                            cwd=ROOT, check=True, capture_output=True, text=True, timeout=20)
    helper_records = [json.loads(line) for line in helper.stdout.splitlines()]
    if len(helper_records) != 6 or not all(record["passed"] for record in helper_records):
        raise AssertionError("Expected six successful direct route-helper calls")
    save_lines(TESTS / "route_helper_actual.jsonl", helper_records)
    large_records = []
    if args.full:
        for name, request, target in large_cases():
            save_lines(TESTS / (name + ".input.jsonl.gz"), [request])
            save_lines(TESTS / (name + ".expected.jsonl.gz"), [target])
            answer, elapsed = run_batch([request], [target])
            save_lines(TESTS / (name + ".actual.jsonl.gz"), answer)
            record = {"case": name, "task": request["task"], "n": request["n"],
                      "m_or_q": len(request.get("operations", request.get("edges", []))),
                      "seconds_including_jvm_parse_and_output": round(elapsed, 6), "passed": True}
            large_records.append(record)
            print(encode(record), flush=True)
    summary = {"status": "passed", "seed": SEED, "boundary_cases": len(boundary_cases()),
               "random_cases": len(random_cases()), "case_count": len(cases),
               "unique_cases": len({json.dumps(case, sort_keys=True, separators=(",", ":")) for case in cases}),
               "mixed_requests_one_process": len(mixed), "mixed_repetition_pattern": "cases + reverse(cases) + cases",
               "mixed_seconds_including_jvm_parse_and_output": round(mixed_seconds, 6),
               "counts_by_task": dict(Counter(request["task"] for request in cases)),
               "certificate_experiments": len(certificate_records),
               "accepted_alternative_or_valid_witnesses": sum(record["actual_acceptance"] for record in certificate_records),
               "rejected_invalid_witnesses": sum(not record["actual_acceptance"] for record in certificate_records),
               "route_helper_calls": len(helper_records), "full_limit_cases": large_records,
               "python": sys.version.split()[0], "platform": platform.platform(),
               "java": subprocess.run(["java", "-version"], text=True, capture_output=True, check=True).stderr.splitlines()[0],
               "heap_option": "-Xmx384m", "stack_option": "-Xss256k", "compile_command": compile_command,
               "command": "python tests/run_own_tests.py" + (" --full" if args.full else "")}
    destination = "own_results.json" if args.full else "own_results_quick.json"
    (TESTS / destination).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
