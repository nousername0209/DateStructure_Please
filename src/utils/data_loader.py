from dataclasses import dataclass
import json
from pathlib import Path

from src.structures.hobby_tree import HobbyTree
from src.structures.map_graph import MapGraph
from src.structures.relationship_graph import RelationshipGraph


DEFAULT_DATA_DIR = Path("assets/data")


@dataclass(frozen=True)
class DialogueNode:
    node_id: str
    text: str
    choices: list[dict]


@dataclass(frozen=True)
class GameData:
    profiles: list[dict]
    relationship_graph: RelationshipGraph
    hobby_tree: HobbyTree
    map_graph: MapGraph
    dialogue_tree: "DialogueTree"


class DialogueTree:
    """Pointer-based dialogue tree/DAG built from JSON nodes."""

    def __init__(self, nodes: dict[str, DialogueNode], start_id: str) -> None:
        if start_id not in nodes:
            raise KeyError(f"Unknown start dialogue node: {start_id}")
        self.nodes = nodes
        # 루트 노드의 ID를 영구적으로 기억하도록 저장
        self.start_id = start_id 
        self.current_id = start_id

    # 언제든 대화를 처음으로 되돌릴 수 있는 메서드 추가
    def reset_to_root(self) -> None:
        """대화 포인터를 트리의 가장 처음(Root) 상태로 되돌립니다."""
        self.current_id = self.start_id

    @property
    def current(self) -> DialogueNode:
        return self.nodes[self.current_id]

    def choose(self, choice_index: int) -> DialogueNode:
        choices = self.current.choices
        if choice_index < 0 or choice_index >= len(choices):
            raise IndexError("Dialogue choice index is out of range.")
        next_id = choices[choice_index]["next"]
        if next_id not in self.nodes:
            raise KeyError(f"Dialogue points to missing node: {next_id}")
        self.current_id = next_id
        return self.current

    @classmethod
    def from_dict(cls, data: dict) -> "DialogueTree":
        nodes = {
            node_id: DialogueNode(
                node_id=node_id,
                text=node["text"],
                choices=node.get("choices", []),
            )
            for node_id, node in data["nodes"].items()
        }
        return cls(nodes, data["start"])


def load_json(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def load_profiles(path: str | Path) -> list[dict]:
    return load_json(path)["profiles"]


def load_relationship_graph(path: str | Path) -> RelationshipGraph:
    return RelationshipGraph.from_edges(load_json(path)["relationships"])


def load_hobby_tree(path: str | Path) -> HobbyTree:
    return HobbyTree.from_nested_dict(load_json(path)["hobbies"])


def load_map_graph(path: str | Path) -> MapGraph:
    return MapGraph.from_routes(load_json(path)["routes"])


def load_dialogue_tree(path: str | Path) -> DialogueTree:
    return DialogueTree.from_dict(load_json(path))


def load_game_data(data_dir: str | Path = DEFAULT_DATA_DIR) -> GameData:
    """Load all game JSON files and inject them into structure objects."""

    data_dir = Path(data_dir)
    profiles_path = data_dir / "profiles.json"
    world_map_path = data_dir / "world_map.json"
    dialogue_tree_path = data_dir / "dialogue_tree.json"

    profiles_data = load_json(profiles_path)
    world_map_data = load_json(world_map_path)
    dialogue_data = load_json(dialogue_tree_path)

    return GameData(
        profiles=profiles_data["profiles"],
        relationship_graph=RelationshipGraph.from_edges(profiles_data["relationships"]),
        hobby_tree=HobbyTree.from_nested_dict(dialogue_data["hobbies"]),
        map_graph=MapGraph.from_routes(world_map_data["routes"]),
        dialogue_tree=DialogueTree.from_dict(dialogue_data),
    )
