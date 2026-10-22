import java.util.List;
import java.util.Map;

public final class Input {
    private Input() {
    }

    public static int vertexCount(Map<String, Object> request) {
        return integer(request.get("n"));
    }

    public static int source(Map<String, Object> request) {
        return integer(request.get("source"));
    }

    public static int[][] operations(Map<String, Object> request) {
        return rows(request.get("operations"));
    }

    public static int[][] edges(Map<String, Object> request) {
        return rows(request.get("edges"));
    }

    private static int integer(Object value) {
        return Math.toIntExact(((Number) value).longValue());
    }

    private static int[][] rows(Object value) {
        List<?> inputRows = (List<?>) value;
        int[][] result = new int[inputRows.size()][];

        for (int i = 0; i < inputRows.size(); i++) {
            List<?> inputRow = (List<?>) inputRows.get(i);
            result[i] = new int[inputRow.size()];
            for (int j = 0; j < inputRow.size(); j++) {
                result[i][j] = integer(inputRow.get(j));
            }
        }
        return result;
    }
}
