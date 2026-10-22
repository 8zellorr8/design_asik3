import argparse
import ctypes
import datetime
import json
import os
import pathlib
import platform
import subprocess
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / ".build" / "benchmark"


def hardware():
    details = {
        "processor": platform.processor(),
        "logical_processors": os.cpu_count(),
        "platform": platform.platform(),
    }
    if sys.platform == "win32":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        ) as key:
            details["processor"] = winreg.QueryValueEx(
                key, "ProcessorNameString"
            )[0].strip()

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            details["physical_memory_bytes"] = status.total_physical
    elif hasattr(os, "sysconf"):
        details["physical_memory_bytes"] = (
            os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        )
    return details


def milliseconds(nanoseconds):
    return f"{nanoseconds / 1_000_000:.3f}"


def write_report(result):
    environment = result["hardware"]
    memory = environment.get("physical_memory_bytes")
    memory_text = f"{memory / (1024 ** 3):.2f} GiB" if memory else "unavailable"
    lines = [
        "# Kruskal and Prim benchmark",
        "",
        f"Measured at {result['measured_at_utc']} (UTC). These are actual local measurements.",
        "",
        "## Reproduce",
        "",
        "Run from the repository root:",
        "",
        "```sh",
        "python tests/benchmark.py --validate-only",
        "python tests/benchmark.py",
        "```",
        "",
        "The runner compiles all Java sources plus `tests/Benchmark.java` with",
        "`javac --release 17 -d .build/benchmark`, then executes",
        "`java -Xms256m -Xmx384m -cp .build/benchmark Benchmark`.",
        "The validation command adds `--validate-only` to the Java invocation.",
        "Exact argument arrays and raw nanoseconds are saved in `tests/benchmark-results.json`.",
        "The validation-only result is saved in `tests/benchmark-validation.json`.",
        "",
        "## Environment and measurement boundary",
        "",
        f"- CPU: {environment['processor']}; {environment['logical_processors']} logical processors.",
        f"- Physical memory: {memory_text}; Java maximum heap: {result['max_heap_bytes'] / (1024 ** 2):.0f} MiB.",
        f"- OS: {environment['platform']}; Java sees {result['os']} {result['os_version']} ({result['architecture']}).",
        f"- Runtime: {result['java_vm']}, Java {result['java_runtime']}.",
        f"- Compiler: {result['compiler_version']}; `--release 17` enforces Java 17 source/API compatibility.",
        "- Timer: `System.nanoTime()`, elapsed nanoseconds converted to milliseconds below.",
        f"- Warm-up: {result['warmups_per_method_per_size']} untimed calls per algorithm at each size, after one untimed correctness call per algorithm.",
        f"- Samples: {result['repetitions_per_method_per_size']} calls per algorithm per size in the same JVM; the first algorithm alternates by repetition.",
        "- Both algorithms receive the exact same preconstructed `int[][]` object at each size. Full input equality is checked before and after timing to detect mutations.",
        "- Timing starts immediately before the typed algorithm call and stops after its result map is returned. It includes sorting, adjacency creation, all algorithm allocations, and returned result construction.",
        "- Compilation, JVM startup, graph generation, input copying, parsing, correctness checks, checksum consumption, and all input/output are excluded. No explicit garbage collection is requested.",
        "- Every returned edge ID and scalar is consumed into a volatile checksum after the timer stops, preventing results from being discarded as unused.",
        "",
        "## Generator and independent correctness argument",
        "",
        f"`tests/Benchmark.java` uses `java.util.Random` with base seed {result['base_seed']}; each graph seed is `base + 31*n + m`.",
        "Vertices `0..n-2` form three contiguous nonempty components; vertex `n-1` is isolated.",
        "Within each component, each vertex after the first receives an edge to a uniformly selected earlier vertex, creating a tree.",
        "These planted tree edges have weights in `[-1000000000, -999900001]`.",
        "Extra edges stay inside one component and have weights in `[0, 1000000000]`; endpoints may repeat and approximately 5% are deliberate self-loops.",
        "The generator shuffles all edges with the same seeded RNG. Original IDs are their positions after this shuffle.",
        "",
        "The optimum is computed directly by summing the planted tree weights, independently of either tested algorithm.",
        "Removing any planted tree edge splits its tree into two sets. That edge is the only planted edge crossing this cut; all other crossing edges have nonnegative weights.",
        "It is therefore the unique cheapest edge across its cut and must belong to every minimum spanning tree. All planted edges together form a spanning forest, proving the expected optimum.",
        "",
        "Before timing, the checker validates each method separately: selected IDs are in range and distinct, no selected edge is a loop, selected weights sum to the returned cost, and this cost equals the independently proved optimum.",
        "Independent breadth-first traversals label input and selected-edge components. The returned component count must match the input; every input edge must stay inside a selected component; exactly `n-components` edges must be selected.",
        "Together, spanning every input component and this edge count prove acyclicity. This checks the actual witness, rather than merely comparing the two algorithm costs.",
        "",
        "## Actual results",
        "",
        "All six pre-timing forest and optimum checks passed. Every graph has four components, including the isolate.",
        "",
        "| n | m | Seed | Optimum cost | Kruskal median (ms) | Prim median (ms) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in result["measurements"]:
        lines.append(
            f"| {row['n']} | {row['m']} | {row['seed']} | {row['expected_cost']} | "
            f"{milliseconds(row['kruskal_median_nanoseconds'])} | "
            f"{milliseconds(row['prim_median_nanoseconds'])} |"
        )
    lines.extend([
        "",
        "All individual timings below are milliseconds in execution-repetition order, rounded to three decimals. Medians are computed from unrounded nanoseconds.",
        "",
        "| n | Method | Sample 1 | Sample 2 | Sample 3 | Sample 4 | Sample 5 |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ])
    for row in result["measurements"]:
        for method in ("kruskal", "prim"):
            samples = " | ".join(milliseconds(value) for value in row[f"{method}_nanoseconds"])
            lines.append(f"| {row['n']} | {method.capitalize()} | {samples} |")
    lines.extend([
        "",
        "## Observations",
        "",
    ])
    for row in result["measurements"]:
        kruskal = row["kruskal_median_nanoseconds"]
        prim = row["prim_median_nanoseconds"]
        faster = "Kruskal" if kruskal < prim else "Prim"
        ratio = max(kruskal, prim) / min(kruskal, prim)
        lines.append(f"- At n={row['n']}, m={row['m']}, {faster} had the smaller median; the ratio between the larger and smaller median was {ratio:.2f}.")
    lines.extend([
        "",
        "These observations describe this run and generator only. Consult the individual samples to see variation; a median reduces the influence of one slow sample but does not eliminate runtime noise.",
        "",
        "## Asymptotic argument and limitations",
        "",
        "Kruskal sorts `m` edges, then performs near-constant amortized DSU operations, giving `O(n + m log(m+1))` time and `O(n+m)` memory.",
        "Prim builds adjacency lists and processes a lazy priority queue, giving `O(n + m log(m+1))` time and `O(n+m)` memory.",
        "These bounds follow from the implementations, not from fitting three measurements.",
        "",
        "The experiment uses three sparse graphs from one deliberately structured distribution, with planted negative optimum edges and four components. It does not characterize dense graphs, arbitrary weight distributions, or every graph shape.",
        "There is one JVM process, five samples per point, and three warm-ups per method per size. JIT compilation, garbage collection, scheduling, CPU frequency changes, cache effects, and background activity can still influence the timings.",
        "No CPU affinity or operating-system isolation was configured. The two algorithms can allocate different amounts of memory even though the measurement boundary is identical.",
        "The local runtime is the version shown above, not Java 17; compilation targets Java 17 but the measurements describe the installed runtime. These data support a reproducible local comparison, not a universal performance claim or proof of complexity.",
        "",
    ])
    (ROOT / "tests" / "benchmark-report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    arguments = parser.parse_args()
    BUILD.mkdir(parents=True, exist_ok=True)
    java_sources = sorted((ROOT / "src" / "Java").glob("*.java"))
    compile_command = [
        "javac", "--release", "17", "-d", BUILD.relative_to(ROOT).as_posix(),
        *(source.relative_to(ROOT).as_posix() for source in java_sources),
        (ROOT / "tests" / "Benchmark.java").relative_to(ROOT).as_posix(),
    ]
    subprocess.run(compile_command, cwd=ROOT, check=True, timeout=60)
    run_command = ["java", "-Xms256m", "-Xmx384m", "-cp", BUILD.relative_to(ROOT).as_posix(), "Benchmark"]
    if arguments.validate_only:
        run_command.append("--validate-only")
    completed = subprocess.run(
        run_command, cwd=ROOT, check=True, capture_output=True, text=True, timeout=180
    )
    result = json.loads(completed.stdout)
    result["measured_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result["hardware"] = hardware()
    result["compiler_version"] = subprocess.run(
        ["javac", "-version"], check=True, capture_output=True, text=True, timeout=20
    ).stdout.strip()
    result["compile_command"] = compile_command
    result["run_command"] = run_command
    filename = "benchmark-validation.json" if arguments.validate_only else "benchmark-results.json"
    (ROOT / "tests" / filename).write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    if not arguments.validate_only:
        write_report(result)
    for row in result["measurements"]:
        print(f"n={row['n']}, m={row['m']}, cost={row['expected_cost']}: validation passed")
        if not arguments.validate_only:
            print(
                f"  Median milliseconds: Kruskal={milliseconds(row['kruskal_median_nanoseconds'])}, "
                f"Prim={milliseconds(row['prim_median_nanoseconds'])}"
            )
    print(f"Saved tests/{filename}")
    if not arguments.validate_only:
        print("Saved tests/benchmark-report.md")


if __name__ == "__main__":
    main()
