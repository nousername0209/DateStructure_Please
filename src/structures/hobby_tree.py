from dataclasses import dataclass, field


@dataclass
class HobbyNode:
    """A node in a general hobby tree."""

    name: str
    parent: "HobbyNode | None" = None
    children: list["HobbyNode"] = field(default_factory=list)
    depth: int = 0  # 노드가 자신의 깊이를 영구적으로 기억하게 함

    def add_child(self, child: "HobbyNode") -> None:
        child.parent = self
        child.depth = self.depth + 1  # 자식을 추가할 때 깊이를 한 번만 계산
        self.children.append(child)


class HobbyTree:
    """General tree with LCA-based distance between hobby nodes."""

    def __init__(self, root_name: str | None = None) -> None:
        self.root: HobbyNode | None = None
        self.nodes: dict[str, HobbyNode] = {}
        self._distance_cache: dict[tuple[str, str], int] = {} # 캐싱 딕셔너리 추가

        if root_name is not None:
            self.root = HobbyNode(root_name)
            self.nodes[root_name] = self.root

    def add_node(self, name: str, parent_name: str | None = None) -> HobbyNode:
        if name in self.nodes:
            raise ValueError(f"Duplicate hobby node: {name}")

        node = HobbyNode(name)
        if parent_name is None:
            if self.root is not None:
                raise ValueError("Root node already exists.")
            self.root = node
        else:
            parent = self._require_node(parent_name)
            parent.add_child(node) # 여기서 깊이가 자동 세팅됨

        self.nodes[name] = node
        return node

    # 무식하게 부모를 타고 올라가던 메서드 삭제, 저장된 속성값 바로 반환
    def depth(self, name: str) -> int:
        return self._require_node(name).depth

    def ancestors(self, name: str) -> list[HobbyNode]:
        node = self._require_node(name)
        result = []
        while node is not None:
            result.append(node)
            node = node.parent
        return result

    def lowest_common_ancestor(self, first_name: str, second_name: str) -> HobbyNode:
        first_ancestors = {node.name for node in self.ancestors(first_name)}
        for ancestor in self.ancestors(second_name):
            if ancestor.name in first_ancestors:
                return ancestor
        raise ValueError("Tree is disconnected.")

    def distance(self, first_name: str, second_name: str) -> int:
        # 캐싱 확인: 이미 계산한 적 있는 거리면 O(1)로 즉시 반환 (순서 무관하게 정렬)
        cache_key = tuple(sorted([first_name, second_name]))
        if cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        lca = self.lowest_common_ancestor(first_name, second_name)
        dist = self.depth(first_name) + self.depth(second_name) - 2 * self.depth(lca.name)
        
        # 계산 결과를 캐시에 저장
        self._distance_cache[cache_key] = dist
        return dist

    def _require_node(self, name: str) -> HobbyNode:
        if name not in self.nodes:
            raise KeyError(f"Unknown hobby node: {name}")
        return self.nodes[name]

    @classmethod
    def from_nested_dict(cls, data: dict) -> "HobbyTree":
        tree = cls()

        def visit(node_data: dict, parent_name: str | None) -> None:
            name = node_data["name"]
            tree.add_node(name, parent_name)
            for child_data in node_data.get("children", []):
                visit(child_data, name)

        visit(data, None)
        return tree
