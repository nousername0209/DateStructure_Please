from collections import deque
from dataclasses import dataclass, field


@dataclass
class RelationshipGraph:
    """Relationship graph for checking direct (undirected) links between profiles."""

    adjacency: dict[str, dict[str, str]] = field(default_factory=dict)

    def add_user(self, user_id: str) -> None:
        self.adjacency.setdefault(user_id, {})

    def add_relation(self, source: str, target: str, kind: str = "unknown") -> None:
        self.add_user(source)
        self.add_user(target)
        self.adjacency[source][target] = kind

    def has_path(self, source: str, target: str) -> bool:
        if source == target:
            return source in self.adjacency
        if source not in self.adjacency or target not in self.adjacency:
            return False

        visited = {source}
        queue = deque([source])

        while queue:
            current = queue.popleft()
            for neighbor in self.adjacency[current]:
                if neighbor == target:
                    return True
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False

    def is_related(self, a: str, b: str) -> bool:
        """두 사용자가 '직접' 연결돼 있으면 True. 관계는 방향이 없는 것으로 취급하며,
        다단계 연쇄(A-B, B-C => A-C)는 보지 않는다."""
        return b in self.adjacency.get(a, {}) or a in self.adjacency.get(b, {})

    def neighbors(self, user_id: str) -> set[str]:
        """방향을 무시한 직접 이웃 집합. 저장된 방향(나가는 간선)과 들어오는 간선을 모두 본다."""
        result = set(self.adjacency.get(user_id, {}).keys())
        for source, targets in self.adjacency.items():
            if user_id in targets:
                result.add(source)
        return result

    @classmethod
    def from_edges(cls, edges: list[dict[str, str]]) -> "RelationshipGraph":
        graph = cls()
        for edge in edges:
            graph.add_relation(edge["from"], edge["to"], edge.get("type", "unknown"))
        return graph
