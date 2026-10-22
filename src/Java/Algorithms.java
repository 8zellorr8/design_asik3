import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.Set;

public final class Algorithms {
    private Algorithms() {
    }

    static Map<String, Object> dsu(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] operations = Input.operations(input);
        DisjointSet sets = new DisjointSet(n);
        int[][] states = new int[operations.length][2];

        for (int i = 0; i < operations.length; i++) {
            sets.union(operations[i][0], operations[i][1]);
            states[i][0] = sets.components;
            states[i][1] = sets.largest;
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("states", states);
        return result;
    }

    static Map<String, Object> kruskal(Map<String, Object> input) {
        return kruskal(Input.vertexCount(input), Input.edges(input));
    }

    static Map<String, Object> kruskal(int n, int[][] edges) {
        Integer[] edgeOrder = new Integer[edges.length];
        for (int i = 0; i < edges.length; i++) {
            edgeOrder[i] = i;
        }
        Arrays.sort(edgeOrder, edgeComparator(edges));

        DisjointSet sets = new DisjointSet(n);
        int[] selected = new int[Math.max(0, n - 1)];
        int selectedCount = 0;
        long cost = 0;

        for (int edgeId : edgeOrder) {
            int[] edge = edges[edgeId];
            if (sets.union(edge[0], edge[1])) {
                selected[selectedCount++] = edgeId;
                cost += (long) edge[2];
            }
        }

        return forestResult(cost, selected, selectedCount, sets.components);
    }

    static Map<String, Object> prim(Map<String, Object> input) {
        return prim(Input.vertexCount(input), Input.edges(input));
    }

    static Map<String, Object> prim(int n, int[][] edges) {
        Adjacency graph = undirectedAdjacency(n, edges);
        PriorityQueue<Integer> frontier = new PriorityQueue<>(edgeComparator(edges));
        boolean[] visited = new boolean[n];
        int[] selected = new int[Math.max(0, n - 1)];
        int selectedCount = 0;
        int components = 0;
        long cost = 0;

        for (int start = 0; start < n; start++) {
            if (visited[start]) {
                continue;
            }
            components++;
            visited[start] = true;
            addFrontierEdges(start, edges, graph, visited, frontier);

            while (!frontier.isEmpty()) {
                int edgeId = frontier.remove();
                int[] edge = edges[edgeId];
                int next = visited[edge[0]] ? edge[1] : edge[0];
                if (visited[next]) {
                    continue;
                }

                visited[next] = true;
                selected[selectedCount++] = edgeId;
                cost += (long) edge[2];
                addFrontierEdges(next, edges, graph, visited, frontier);
            }
        }

        return forestResult(cost, selected, selectedCount, components);
    }

    static Map<String, Object> scc(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);
        Adjacency graph = directedAdjacency(n, edges, false);
        Adjacency transpose = directedAdjacency(n, edges, true);
        int[] order = depthFirstOrder(n, edges, graph, false);
        int[] component = new int[n];
        Arrays.fill(component, -1);
        int[] stack = new int[n];
        int componentCount = 0;

        for (int start : order) {
            if (component[start] != -1) {
                continue;
            }
            int stackSize = 0;
            stack[stackSize++] = start;
            component[start] = componentCount;

            while (stackSize > 0) {
                int vertex = stack[--stackSize];
                for (int position = transpose.offsets[vertex];
                        position < transpose.offsets[vertex + 1]; position++) {
                    int edgeId = transpose.edgeIds[position];
                    int next = edges[edgeId][0];
                    if (component[next] == -1) {
                        component[next] = componentCount;
                        stack[stackSize++] = next;
                    }
                }
            }
            componentCount++;
        }

        Set<Long> seenPairs = new HashSet<>();
        int[][] condensation = new int[edges.length][];
        int pairCount = 0;
        for (int[] edge : edges) {
            int from = component[edge[0]];
            int to = component[edge[1]];
            if (from != to) {
                long pair = (long) from * n + to;
                if (seenPairs.add(pair)) {
                    condensation[pairCount++] = new int[] {from, to};
                }
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("component", component);
        result.put("condensation", Arrays.copyOf(condensation, pairCount));
        return result;
    }

    static Map<String, Object> topo(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);
        Adjacency graph = directedAdjacency(n, edges, false);
        int[] order = depthFirstOrder(n, edges, graph, true);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("acyclic", order != null);
        result.put("order", order == null ? new int[0] : order);
        return result;
    }

    static Map<String, Object> dag(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int source = Input.source(input);
        int[][] edges = Input.edges(input);
        Adjacency graph = directedAdjacency(n, edges, false);
        int[] order = depthFirstOrder(n, edges, graph, true);
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("acyclic", order != null);

        if (order == null) {
            result.put("distance", new Long[0]);
            result.put("parent_edge", new int[0]);
            return result;
        }

        Long[] distance = new Long[n];
        int[] parentEdge = new int[n];
        Arrays.fill(parentEdge, -1);
        distance[source] = 0L;

        for (int vertex : order) {
            if (distance[vertex] == null) {
                continue;
            }
            for (int position = graph.offsets[vertex];
                    position < graph.offsets[vertex + 1]; position++) {
                int edgeId = graph.edgeIds[position];
                int[] edge = edges[edgeId];
                int next = edge[1];
                long candidate = distance[vertex] + (long) edge[2];
                if (distance[next] == null || candidate < distance[next]) {
                    distance[next] = candidate;
                    parentEdge[next] = edgeId;
                }
            }
        }

        result.put("distance", distance);
        result.put("parent_edge", parentEdge);
        return result;
    }

    static List<Integer> reconstructRoute(int source, int target, int[][] edges, int[] parentEdge) {
        if (edges == null || parentEdge == null) {
            throw new IllegalArgumentException("Edges and parent edges must be provided");
        }
        if (source < 0 || source >= parentEdge.length || target < 0 || target >= parentEdge.length) {
            throw new IllegalArgumentException("Source and target must be valid vertices");
        }
        if (source == target) {
            return List.of(source);
        }
        if (parentEdge[target] == -1) {
            return List.of();
        }

        List<Integer> route = new ArrayList<>();
        int vertex = target;
        while (vertex != source) {
            if (route.size() >= parentEdge.length) {
                throw new IllegalArgumentException("Parent edges contain a cycle");
            }
            route.add(vertex);
            int edgeId = parentEdge[vertex];
            if (edgeId < 0 || edgeId >= edges.length) {
                throw new IllegalArgumentException("Parent edges do not lead to the source");
            }
            int[] edge = edges[edgeId];
            if (edge == null || edge.length < 2 || edge[1] != vertex
                    || edge[0] < 0 || edge[0] >= parentEdge.length) {
                throw new IllegalArgumentException("A parent edge has an invalid direction or endpoint");
            }
            vertex = edge[0];
        }
        route.add(source);
        Collections.reverse(route);
        return route;
    }

    private static Comparator<Integer> edgeComparator(int[][] edges) {
        return Comparator.comparingInt((Integer edgeId) -> edges[edgeId][2])
                .thenComparingInt(edgeId -> edgeId);
    }

    private static Map<String, Object> forestResult(long cost, int[] selected,
            int selectedCount, int components) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cost", cost);
        result.put("edge_ids", Arrays.copyOf(selected, selectedCount));
        result.put("components", components);
        return result;
    }

    private static void addFrontierEdges(int vertex, int[][] edges, Adjacency graph,
            boolean[] visited, PriorityQueue<Integer> frontier) {
        for (int position = graph.offsets[vertex]; position < graph.offsets[vertex + 1]; position++) {
            int edgeId = graph.edgeIds[position];
            int[] edge = edges[edgeId];
            int next = edge[0] == vertex ? edge[1] : edge[0];
            if (!visited[next]) {
                frontier.add(edgeId);
            }
        }
    }

    private static Adjacency directedAdjacency(int n, int[][] edges, boolean reversed) {
        int fromIndex = reversed ? 1 : 0;
        int[] offsets = new int[n + 1];
        for (int[] edge : edges) {
            offsets[edge[fromIndex] + 1]++;
        }
        for (int vertex = 0; vertex < n; vertex++) {
            offsets[vertex + 1] += offsets[vertex];
        }

        int[] nextPosition = Arrays.copyOf(offsets, n);
        int[] edgeIds = new int[edges.length];
        for (int edgeId = 0; edgeId < edges.length; edgeId++) {
            int from = edges[edgeId][fromIndex];
            edgeIds[nextPosition[from]++] = edgeId;
        }
        return new Adjacency(offsets, edgeIds);
    }

    private static Adjacency undirectedAdjacency(int n, int[][] edges) {
        int[] offsets = new int[n + 1];
        for (int[] edge : edges) {
            offsets[edge[0] + 1]++;
            offsets[edge[1] + 1]++;
        }
        for (int vertex = 0; vertex < n; vertex++) {
            offsets[vertex + 1] += offsets[vertex];
        }

        int[] nextPosition = Arrays.copyOf(offsets, n);
        int[] edgeIds = new int[2 * edges.length];
        for (int edgeId = 0; edgeId < edges.length; edgeId++) {
            int[] edge = edges[edgeId];
            edgeIds[nextPosition[edge[0]]++] = edgeId;
            edgeIds[nextPosition[edge[1]]++] = edgeId;
        }
        return new Adjacency(offsets, edgeIds);
    }

    private static int[] depthFirstOrder(int n, int[][] edges, Adjacency graph, boolean checkCycles) {
        byte[] state = new byte[n];
        int[] stack = new int[n];
        int[] nextEdge = new int[n];
        int[] order = new int[n];
        int orderPosition = n;

        for (int start = 0; start < n; start++) {
            if (state[start] != 0) {
                continue;
            }
            int depth = 0;
            stack[depth] = start;
            nextEdge[depth] = graph.offsets[start];
            state[start] = 1;

            while (depth >= 0) {
                int vertex = stack[depth];
                if (nextEdge[depth] == graph.offsets[vertex + 1]) {
                    state[vertex] = 2;
                    order[--orderPosition] = vertex;
                    depth--;
                    continue;
                }

                int edgeId = graph.edgeIds[nextEdge[depth]++];
                int next = edges[edgeId][1];
                if (state[next] == 1 && checkCycles) {
                    return null;
                }
                if (state[next] == 0) {
                    state[next] = 1;
                    depth++;
                    stack[depth] = next;
                    nextEdge[depth] = graph.offsets[next];
                }
            }
        }
        return order;
    }

    private static final class Adjacency {
        private final int[] offsets;
        private final int[] edgeIds;

        private Adjacency(int[] offsets, int[] edgeIds) {
            this.offsets = offsets;
            this.edgeIds = edgeIds;
        }
    }

    private static final class DisjointSet {
        private final int[] parent;
        private final int[] size;
        private int components;
        private int largest;

        private DisjointSet(int n) {
            parent = new int[n];
            size = new int[n];
            components = n;
            largest = n == 0 ? 0 : 1;
            for (int vertex = 0; vertex < n; vertex++) {
                parent[vertex] = vertex;
                size[vertex] = 1;
            }
        }

        private int find(int vertex) {
            int root = vertex;
            while (parent[root] != root) {
                root = parent[root];
            }
            while (vertex != root) {
                int next = parent[vertex];
                parent[vertex] = root;
                vertex = next;
            }
            return root;
        }

        private boolean union(int first, int second) {
            int firstRoot = find(first);
            int secondRoot = find(second);
            if (firstRoot == secondRoot) {
                return false;
            }
            if (size[firstRoot] < size[secondRoot]) {
                int temporary = firstRoot;
                firstRoot = secondRoot;
                secondRoot = temporary;
            }
            parent[secondRoot] = firstRoot;
            size[firstRoot] += size[secondRoot];
            components--;
            largest = Math.max(largest, size[firstRoot]);
            return true;
        }
    }
}
