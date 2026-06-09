from dataclasses import dataclass, field
import heapq
import math


@dataclass
class MapGraph:
    """Weighted undirected graph for shortest-distance city checks."""

    adjacency: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    # 도시 이름 -> 정규화된 (x, y) 좌표 (0..1). 지도 시각화 배치에만 사용됨.
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    # (도시A, 도시B)의 최단 거리를 기억하는 수첩
    _distance_cache: dict[tuple[str, str], float] = field(default_factory=dict)

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

        # 캐싱 확인: 알파벳 순으로 정렬해서 (A, B)와 (B, A)를 똑같이 취급 (무방향 그래프이므로)
        cache_key = tuple(sorted([start, end]))
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        distances = {city: math.inf for city in self.adjacency}
        distances[start] = 0
        heap = [(0.0, start)]

        while heap:
            current_distance, city = heapq.heappop(heap)
            
            # 도착지에 도달했을 때
            if city == end:
                self._distance_cache[cache_key] = current_distance # 기록해두고 반환
                return current_distance
                
            if current_distance > distances[city]:
                continue

            for neighbor, weight in self.adjacency[city]:
                candidate = current_distance + weight
                if candidate < distances[neighbor]:
                    distances[neighbor] = candidate
                    heapq.heappush(heap, (candidate, neighbor))

        # 경로가 없는 경우 캐싱
        self._distance_cache[cache_key] = math.inf
        return math.inf

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
    def from_routes(cls, routes: list[dict], cities: list[dict] | None = None) -> "MapGraph":
        graph = cls()
        for route in routes:
            graph.add_route(route["from"], route["to"], route["distance"])
        for city in cities or []:
            graph.positions[city["name"]] = (city["x"], city["y"])
        return graph
