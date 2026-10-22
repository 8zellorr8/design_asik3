import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

public final class Benchmark {
    private static final long BASE_SEED = 20261022L;
    private static final int WARMUPS = 3;
    private static final int REPETITIONS = 5;
    private static volatile long checksum;

    private record Graph(int vertexCount, int[][] edges, long seed, long optimum) {
    }

    public static void main(String[] arguments) {
        boolean validateOnly = arguments.length == 1
                && arguments[0].equals("--validate-only");
        if (arguments.length > 1 || arguments.length == 1 && !validateOnly) {
            throw new IllegalArgumentException("Usage: Benchmark [--validate-only]");
        }

        int[][] sizes = {{1000, 4000}, {10000, 40000}, {100000, 250000}};
        List<Map<String, Object>> measurements = new ArrayList<>();
        for (int[] size : sizes) {
            Graph graph = generate(size[0], size[1]);
            int[][] originalEdges = copyEdges(graph.edges());
            validate(graph, Algorithms.kruskal(graph.vertexCount(), graph.edges()));
            validate(graph, Algorithms.prim(graph.vertexCount(), graph.edges()));
            require(Arrays.deepEquals(originalEdges, graph.edges()),
                    "An algorithm changed the benchmark input");

            Map<String, Object> measurement = new LinkedHashMap<>();
            measurement.put("n", graph.vertexCount());
            measurement.put("m", graph.edges().length);
            measurement.put("seed", graph.seed());
            measurement.put("graph_fingerprint", fingerprint(graph));
            measurement.put("expected_components", 4);
            measurement.put("expected_cost", graph.optimum());
            measurement.put("validation", "passed");

            if (!validateOnly) {
                for (int repetition = 0; repetition < WARMUPS; repetition++) {
                    consume(Algorithms.kruskal(graph.vertexCount(), graph.edges()));
                    consume(Algorithms.prim(graph.vertexCount(), graph.edges()));
                }

                long[] kruskalTimes = new long[REPETITIONS];
                long[] primTimes = new long[REPETITIONS];
                for (int repetition = 0; repetition < REPETITIONS; repetition++) {
                    if (repetition % 2 == 0) {
                        kruskalTimes[repetition] = measure(graph, true);
                        primTimes[repetition] = measure(graph, false);
                    } else {
                        primTimes[repetition] = measure(graph, false);
                        kruskalTimes[repetition] = measure(graph, true);
                    }
                }
                measurement.put("kruskal_nanoseconds", kruskalTimes);
                measurement.put("prim_nanoseconds", primTimes);
                measurement.put("kruskal_median_nanoseconds", median(kruskalTimes));
                measurement.put("prim_median_nanoseconds", median(primTimes));
            }
            require(Arrays.deepEquals(originalEdges, graph.edges()),
                    "An algorithm changed the benchmark input");
            measurements.add(measurement);
        }

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("mode", validateOnly ? "validation" : "timing");
        report.put("base_seed", BASE_SEED);
        report.put("warmups_per_method_per_size", WARMUPS);
        report.put("repetitions_per_method_per_size", REPETITIONS);
        report.put("timer", "System.nanoTime()");
        report.put("java_version", System.getProperty("java.version"));
        report.put("java_runtime", System.getProperty("java.runtime.version"));
        report.put("java_vm", System.getProperty("java.vm.name"));
        report.put("os", System.getProperty("os.name"));
        report.put("os_version", System.getProperty("os.version"));
        report.put("architecture", System.getProperty("os.arch"));
        report.put("available_processors", Runtime.getRuntime().availableProcessors());
        report.put("max_heap_bytes", Runtime.getRuntime().maxMemory());
        report.put("checksum", checksum);
        report.put("measurements", measurements);
        System.out.println(Json.write(report));
    }

    private static Graph generate(int vertexCount, int edgeCount) {
        long seed = BASE_SEED + 31L * vertexCount + edgeCount;
        Random random = new Random(seed);
        int[][] edges = new int[edgeCount][];
        int[] boundaries = {0, (vertexCount - 1) / 3,
                2 * (vertexCount - 1) / 3, vertexCount - 1};
        int nextEdge = 0;
        long optimum = 0;

        for (int component = 0; component < 3; component++) {
            int firstVertex = boundaries[component];
            int endVertex = boundaries[component + 1];
            for (int vertex = firstVertex + 1; vertex < endVertex; vertex++) {
                int parent = firstVertex + random.nextInt(vertex - firstVertex);
                int weight = -1_000_000_000 + random.nextInt(100_000);
                edges[nextEdge++] = new int[]{parent, vertex, weight};
                optimum += weight;
            }
        }

        while (nextEdge < edgeCount) {
            int component = random.nextInt(3);
            int firstVertex = boundaries[component];
            int size = boundaries[component + 1] - firstVertex;
            int from = firstVertex + random.nextInt(size);
            int to = random.nextInt(20) == 0 ? from
                    : firstVertex + random.nextInt(size);
            int weight = random.nextInt(1_000_000_001);
            edges[nextEdge++] = new int[]{from, to, weight};
        }

        for (int index = edges.length - 1; index > 0; index--) {
            int replacement = random.nextInt(index + 1);
            int[] edge = edges[index];
            edges[index] = edges[replacement];
            edges[replacement] = edge;
        }
        return new Graph(vertexCount, edges, seed, optimum);
    }

    private static void validate(Graph graph, Map<String, Object> result) {
        require(result.get("cost") instanceof Number, "Cost is missing");
        require(result.get("components") instanceof Number, "Components are missing");
        require(result.get("edge_ids") instanceof int[], "Edge IDs must be int[]");
        long cost = ((Number) result.get("cost")).longValue();
        int components = ((Number) result.get("components")).intValue();
        int[] selected = (int[]) result.get("edge_ids");
        boolean[] used = new boolean[graph.edges().length];
        int[][] selectedEdges = new int[selected.length][];
        long selectedCost = 0;
        for (int index = 0; index < selected.length; index++) {
            int edgeId = selected[index];
            require(edgeId >= 0 && edgeId < graph.edges().length, "Invalid edge ID");
            require(!used[edgeId], "Repeated edge ID");
            used[edgeId] = true;
            int[] edge = graph.edges()[edgeId];
            require(edge[0] != edge[1], "A selected edge is a self-loop");
            selectedEdges[index] = edge;
            selectedCost += edge[2];
        }

        int[] inputLabels = componentLabels(graph.vertexCount(), graph.edges());
        int[] selectedLabels = componentLabels(graph.vertexCount(), selectedEdges);
        int inputComponents = 1 + Arrays.stream(inputLabels).max().orElse(-1);
        int selectedComponents = 1 + Arrays.stream(selectedLabels).max().orElse(-1);
        require(inputComponents == 4, "The generated graph has unexpected components");
        require(components == inputComponents, "Incorrect component count");
        require(selectedComponents == inputComponents, "Forest does not span components");
        require(selected.length == graph.vertexCount() - components,
                "Incorrect edge count or a cycle");
        for (int[] edge : graph.edges()) {
            require(selectedLabels[edge[0]] == selectedLabels[edge[1]],
                    "A connected input component was split");
        }
        require(cost == selectedCost, "Cost does not equal selected edge weights");
        require(cost == graph.optimum(), "Cost is not the independently proved optimum");
        consume(result);
    }

    private static int[] componentLabels(int vertexCount, int[][] edges) {
        int[] degrees = new int[vertexCount];
        for (int[] edge : edges) {
            degrees[edge[0]]++;
            degrees[edge[1]]++;
        }
        int[][] neighbors = new int[vertexCount][];
        for (int vertex = 0; vertex < vertexCount; vertex++) {
            neighbors[vertex] = new int[degrees[vertex]];
        }
        Arrays.fill(degrees, 0);
        for (int[] edge : edges) {
            neighbors[edge[0]][degrees[edge[0]]++] = edge[1];
            neighbors[edge[1]][degrees[edge[1]]++] = edge[0];
        }

        int[] labels = new int[vertexCount];
        Arrays.fill(labels, -1);
        int[] queue = new int[vertexCount];
        int component = 0;
        for (int start = 0; start < vertexCount; start++) {
            if (labels[start] != -1) {
                continue;
            }
            int front = 0;
            int back = 0;
            queue[back++] = start;
            labels[start] = component;
            while (front < back) {
                int vertex = queue[front++];
                for (int neighbor : neighbors[vertex]) {
                    if (labels[neighbor] == -1) {
                        labels[neighbor] = component;
                        queue[back++] = neighbor;
                    }
                }
            }
            component++;
        }
        return labels;
    }

    private static long measure(Graph graph, boolean useKruskal) {
        long start = System.nanoTime();
        Map<String, Object> result = useKruskal
                ? Algorithms.kruskal(graph.vertexCount(), graph.edges())
                : Algorithms.prim(graph.vertexCount(), graph.edges());
        long elapsed = System.nanoTime() - start;
        consume(result);
        return elapsed;
    }

    private static void consume(Map<String, Object> result) {
        long value = ((Number) result.get("cost")).longValue();
        value = value * 31 + ((Number) result.get("components")).intValue();
        for (int edgeId : (int[]) result.get("edge_ids")) {
            value = value * 31 + edgeId;
        }
        checksum = checksum * 31 + value;
    }

    private static long median(long[] values) {
        long[] sorted = values.clone();
        Arrays.sort(sorted);
        return sorted[sorted.length / 2];
    }

    private static int[][] copyEdges(int[][] edges) {
        int[][] copy = new int[edges.length][];
        for (int index = 0; index < edges.length; index++) {
            copy[index] = edges[index].clone();
        }
        return copy;
    }

    private static String fingerprint(Graph graph) {
        long value = graph.vertexCount();
        for (int[] edge : graph.edges()) {
            for (int item : edge) {
                value = value * 1_000_003L + item;
            }
        }
        return Long.toUnsignedString(value, 16);
    }

    private static void require(boolean condition, String message) {
        if (!condition) {
            throw new IllegalStateException(message);
        }
    }
}
