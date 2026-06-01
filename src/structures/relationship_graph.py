from collections import deque
from dataclasses import dataclass, field


@dataclass
class RelationshipGraph:
    """Directed graph for checking forbidden social paths between profiles."""

    adjacency: dict[str, set[str]] = field(default_factory=dict)

    def add_user(self, user_id: str) -> None:
        self.adjacency.setdefault(user_id, set())

    def add_relation(self, source: str, target: str) -> None:
        self.add_user(source)
        self.add_user(target)
        self.adjacency[source].add(target)

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

    def first_forbidden_path(
        self,
        source: str,
        target: str,
        forbidden_targets: set[str] | None = None,
    ) -> list[str] | None:
        """Return a shortest forbidden path from source to target or blacklisted node."""

        targets = set(forbidden_targets or set())
        targets.add(target)
        if source not in self.adjacency:
            return None

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()
            if current in targets and current != source:
                return path
            for neighbor in self.adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))
        return None

    @classmethod
    def from_edges(cls, edges: list[dict[str, str]]) -> "RelationshipGraph":
        graph = cls()
        for edge in edges:
            graph.add_relation(edge["from"], edge["to"])
        return graph
