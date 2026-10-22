import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class RouteHelperTest {
    private RouteHelperTest() {
    }

    public static void main(String[] args) {
        Map<String, Object> basic = Json.parseRequest(
                "{\"task\":\"dag\",\"n\":5,\"source\":0,\"edges\":[[0,1,3],[0,2,8],[1,2,-7],[2,3,4]]}");
        int[][] basicEdges = Input.edges(basic);
        int[] basicParents = parents(Algorithms.dag(basic));
        verify("reachable", 0, 3, basicEdges, basicParents,
                Arrays.asList(0, 1, 2, 3), 0L);
        verify("source", 0, 0, basicEdges, basicParents,
                Arrays.asList(0), 0L);
        verify("unreachable", 0, 4, basicEdges, basicParents,
                new ArrayList<>(), null);

        Map<String, Object> tied = Json.parseRequest(
                "{\"task\":\"dag\",\"n\":4,\"source\":0,\"edges\":[[0,1,5],[0,1,2],[0,2,1],[2,1,1],[1,3,0],[2,3,1],[0,1,2]]}");
        int[][] tiedEdges = Input.edges(tied);
        verify("tied_parallel_actual", 0, 3, tiedEdges,
                parents(Algorithms.dag(tied)), null, 2L);
        verify("parallel_selected_id", 0, 3, tiedEdges,
                new int[]{-1, 6, 2, 4}, Arrays.asList(0, 1, 3), 2L);
        verify("alternative_tied_route", 0, 3, tiedEdges,
                new int[]{-1, 3, 2, 5}, Arrays.asList(0, 2, 3), 2L);
    }

    private static int[] parents(Map<String, Object> answer) {
        Map<String, Object> decoded = Json.parseRequest(Json.write(answer));
        List<?> values = (List<?>) decoded.get("parent_edge");
        int[] result = new int[values.size()];
        for (int index = 0; index < values.size(); index++) {
            result[index] = ((Number) values.get(index)).intValue();
        }
        return result;
    }

    private static void verify(String name, int source, int target, int[][] edges,
                               int[] parentEdge, List<Integer> expectedRoute,
                               Long expectedCost) {
        List<Integer> route = Algorithms.reconstructRoute(source, target, edges, parentEdge);
        if (expectedRoute != null && !route.equals(expectedRoute)) {
            throw new AssertionError(name + ": unexpected route " + route);
        }
        List<Integer> selectedEdges = new ArrayList<>();
        long total = 0;
        if (expectedCost != null) {
            if (route.isEmpty() || route.get(0) != source
                    || route.get(route.size() - 1) != target) {
                throw new AssertionError(name + ": incorrect route endpoints");
            }
            for (int index = 1; index < route.size(); index++) {
                int from = route.get(index - 1);
                int to = route.get(index);
                int edgeId = parentEdge[to];
                if (edgeId < 0 || edgeId >= edges.length
                        || edges[edgeId][0] != from || edges[edgeId][1] != to) {
                    throw new AssertionError(name + ": incorrect edge direction or ID");
                }
                selectedEdges.add(edgeId);
                total += edges[edgeId][2];
            }
            if (total != expectedCost) {
                throw new AssertionError(name + ": unexpected route cost " + total);
            }
        } else if (!route.isEmpty()) {
            throw new AssertionError(name + ": unreachable target has a route");
        }
        Map<String, Object> record = new LinkedHashMap<>();
        record.put("case", name);
        record.put("source", source);
        record.put("target", target);
        record.put("parent_edge", parentEdge);
        record.put("route", route);
        record.put("selected_edge_ids", selectedEdges);
        record.put("cost", expectedCost == null ? null : total);
        record.put("expected_cost", expectedCost);
        record.put("direction_valid", true);
        record.put("passed", true);
        System.out.println(Json.write(record));
    }
}
