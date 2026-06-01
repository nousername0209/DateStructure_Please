from dataclasses import dataclass, field


@dataclass
class HobbyNode:
    """A node in a general hobby tree."""

    name: str
    parent: "HobbyNode | None" = None
    children: list["HobbyNode"] = field(default_factory=list)

    def add_child(self, child: "HobbyNode") -> None:
        child.parent = self
        self.children.append(child)


class HobbyTree:
    """General tree with LCA-based distance between hobby nodes."""

    def __init__(self, root_name: str | None = None) -> None:
        self.root: HobbyNode | None = None
        self.nodes: dict[str, HobbyNode] = {}
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
            parent.add_child(node)

        self.nodes[name] = node
        return node

    def depth(self, name: str) -> int:
        node = self._require_node(name)
        depth = 0
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth

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
        lca = self.lowest_common_ancestor(first_name, second_name)
        return self.depth(first_name) + self.depth(second_name) - 2 * self.depth(lca.name)

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
