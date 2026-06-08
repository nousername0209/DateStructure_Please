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
from src.utils.sorter import merge_sort, binary_search_by_id


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
    # 기획자가 언제든 한 곳에서 쉽게 밸런스를 수정할 수 있도록 상수화
    PENALTY_HOBBY = 10
    PENALTY_TRAVEL = 5
    PASS_SCORE = 60

    def __init__(
        self,
        profiles: list[dict],
        relationships: RelationshipGraph,
        hobbies: HobbyTree,
        map_graph: MapGraph,
        dialogue: DialogueTree,
    ) -> None:
        # 기존 딕셔너리 방식 삭제 (이진 탐색을 안 쓰게 만드는 주범)
        # self.profiles = {profile["id"]: profile for profile in profiles}
        
        # 우리가 만든 merge_sort로 'ID 오름차순 리스트(Primary Index)' 구축
        self.profiles_by_id = merge_sort(profiles, key=lambda p: p["id"], reverse=False)
        
        self.relationships = relationships
        self.hobbies = hobbies
        self.map_graph = map_graph
        self.dialogue = dialogue
        self.ui_stack = UIStack[object]()
        self.event_queue = EventQueue[str]()
        self.reputation = 80

    def get_profile(self, profile_id: str) -> dict:
        """딕셔너리 대신 직접 구현한 이진 탐색(Binary Search)을 사용하여 프로필을 찾습니다."""
        profile = binary_search_by_id(self.profiles_by_id, profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found!")
        return profile

    def is_same_gender_pair(self, first: dict, second: dict) -> bool:
        """두 프로필의 gender 값이 같으면 동성 매칭으로 판단합니다."""
        return first.get("gender") == second.get("gender")

    def analyze_pair(
        self,
        first_id: str,
        second_id: str,
        *,
        long_distance_limit: float = 8,
        hobby_distance_limit: int = 4,
    ) -> MatchAnalysis:
        first = self.get_profile(first_id)   # 이진 탐색 호출
        second = self.get_profile(second_id) # 이진 탐색 호출
        forbidden = set(first.get("blacklist", [])) | set(second.get("blacklist", []))
        # 일방통행 버그 수정. A의 시점과 B의 시점 모두에서 금지망을 탐색.
        forbidden_path = self.relationships.first_forbidden_path(first_id, second_id, forbidden)
        if forbidden_path is None:
            # A쪽에서 문제가 없었다면, 방향을 뒤집어서 B쪽에서도 검사함
            forbidden_path = self.relationships.first_forbidden_path(second_id, first_id, forbidden)

        hobby_distance = self.hobbies.distance(first["hobby"], second["hobby"])
        travel_distance = self.map_graph.shortest_distance(first["city"], second["city"])

        if self.is_same_gender_pair(first, second):
            score = 0
        elif forbidden_path is not None:
            score = 0
        else:
            score = 100
            if hobby_distance > hobby_distance_limit:
                score -= (hobby_distance - hobby_distance_limit) * self.PENALTY_HOBBY
            if travel_distance > long_distance_limit:
                score -= int((travel_distance - long_distance_limit) * self.PENALTY_TRAVEL)

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
        first = self.get_profile(first_id)   # 이진 탐색 호출
        second = self.get_profile(second_id) # 이진 탐색 호출
        reasons = []
        analysis = self.analyze_pair(
            first_id,
            second_id,
            long_distance_limit=long_distance_limit,
            hobby_distance_limit=hobby_distance_limit,
        )

        if self.is_same_gender_pair(first, second):
            self.event_queue.enqueue("warning_print")
            return MatchResult(
                False,
                0,
                ["동성끼리의 매칭이므로 거부해야 합니다."],
            )

        if analysis.forbidden_path is not None:
            self.event_queue.enqueue("warning_print")
            return MatchResult(
                False,
                0,
                [f"금지된 관계망 적발 : {' -> '.join(analysis.forbidden_path)}"],
            )

        if analysis.hobby_distance > hobby_distance_limit:
            penalty = (analysis.hobby_distance - hobby_distance_limit) * self.PENALTY_HOBBY
            reasons.append(f"취미가 맞지 않음. 벌점 부과 : -{penalty}")

        if analysis.travel_distance > long_distance_limit:
            penalty = int((analysis.travel_distance - long_distance_limit) * self.PENALTY_TRAVEL)
            reasons.append(f"거리가 너무 멂. 벌점 부과 : -{penalty}")

        accepted = analysis.score >= self.PASS_SCORE
        reasons.append("최종 승인 (적합한 매칭)" if accepted else "최종 거절 (기준 점수 미달)")
        self.event_queue.enqueue("match_success" if accepted else "warning_print")
        return MatchResult(accepted, analysis.score, reasons)

    def priority_profiles(self) -> list[dict]:
        return merge_sort(
            self.profiles_by_id, # ID로 정렬된 원본 리스트를 가져와서 다시 정렬
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
