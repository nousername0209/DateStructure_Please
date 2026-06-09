import random
from collections import deque
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
    PENALTY_TRAVEL = 0.2  # 한계 거리를 km 단위로 초과할 때 km당 부과되는 벌점
    SUCCESS_MATCH = 2    # 적합한 매칭을 승인했을 때 명성 상승치
    SUCCESS_REJECT = 1  # 부적합 매칭을 거절했을 때 명성 상승치
    PASS_SCORE = 60
    MATCH_GRAPH_SIZE = 16  # 관계 그래프 패널에 한 번에 표시할 인원 수

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

    def analyze_pair(
        self,
        first_id: str,
        second_id: str,
        *,
        long_distance_limit: float = 150,
        hobby_distance_limit: int = 4,
    ) -> MatchAnalysis:
        first = self.get_profile(first_id)   # 이진 탐색 호출
        second = self.get_profile(second_id) # 이진 탐색 호출
        # 다단계 연쇄(A-B, B-C => A-C) 탐색을 제거. 직접 연결된 관계 또는
        # 직접 블랙리스트(서로를 차단)만 거부 사유로 본다.
        blacklisted = second_id in first.get("blacklist", []) or first_id in second.get("blacklist", [])
        if self.relationships.is_related(first_id, second_id) or blacklisted:
            forbidden_path = [first_id, second_id]
        else:
            forbidden_path = None

        hobby_distance = self.hobbies.distance(first["hobby"], second["hobby"])
        travel_distance = self.map_graph.shortest_distance(first["city"], second["city"])

        if forbidden_path is not None:
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
        long_distance_limit: float = 150,
        hobby_distance_limit: int = 4,
    ) -> MatchResult:
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

    def select_graph_members(self, first_id: str, second_id: str) -> list[str]:
        """관계 그래프 패널에 표시할 MATCH_GRAPH_SIZE명을 고른다.
        두 매칭 대상에서 시작해 BFS로 관계가 가까운 사람부터 채우고, 연결 성분이
        소진되면 나머지는 무작위로 채운다(랜덤은 순수 미끼)."""
        size = self.MATCH_GRAPH_SIZE
        members, seen = [first_id, second_id], {first_id, second_id}
        # BFS 확장: 이미 선택된 사람과 관계된 사람을 가까운 순서로 우선 채운다.
        queue = deque([first_id, second_id])
        while queue and len(members) < size:
            current = queue.popleft()
            nbrs = list(self.relationships.neighbors(current) - seen)
            random.shuffle(nbrs)  # 같은 깊이(frontier) 안에서는 무작위 순서
            for nb in nbrs:
                if len(members) >= size:
                    break
                members.append(nb)
                seen.add(nb)
                queue.append(nb)
        # 관계로 더 못 채우면(연결 성분 소진) 나머지는 무작위로 채운다.
        if len(members) < size:
            pool = [p["id"] for p in self.profiles_by_id if p["id"] not in seen]
            random.shuffle(pool)
            for pid in pool:
                if len(members) >= size:
                    break
                members.append(pid)
                seen.add(pid)
        return members


def build_engine(data_dir: str | Path = "assets/data") -> MatchmakingEngine:
    game_data = load_game_data(data_dir)
    return MatchmakingEngine(
        profiles=game_data.profiles,
        relationships=game_data.relationship_graph,
        hobbies=game_data.hobby_tree,
        map_graph=game_data.map_graph,
        dialogue=game_data.dialogue_tree,
    )
