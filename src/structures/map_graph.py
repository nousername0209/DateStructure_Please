from dataclasses import dataclass, field
import heapq
import math


@dataclass
class MapGraph:
    """Weighted undirected graph for shortest-distance city checks."""

    adjacency: dict[str, list[tuple[str, float]]] = field(default_factory=dict)

    def add_city(self, city: str) -> None:
        self.adjacency.setdefault(city, [])

    def add_route(self, first: str, second: str, distance: float) -> None:
        if distance < 0:
            raise ValueError("Dijkstra requires non-negative route weights.")
        self.add_city(first)
        self.add_city(second)
        self.adjacency[first].append((second, distance))
        self.adjacency[second].append((first, distance))

    def shortest_distance(self, start: str, end: str) -> float:
        if start not in self.adjacency or end not in self.adjacency:
            return math.inf

        distances = {city: math.inf for city in self.adjacency}
        distances[start] = 0
        heap = [(0.0, start)]

        while heap:
            current_distance, city = heapq.heappop(heap)
            if city == end:
                return current_distance
            if current_distance > distances[city]:
                continue

            for neighbor, weight in self.adjacency[city]:
                candidate = current_distance + weight
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    heapq.heappush(heap, (candidate, neighbor))

        return math.inf

    @classmethod
    def from_routes(cls, routes: list[dict]) -> "MapGraph":
        graph = cls()
        for route in routes:
            graph.add_route(route["from"], route["to"], route["distance"])
        return graph
