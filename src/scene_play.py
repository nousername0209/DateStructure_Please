from dataclasses import dataclass
import math
from pathlib import Path

import pygame
import itertools
import random
from collections import deque  # 프로젝트의 EventQueue를 못 찾을 경우를 대비한 가장 안전하고 엄밀한 내장 큐

from src.engine import MatchAnalysis, MatchmakingEngine


WIDTH = 960
HEIGHT = 640
FPS = 60
BG = (245, 242, 236)
INK = (34, 36, 40)
MUTED = (104, 108, 116)
CARD = (255, 255, 252)
LINE = (210, 204, 194)
ACCENT = (38, 116, 92)
WARN = (178, 61, 48)
BLUE = (48, 86, 150)
GRAY = (214, 214, 214)


@dataclass(frozen=True)
class Button:
    rect: pygame.Rect
    label: str
    action: str
    color: tuple[int, int, int]

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font) -> None:
        pygame.draw.rect(screen, self.color, self.rect, border_radius=8)
        label = font.render(self.label, True, (255, 255, 255))
        screen.blit(label, label.get_rect(center=self.rect.center))


class UIContext:
    """Small object-oriented drawing surface for scene UI widgets."""

    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        self.screen = screen
        self.fonts = fonts
        self.buttons: list[Button] = []

    def text(
        self,
        font_name: str,
        text: str,
        pos: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        self.screen.blit(self.fonts[font_name].render(text, True, color), pos)

    def button(
        self,
        rect: pygame.Rect,
        label: str,
        action: str,
        color: tuple[int, int, int],
    ) -> Button:
        button = Button(rect, label, action, color)
        button.draw(self.screen, self.fonts["body"])
        self.buttons.append(button)
        return button

    def scrim(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 20, 20, 120))
        self.screen.blit(overlay, (0, 0))

    def popup_frame(
        self,
        rect: pygame.Rect,
        title: str,
        color: tuple[int, int, int],
        depth: int,
        *,
        fill: tuple[int, int, int] = CARD,
    ) -> None:
        shadow = pygame.Surface((rect.width + 18, rect.height + 18), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 0))
        pygame.draw.rect(shadow, (22, 24, 28, 70), shadow.get_rect(), border_radius=10)
        self.screen.blit(shadow, (rect.x + 10 + depth * 2, rect.y + 12 + depth * 2))

        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        title_bar = pygame.Rect(rect.x, rect.y, rect.width, 54)
        pygame.draw.rect(self.screen, (250, 242, 232), title_bar, border_top_left_radius=8, border_top_right_radius=8)
        pygame.draw.line(self.screen, LINE, (rect.x, title_bar.bottom), (rect.right, title_bar.bottom), 2)
        pygame.draw.rect(self.screen, color, rect, 3, border_radius=8)
        self.text("popup_title", title, (rect.x + 24, rect.y + 16), color)

    def wrap_text(self, font_name: str, text: str, max_width: int) -> list[str]:
        font = self.fonts[font_name]
        words = text.split(" ")
        lines: list[str] = []
        current_line = ""

        for word in words:
            candidate = f"{current_line} {word}" if current_line else word
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines


class UILayer:
    def draw(self, scene: "PlayScene", ui: UIContext, depth: int) -> None:
        raise NotImplementedError

    def handle_click(self, scene: "PlayScene", pos: tuple[int, int]) -> bool:
        return False

    def on_escape(self, scene: "PlayScene") -> bool:
        scene.close_top_layer()
        return True


class DialoguePopup(UILayer):
    def draw(self, scene: "PlayScene", ui: UIContext, depth: int) -> None:
        dialogue = scene.engine.dialogue.current
        panel = pygame.Rect(92 + depth * 28, 86 + depth * 20, WIDTH - 184, 348)
        ui.popup_frame(panel, "Dialogue", BLUE, depth)
        ui.button(pygame.Rect(panel.right - 116, panel.y + 14, 88, 34), "CLOSE", "close_dialogue", WARN)

        text_lines = ui.wrap_text("body", dialogue.text, panel.width - 48)
        line_y = panel.y + 84
        for line in text_lines:
            ui.text("body", line, (panel.x + 24, line_y), INK)
            line_y += ui.fonts["body"].get_height() + 6

        if scene.dialogue_history:
            ui.button(pygame.Rect(panel.right - 212, panel.y + 14, 84, 34), "뒤로", "dialogue_back", WARN)

        if dialogue.choices:
            choice_y = line_y + 16
            for index, choice in enumerate(dialogue.choices):
                button_rect = pygame.Rect(panel.x + 24, choice_y, panel.width - 48, 48)
                ui.button(button_rect, choice["label"], f"dialogue_choice_{index}", ACCENT)
                choice_y += 60
        else:
            info_text = "선택지가 없습니다. ESC를 눌러 대화를 종료하거나 뒤로 가기 버튼을 누르세요." if scene.dialogue_history else "선택지가 없습니다. ESC를 눌러 대화를 종료하세요."
            ui.text("small", info_text, (panel.x + 24, panel.bottom - 40), MUTED)

    def handle_click(self, scene: "PlayScene", pos: tuple[int, int]) -> bool:
        for button in scene.buttons:
            if not button.contains(pos):
                continue
            if button.action == "close_dialogue":
                scene.close_top_layer()
                return True
            if button.action.startswith("dialogue_choice"):
                scene.dialogue_history.append(scene.engine.dialogue.current_id)
                choice_index = int(button.action.split("_")[-1])
                scene.engine.dialogue.choose(choice_index)
                return True
            if button.action == "dialogue_back":
                scene.go_back_dialogue()
                return True
        return True


class AssetPopup(UILayer):
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.cached_layout: dict[str, tuple[int, int]] | None = None

    def draw(self, scene: "PlayScene", ui: UIContext, depth: int) -> None:
        title_map = {
            "tree": "동적 렌더링: 취미 트리",
            "graph_rel": "동적 렌더링: 관계도 (구현 대기)",
            "graph_city": "물리 기반 렌더링: 대한민국 도시망",
        }
        title = title_map.get(self.kind, "Asset")
        rect = pygame.Rect(112 + depth * 28, 74 + depth * 22, WIDTH - 224, HEIGHT - 142)
        ui.popup_frame(rect, title, ACCENT, depth)

        content_rect = pygame.Rect(rect.x + 32, rect.y + 74, rect.width - 64, rect.height - 104)

        if self.kind == "graph_city":
            self._draw_map_graph(scene, ui, content_rect)
        elif self.kind == "tree":
            self._draw_hobby_tree(scene, ui, content_rect)
        else:
            ui.text("heading", "해당 그래프 렌더러는 아직 준비되지 않았습니다.", (rect.x + 28, rect.y + 92), WARN)

        ui.button(pygame.Rect(rect.right - 132, rect.y + 14, 104, 34), "CLOSE", "close_asset", WARN)
        ui.text("small", "ESC를 눌러 닫기", (rect.x + 28, rect.bottom - 32), MUTED)

    def _compute_physics_layout(self, map_data: dict, area: pygame.Rect) -> dict[str, tuple[int, int]]:
        cities = list(map_data.keys())
        if not cities: return {}

        center_x, center_y = area.width / 2, area.height / 2
        positions = {city: [center_x + random.randint(-50, 50), center_y + random.randint(-50, 50)] for city in cities}
        velocities = {city: [0.0, 0.0] for city in cities}

        max_dist = max([d for edges in map_data.values() for _, d in edges] + [1])
        SCALE = (min(area.width, area.height) * 0.6) / max_dist

        ITERATIONS = 150
        REPULSION = 5000.0
        SPRING_K = 0.1
        DAMPING = 0.85

        for _ in range(ITERATIONS):
            forces = {city: [0.0, 0.0] for city in cities}

            for i in range(len(cities)):
                for j in range(i + 1, len(cities)):
                    c1, c2 = cities[i], cities[j]
                    p1, p2 = positions[c1], positions[c2]
                    dx, dy = p1[0] - p2[0], p1[1] - p2[1]
                    dist = math.hypot(dx, dy)
                    if dist == 0: dist, dx, dy = 0.1, random.random(), random.random()
                    
                    force = REPULSION / (dist * dist)
                    forces[c1][0] += (dx / dist) * force
                    forces[c1][1] += (dy / dist) * force
                    forces[c2][0] -= (dx / dist) * force
                    forces[c2][1] -= (dy / dist) * force

            drawn_edges = set()
            for city, edges in map_data.items():
                for neighbor, distance in edges:
                    edge_pair = tuple(sorted([city, neighbor]))
                    if edge_pair not in drawn_edges:
                        drawn_edges.add(edge_pair)
                        p1, p2 = positions[city], positions[neighbor]
                        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                        dist = math.hypot(dx, dy)
                        if dist == 0: dist = 0.1
                        
                        ideal_dist = distance * SCALE
                        force = (dist - ideal_dist) * SPRING_K
                        forces[city][0] += (dx / dist) * force
                        forces[city][1] += (dy / dist) * force
                        forces[neighbor][0] -= (dx / dist) * force
                        forces[neighbor][1] -= (dy / dist) * force

            for city in cities:
                velocities[city][0] = (velocities[city][0] + forces[city][0]) * DAMPING
                velocities[city][1] = (velocities[city][1] + forces[city][1]) * DAMPING
                positions[city][0] += velocities[city][0]
                positions[city][1] += velocities[city][1]

        avg_x = sum(p[0] for p in positions.values()) / len(cities)
        avg_y = sum(p[1] for p in positions.values()) / len(cities)
        offset_x = center_x - avg_x
        offset_y = center_y - avg_y

        final_coords = {}
        for city, p in positions.items():
            final_coords[city] = (int(area.x + p[0] + offset_x), int(area.y + p[1] + offset_y))
            
        return final_coords

    def _draw_map_graph(self, scene: "PlayScene", ui: UIContext, area: pygame.Rect) -> None:
        map_data = scene.engine.map_graph.adjacency
        
        if self.cached_layout is None:
            self.cached_layout = self._compute_physics_layout(map_data, area)
            
        pixel_coords = self.cached_layout

        drawn_edges = set()
        for city, edges in map_data.items():
            for neighbor, distance in edges:
                edge_pair = tuple(sorted([city, neighbor]))
                if edge_pair not in drawn_edges:
                    drawn_edges.add(edge_pair)
                    
                    p1, p2 = pixel_coords[city], pixel_coords.get(neighbor)
                    if p1 and p2:
                        pygame.draw.line(ui.screen, LINE, p1, p2, 4)
                        
                        mid_x, mid_y = (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2
                        dist_text = f"{distance}km"
                        text_surf = ui.fonts["small"].render(dist_text, True, BLUE)
                        text_rect = text_surf.get_rect(center=(mid_x, mid_y))
                        
                        bg_rect = text_rect.inflate(8, 4)
                        pygame.draw.rect(ui.screen, CARD, bg_rect, border_radius=4)
                        ui.screen.blit(text_surf, text_rect)

        for city, pos in pixel_coords.items():
            pygame.draw.circle(ui.screen, ACCENT, pos, 18)
            pygame.draw.circle(ui.screen, CARD, pos, 18, 3)
            
            text_surf = ui.fonts["body"].render(city, True, INK)
            text_rect = text_surf.get_rect(center=(pos[0], pos[1] + 28))
            ui.screen.blit(text_surf, text_rect)

    def _draw_hobby_tree(self, scene: "PlayScene", ui: UIContext, area: pygame.Rect) -> None:
        root = scene.engine.hobbies.root
        if not root:
            return

        max_depth = max(node.depth for node in scene.engine.hobbies.nodes.values())
        y_step = area.height // (max_depth + 1) if max_depth > 0 else 0

        def draw_node(node, x_min, x_max, current_y):
            x = (x_min + x_max) // 2
            y = current_y

            if node.children:
                child_width = (x_max - x_min) // len(node.children)
                for i, child in enumerate(node.children):
                    child_x_min = x_min + i * child_width
                    child_x_max = child_x_min + child_width
                    child_x = (child_x_min + child_x_max) // 2
                    child_y = current_y + y_step
                    
                    pygame.draw.line(ui.screen, LINE, (x, y), (child_x, child_y), 3)
                    draw_node(child, child_x_min, child_x_max, child_y)

            pygame.draw.rect(ui.screen, CARD, (x - 40, y - 15, 80, 30), border_radius=5)
            pygame.draw.rect(ui.screen, ACCENT, (x - 40, y - 15, 80, 30), 2, border_radius=5)
            
            text_surf = ui.fonts["small"].render(node.name, True, INK)
            text_rect = text_surf.get_rect(center=(x, y))
            ui.screen.blit(text_surf, text_rect)

        draw_node(root, area.x, area.right, area.y + 30)

    def handle_click(self, scene: "PlayScene", pos: tuple[int, int]) -> bool:
        for button in scene.buttons:
            if button.contains(pos) and button.action == "close_asset":
                scene.close_top_layer()
                return True
        return True

class PlayScene:
    """Pygame play loop for pair review and contradiction rejection."""

    def __init__(self, engine: MatchmakingEngine) -> None:
        self.engine = engine
        self.profiles = self.engine.priority_profiles()

        # --- 핵심 추가 로직 --- 임호준
        # 1. profiles에 있는 모든 사람들의 가능한 모든 2명 짝(조합)을 리스트로 만듦
        self.match_queue = list(itertools.combinations(self.profiles, 2))
        # 2. 플레이할 때마다 매칭 순서가 달라지도록 섞음 (난수화)
        random.shuffle(self.match_queue)
        # ------------------------
        
        self.pair_index = 0
        self.game_state = "playing" # 이 줄을 추가 ("playing", "game_over", "clear" 상태를 가질 예정) -호준
        # 기획서 요건을 충족하는 UI 이벤트 큐(Queue) 파이프라인 생성
        self.message_queue = deque()
        self.buttons: list[Button] = []
        self.notice_text = ""
        self.notice_timer = 0.0
        self.dialogue_history: list[str] = []
        self.tree_image: pygame.Surface | None = None
        self.graph_rel_image: pygame.Surface | None = None
        self.graph_city_image: pygame.Surface | None = None
        self.asset_dir = Path(__file__).resolve().parents[1] / "assets" / "data"
        self.engine.ui_stack.clear()
        self.engine.ui_stack.push(DialoguePopup())

    def run(self) -> None:
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("DateStructure, Please")
        clock = pygame.time.Clock()
        self.tree_image = pygame.image.load(str(self.asset_dir / "tree.png")).convert_alpha()
        self.graph_rel_image = pygame.image.load(str(self.asset_dir / "graph_rel.png")).convert_alpha()
        self.graph_city_image = pygame.image.load(str(self.asset_dir / "graph_city.png")).convert_alpha()
        fonts = {
            "title": pygame.font.SysFont(["malgungothic", 'applegothic'], 34),
            "heading": pygame.font.SysFont(["malgungothic", 'applegothic'], 24),
            "body": pygame.font.SysFont(["malgungothic",'applegothic'], 18),
            "small": pygame.font.SysFont(["malgungothic",'applegothic'], 15),
            "popup_title": pygame.font.SysFont(["malgungothic",'applegothic'], 20),
        }

        running = True
        while running:
            dt = clock.tick(FPS) / 1000
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = self._handle_escape()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)

            self._update(dt)
            self._draw(screen, fonts)
            pygame.display.flip()

        pygame.quit()

    def _current_pair(self) -> tuple[dict, dict]:
        # 기존의 i, i+2 억지 공식을 버리고, 우리가 만든 매칭 대기열(queue)에서 순서대로 꺼내오기 - by 호준
        pair = self.match_queue[self.pair_index % len(self.match_queue)]
        return pair[0], pair[1]

    def _analysis(self) -> MatchAnalysis:
        first, second = self._current_pair()
        return self.engine.analyze_pair(first["id"], second["id"])

    def analysis(self) -> MatchAnalysis:
        return self._analysis()

    def _handle_click(self, pos: tuple[int, int]) -> None:
        top_layer = self.engine.ui_stack.peek()
        if isinstance(top_layer, UILayer):
            top_layer.handle_click(self, pos)
            return

        for button in self.buttons:
            if button.contains(pos):
                if button.action == "restart":      
                    self._restart_game()
                elif button.action == "reject":
                    self._reject_pair()
                elif button.action == "next":
                    first, second = self._current_pair()
                    result = self.engine.evaluate_match(first["id"], second["id"])
                    
                    if result.accepted:
                        self.message_queue.append(f"승인 성공! 매칭 점수: {result.score}점")
                    else:
                        self.engine.reputation = max(0, self.engine.reputation - 10)
                        reason_str = " / ".join(result.reasons)
                        self.message_queue.append(f"오심! 부적합 매칭 승인. 사유: {reason_str}")

                    # 수정됨: % 연산 제거 및 상태 검사 추가 - 호준
                    self.pair_index += 1
                    #self.notice_timer = 3.0
                    self._update_game_state()

                elif button.action == "tree":
                    self.engine.ui_stack.push(AssetPopup("tree"))
                    self.notice_text = ""
                elif button.action == "graph_rel":
                    self.engine.ui_stack.push(AssetPopup("graph_rel"))
                    self.notice_text = ""
                elif button.action == "graph_city":
                    self.engine.ui_stack.push(AssetPopup("graph_city"))
                    self.notice_text = ""
                return

    def _handle_escape(self) -> bool:
        top_layer = self.engine.ui_stack.peek()
        if isinstance(top_layer, UILayer):
            return top_layer.on_escape(self)
        return False

    def _reject_pair(self) -> None:
        first, second = self._current_pair()
        result = self.engine.evaluate_match(first["id"], second["id"])
        
        if not result.accepted:
            self.message_queue.append(f"정확한 판단입니다! 사유: {result.reasons[0]}") # Enqueue
        else:
            self.engine.reputation = max(0, self.engine.reputation - 10)
            self.message_queue.append(f"오심입니다! 적합한 매칭을 거절했습니다. (점수: {result.score}점)") # Enqueue

        # 수정: % len(self.match_queue) 를 빼버려서 무한루프를 막기 - 호준
        self.pair_index += 1 
        #self.notice_timer = 3.0
        self._update_game_state() # 매 판정이 끝날 때마다 상태 검사

    def close_top_layer(self) -> None:
        if isinstance(self.engine.ui_stack.peek(), UILayer):
            self.engine.ui_stack.pop()

    def _update(self, dt: float) -> None:
        # 1. 화면에 떠 있는 메시지가 있다면 일단 타이머를 줄입니다.
        if self.notice_timer > 0:
            self.notice_timer = max(0, self.notice_timer - dt)
            if self.notice_timer == 0:
                self.notice_text = "" 

        # 2. UX(조작감) 개선 로직: 큐에 새 이벤트(메시지)가 들어왔다면 즉시 모조리 꺼냄
        while len(self.message_queue) > 0:
            # 큐에서 순서대로 빼내되, 가장 최신(마지막) 이벤트가 notice_text를 차지하게 됨
            self.notice_text = self.message_queue.popleft() 
            self.notice_timer = 3.0 # 타이머를 즉시 3초로 초기화 (기존 대기시간 무시)

    def _draw(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        analysis = self._analysis()
        screen.fill(BG)
        ui = UIContext(screen, fonts)

        ui.text("title", "DateStructure, Please", (40, 30), INK)
        ui.text("body", "Moderator review desk", (44, 72), MUTED)
        self._draw_reputation(ui)
        self._draw_profile_card(ui, analysis.first, pygame.Rect(46, 128, 350, 250))
        self._draw_profile_card(ui, analysis.second, pygame.Rect(564, 128, 350, 250))
        self._draw_asset_buttons(ui)
        self._draw_actions(ui)

        overlays = self.engine.ui_stack.items()
        if overlays:
            ui.scrim()

        for depth, layer in enumerate(overlays):
            layer.draw(self, ui, depth)

        self.buttons = ui.buttons

        # 이 부분을 추가함 - 호준
        if self.game_state != "playing":
            ui.buttons = [] # 배경에 있는 기존 플레이용 버튼들을 비활성화
            self._draw_end_screen(ui) # 엔딩 창과 RESTART 버튼 렌더링
            
        self.buttons = ui.buttons # 최종적으로 클릭 가능한 버튼들을 확정

    def _draw_reputation(self, ui: UIContext) -> None:
        box = pygame.Rect(724, 26, 190, 52)
        pygame.draw.rect(ui.screen, GRAY, box, border_radius=8)
        pygame.draw.rect(ui.screen, LINE, box, 2, border_radius=8)
        ui.text("body", f"Reputation: {self.engine.reputation}", (box.x + 18, box.y + 15), INK)

    def _draw_profile_card(
        self,
        ui: UIContext,
        profile: dict,
        rect: pygame.Rect,
    ) -> None:
        pygame.draw.rect(ui.screen, CARD, rect, border_radius=8)
        pygame.draw.rect(ui.screen, LINE, rect, 2, border_radius=8)
        ui.text("heading", profile["name"], (rect.x + 24, rect.y + 24), INK)
        ui.text("body", f"ID: {profile['id']}", (rect.x + 24, rect.y + 70), MUTED)
        ui.text("body", f"City: {profile['city']}", (rect.x + 24, rect.y + 106), INK)
        ui.text("body", f"Hobby: {profile['hobby']}", (rect.x + 24, rect.y + 142), INK)
        #ui.text("body", f"Tier: {profile['tier']}", (rect.x + 24, rect.y + 178), INK)
        #ui.text("small", f"Suspicion: {profile['suspicion']}", (rect.x + 24, rect.y + 218), WARN)

    def _draw_analysis_panel(
        self,
        ui: UIContext,
        analysis: MatchAnalysis,
    ) -> None:
        # Matching Analysis 박스 UI는 제거되었으나 분석은 내부적으로 계속 진행됨
        pass

    def _draw_asset_buttons(self, ui: UIContext) -> None:
        panel = pygame.Rect(278, 410, 404, 150)
        pygame.draw.rect(ui.screen, (250, 249, 244), panel, border_radius=8)
        pygame.draw.rect(ui.screen, LINE, panel, 2, border_radius=8)
        ui.text("heading", "그래프 보기", (panel.x + 24, panel.y + 18), INK)

    def _draw_actions(self, ui: UIContext) -> None:
        ui.button(pygame.Rect(46, 514, 170, 52), "REJECT", "reject", WARN)
        ui.button(pygame.Rect(744, 514, 170, 52), "NEXT PAIR", "next", ACCENT)
        
        # Asset buttons (그래프 보기 패널 내)
        panel = pygame.Rect(278, 410, 404, 150)
        button_width = 110
        button_height = 80
        button_y = panel.y + 54
        spacing = 12
        start_x = panel.x + 24
        
        # 수정 전 : ui.button(pygame.Rect(start_x, button_y, button_width, button_height), "관계도\n(Tree)", "tree", ACCENT)
        ui.button(pygame.Rect(start_x, button_y, button_width, button_height), "취미 트리\n(Tree)", "tree", ACCENT)
        ui.button(pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height), "관계\n그래프", "graph_rel", ACCENT)
        ui.button(pygame.Rect(start_x + (button_width + spacing) * 2, button_y, button_width, button_height), "도시\n그래프", "graph_city", ACCENT)
        
        if self.notice_text:
            ui.text("small", self.notice_text, (46, 588), WARN)
    # 추가함 - 호준
    def _update_game_state(self) -> None:
        """명성이나 큐 상태를 확인하여 게임 오버 또는 클리어 상태로 전환"""
        if self.engine.reputation <= 0:
            self.game_state = "game_over"
        elif self.pair_index >= len(self.match_queue):
            self.game_state = "clear"

    def _draw_end_screen(self, ui: UIContext) -> None:
        """게임 오버 또는 클리어 시 화면을 덮는 팝업과 재시작 버튼을 그림"""
        ui.scrim() # 배경을 어둡게 처리
        
        # 패널 높이를 200에서 230으로 살짝 키워서 겹침을 방지함
        panel = pygame.Rect(WIDTH // 2 - 200, HEIGHT // 2 - 115, 400, 230)
        
        if self.game_state == "game_over":
            ui.popup_frame(panel, "GAME OVER", WARN, 0)
            ui.text("heading", "해고되었습니다.", (panel.x + 130, panel.y + 60), WARN)
            ui.text("body", "명성이 바닥나 심사관 자격을 박탈당했습니다.", (panel.x + 30, panel.y + 100), INK)
        elif self.game_state == "clear":
            ui.popup_frame(panel, "STAGE CLEAR", ACCENT, 0)
            ui.text("heading", "오늘의 업무 종료", (panel.x + 115, panel.y + 60), ACCENT)
            ui.text("body", f"성공적으로 업무를 마쳤습니다! (남은 명성: {self.engine.reputation})", (panel.x + 35, panel.y + 100), INK)
        
        # 버튼은 패널 하단에서 80픽셀 위로 올려서 넉넉하게 배치
        ui.button(pygame.Rect(panel.x + 130, panel.bottom - 80, 140, 40), "RESTART", "restart", BLUE)
        
        # 안내 텍스트는 버튼 아래인 하단에서 25픽셀 위로 배치하여 절대 겹치지 않게
        ui.text("small", "ESC를 눌러 게임을 종료하세요.", (panel.x + 95, panel.bottom - 25), MUTED)
    
    def go_back_dialogue(self) -> None:
        if not self.dialogue_history:
            return
        previous_id = self.dialogue_history.pop()
        self.engine.dialogue.current_id = previous_id

    def _restart_game(self) -> None:
        """게임을 초기 상태로 되돌리고 재시작"""
        self.game_state = "playing"
        self.pair_index = 0
        self.engine.reputation = 80  # 명성을 초기 점수(80점)로 복구
        random.shuffle(self.match_queue)  # 큐를 다시 섞어서 새로운 패턴 제공
        # 메시지 큐 비우기
        self.message_queue.clear() 
        self.notice_text = ""
        self.notice_timer = 0.0

        # 대화 트리 상태 초기화
        self.engine.dialogue.reset_to_root() 
        # UI 대화 뒤로가기 기록도 완벽히 비워줌 (이거 안 비우면 뒤로가기 눌렀을 때 버그 남)
        self.dialogue_history.clear()        
        
        self.engine.ui_stack.clear()
        
        # 대화창 띄우기
        self.engine.ui_stack.push(DialoguePopup())

def run_game(engine: MatchmakingEngine) -> None:
    PlayScene(engine).run()
