from dataclasses import dataclass
from pathlib import Path

from src.structures.event_queue import EventQueue
from src.structures.hobby_tree import HobbyTree
from src.structures.map_graph import MapGraph
from src.structures.relationship_graph import RelationshipGraph
from src.structures.ui_stack import UIStack
from src.utils.data_loader import (
    DialogueTree,
    load_game_data,
)
from src.utils.sorter import merge_sort


@dataclass(frozen=True)
class MatchResult:
    accepted: bool
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class MatchAnalysis:
    first: dict
    second: dict
    score: int
    hobby_distance: int
    travel_distance: float
    forbidden_path: list[str] | None


class MatchmakingEngine:
    def __init__(
        self,
        profiles: list[dict],
        relationships: RelationshipGraph,
        hobbies: HobbyTree,
        map_graph: MapGraph,
        dialogue: DialogueTree,
    ) -> None:
        self.profiles = {profile["id"]: profile for profile in profiles}
        self.relationships = relationships
        self.hobbies = hobbies
        self.map_graph = map_graph
        self.dialogue = dialogue
        self.ui_stack = UIStack[str]()
        self.event_queue = EventQueue[str]()

    def analyze_pair(
        self,
        first_id: str,
        second_id: str,
        *,
        long_distance_limit: float = 8,
        hobby_distance_limit: int = 4,
    ) -> MatchAnalysis:
        first = self.profiles[first_id]
        second = self.profiles[second_id]
        forbidden = set(first.get("blacklist", [])) | set(second.get("blacklist", []))
        forbidden_path = self.relationships.first_forbidden_path(first_id, second_id, forbidden)
        hobby_distance = self.hobbies.distance(first["hobby"], second["hobby"])
        travel_distance = self.map_graph.shortest_distance(first["city"], second["city"])

        if forbidden_path is not None:
            score = 0
        else:
            score = 100
            if hobby_distance > hobby_distance_limit:
                score -= (hobby_distance - hobby_distance_limit) * 10
            if travel_distance > long_distance_limit:
                score -= int((travel_distance - long_distance_limit) * 5)

        return MatchAnalysis(
            first=first,
            second=second,
            score=max(score, 0),
            hobby_distance=hobby_distance,
            travel_distance=travel_distance,
            forbidden_path=forbidden_path,
        )

    def evaluate_match(
        self,
        first_id: str,
        second_id: str,
        *,
        long_distance_limit: float = 8,
        hobby_distance_limit: int = 4,
    ) -> MatchResult:
        first = self.profiles[first_id]
        second = self.profiles[second_id]
        reasons = []
        analysis = self.analyze_pair(
            first_id,
            second_id,
            long_distance_limit=long_distance_limit,
            hobby_distance_limit=hobby_distance_limit,
        )

        if analysis.forbidden_path is not None:
            self.event_queue.enqueue("warning_print")
            return MatchResult(
                False,
                0,
                [f"REJECT: forbidden relationship path {' -> '.join(analysis.forbidden_path)}"],
            )

        if analysis.hobby_distance > hobby_distance_limit:
            penalty = (analysis.hobby_distance - hobby_distance_limit) * 10
            reasons.append(f"Interest mismatch penalty: -{penalty}")

        if analysis.travel_distance > long_distance_limit:
            penalty = int((analysis.travel_distance - long_distance_limit) * 5)
            reasons.append(f"Long-distance penalty: -{penalty}")

        accepted = analysis.score >= 60
        reasons.append("ACCEPT" if accepted else "REJECT: score below threshold")
        self.event_queue.enqueue("match_success" if accepted else "warning_print")
        return MatchResult(accepted, analysis.score, reasons)

    def priority_profiles(self) -> list[dict]:
        return merge_sort(
            list(self.profiles.values()),
            key=lambda profile: (profile["tier_priority"], profile["success_rate"]),
            reverse=True,
        )


def build_engine(data_dir: str | Path = "assets/data") -> MatchmakingEngine:
    game_data = load_game_data(data_dir)
    return MatchmakingEngine(
        profiles=game_data.profiles,
        relationships=game_data.relationship_graph,
        hobbies=game_data.hobby_tree,
        map_graph=game_data.map_graph,
        dialogue=game_data.dialogue_tree,
    )
