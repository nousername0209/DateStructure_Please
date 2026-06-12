from array import array
from dataclasses import dataclass
import math
from pathlib import Path
import random
from collections import deque

import pygame

from src.engine import MatchAnalysis, MatchmakingEngine


WIDTH = 960
HEIGHT = 640
FPS = 60
BG = (238, 235, 228)
INK = (33, 36, 42)
MUTED = (106, 110, 118)
CARD = (255, 255, 252)
LINE = (207, 200, 190)
ACCENT = (39, 125, 97)
WARN = (184, 67, 52)
BLUE = (50, 91, 158)
GRAY = (218, 218, 218)
SOFT_RED = (255, 235, 231)
PORTRAIT_BG = (235, 231, 222)

# 프로필 카드 초상화: assets/img의 {gender}_{1..AVATAR_VARIANTS}.png를 정사각형으로 표시한다.
AVATAR_SIZE = 116
AVATAR_VARIANTS = 17

# 관계 종류별 화살표 색상. adjacency에 저장된 kind 문자열로 조회한다.
REL_COLORS = {"best_friend": ACCENT, "ex_partner": BLUE, "scam_partner": WARN}
REL_DEFAULT_COLOR = MUTED


@dataclass(frozen=True)
class Button:
    rect: pygame.Rect
    label: str
    action: str
    color: tuple[int, int, int]

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def draw(self, screen: pygame.Surface, font: pygame.font.Font, mouse_pos: tuple[int, int]) -> None:
        hovered = self.contains(mouse_pos)
        color = tuple(min(255, c + 18) for c in self.color) if hovered else self.color
        shadow = pygame.Rect(self.rect.x + 2, self.rect.y + 3, self.rect.width, self.rect.height)
        pygame.draw.rect(screen, (0, 0, 0, 28), shadow, border_radius=8)
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (255, 255, 255, 70), self.rect, 1, border_radius=8)
        label = font.render(self.label, True, (255, 255, 255))
        screen.blit(label, label.get_rect(center=self.rect.center))


class UIContext:
    def __init__(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        self.screen = screen
        self.fonts = fonts
        self.buttons: list[Button] = []
        self.mouse_pos = pygame.mouse.get_pos()

    def text(self, font_name: str, text: str, pos: tuple[int, int], color: tuple[int, int, int]) -> None:
        self.screen.blit(self.fonts[font_name].render(text, True, color), pos)

    def button(self, rect: pygame.Rect, label: str, action: str, color: tuple[int, int, int]) -> Button:
        button = Button(rect, label, action, color)
        button.draw(self.screen, self.fonts["body"], self.mouse_pos)
        self.buttons.append(button)
        return button

    def scrim(self) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 20, 20, 125))
        self.screen.blit(overlay, (0, 0))

    def popup_frame(self, rect: pygame.Rect, title: str, color: tuple[int, int, int], depth: int, *, fill: tuple[int, int, int] = CARD) -> None:
        shadow = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (22, 24, 28, 64), shadow.get_rect(), border_radius=12)
        self.screen.blit(shadow, (rect.x + 10 + depth * 3, rect.y + 12 + depth * 3))
        pygame.draw.rect(self.screen, fill, rect, border_radius=10)
        pygame.draw.rect(self.screen, color, rect, 3, border_radius=10)
        pygame.draw.line(self.screen, LINE, (rect.x, rect.y + 58), (rect.right, rect.y + 58), 2)
        self.text("popup_title", title, (rect.x + 24, rect.y + 18), color)

    def wrap_text(self, font_name: str, text: str, max_width: int) -> list[str]:
        font = self.fonts[font_name]
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            candidate = f"{current} {word}" if current else word
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
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
        panel = pygame.Rect(64 + depth * 16, 28 + depth * 12, WIDTH - 128, HEIGHT - 56)
        ui.popup_frame(panel, "Briefing", BLUE, depth)
        ui.button(pygame.Rect(panel.right - 118, panel.y + 14, 90, 34), "CLOSE", "close_dialogue", WARN)

        button_height = 42
        button_gap = 12
        choice_count = len(dialogue.choices)
        choices_height = choice_count * button_height + max(0, choice_count - 1) * button_gap
        choice_y = panel.bottom - 30 - choices_height
        text_area_bottom = choice_y - 24

        y = panel.y + 84
        for line in ui.wrap_text("body", dialogue.text, panel.width - 56):
            if y + ui.fonts["body"].get_height() > text_area_bottom:
                break
            ui.text("body", line, (panel.x + 28, y), INK)
            y += ui.fonts["body"].get_height() + 7

        if scene.dialogue_history:
            ui.button(pygame.Rect(panel.right - 214, panel.y + 14, 82, 34), "BACK", "dialogue_back", BLUE)

        for index, choice in enumerate(dialogue.choices):
            ui.button(
                pygame.Rect(panel.x + 28, choice_y + index * (button_height + button_gap), panel.width - 56, button_height),
                choice["label"],
                f"dialogue_choice_{index}",
                ACCENT,
            )

    def handle_click(self, scene: "PlayScene", pos: tuple[int, int]) -> bool:
        for button in scene.buttons:
            if not button.contains(pos):
                continue
            scene._play_sound("click")
            if button.action == "close_dialogue":
                scene.close_top_layer()
                return True
            if button.action == "dialogue_back":
                scene.go_back_dialogue()
                return True
            if button.action.startswith("dialogue_choice"):
                scene.dialogue_history.append(scene.engine.dialogue.current_id)
                scene.engine.dialogue.choose(int(button.action.split("_")[-1]))
                return True
        return True


class AssetPopup(UILayer):
    def __init__(self, kind: str) -> None:
        self.kind = kind

    def draw(self, scene: "PlayScene", ui: UIContext, depth: int) -> None:
        titles = {"tree": "Hobby Tree", "graph_rel": "Relationship Graph", "graph_city": "City Distance Graph"}
        rect = pygame.Rect(96 + depth * 24, 70 + depth * 18, WIDTH - 192, HEIGHT - 130)
        ui.popup_frame(rect, titles.get(self.kind, "Graph"), ACCENT, depth)
        area = pygame.Rect(rect.x + 36, rect.y + 82, rect.width - 72, rect.height - 128)
        if self.kind == "tree":
            self._draw_hobby_tree(scene, ui, area)
        elif self.kind == "graph_rel":
            self._draw_relationship_graph(scene, ui, area)
        else:
            self._draw_city_graph(scene, ui, area)
        ui.button(pygame.Rect(rect.right - 132, rect.y + 14, 104, 34), "CLOSE", "close_asset", WARN)
        ui.text("small", "ESC closes this panel", (rect.x + 28, rect.bottom - 32), MUTED)

    def _draw_city_graph(self, scene: "PlayScene", ui: UIContext, area: pygame.Rect) -> None:
        graph = scene.engine.map_graph.adjacency
        positions = scene.engine.map_graph.positions
        cities = list(graph.keys())
        if not cities:
            return
        # 한반도 모양을 본뜬 고정 좌표(정규화 0..1)를 패널 안쪽 사각형으로 매핑.
        # 좌표가 없는 도시는 기존 원형 배치로 폴백한다.
        margin = 10  # 노드 반지름(18) + 라벨 여백
        inner = area.inflate(-margin * 2, -margin * 2)
        radius = min(area.width, area.height) // 2 - 44
        coords = {}
        for i, city in enumerate(cities):
            if city in positions:
                nx, ny = positions[city]
                coords[city] = (int(inner.x + nx * inner.width), int(inner.y + ny * inner.height))
            else:
                angle = 2 * math.pi * i / len(cities) - math.pi / 2
                coords[city] = (int(area.centerx + math.cos(angle) * radius), int(area.centery + math.sin(angle) * radius))
        seen = set()
        for city, edges in graph.items():
            for neighbor, distance in edges:
                edge = tuple(sorted((city, neighbor)))
                if edge in seen:
                    continue
                seen.add(edge)
                p1, p2 = coords[city], coords[neighbor]
                pygame.draw.line(ui.screen, LINE, p1, p2, 3)
                mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
                label = ui.fonts["small"].render(str(distance), True, BLUE)
                pygame.draw.rect(ui.screen, CARD, label.get_rect(center=mid).inflate(8, 4), border_radius=4)
                ui.screen.blit(label, label.get_rect(center=mid))
        for city, pos in coords.items():
            pygame.draw.circle(ui.screen, ACCENT, pos, 14)
            pygame.draw.circle(ui.screen, CARD, pos, 14, 3)
            label = ui.fonts["small"].render(city, True, INK)
            ui.screen.blit(label, label.get_rect(center=(pos[0], pos[1] + 18)))

    def _draw_relationship_graph(self, scene: "PlayScene", ui: UIContext, area: pygame.Rect) -> None:
        # 현재 페어 기준 15명만 표시(페어가 바뀔 때만 재계산되는 캐시).
        members = scene._relationship_members()
        if not members:
            return
        member_set = set(members)
        first, second = scene._current_pair()
        matched = {first["id"], second["id"]}
        adjacency = scene.engine.relationships.adjacency
        radius = min(area.width, area.height) // 2 - 20
        # 심사 중인 두 사람을 원의 정반대(위/아래)에 배치하고, 나머지는 빈 자리를 순서대로 채운다.
        n = len(members)
        half = n // 2
        ordered: list[str | None] = [None] * n
        ordered[0] = members[0]       # first → 맨 위
        ordered[half] = members[1]    # second → 정반대편
        open_slots = [i for i in range(n) if ordered[i] is None]
        for slot, node in zip(open_slots, members[2:]):
            ordered[slot] = node
        coords = {}
        for pos, node in enumerate(ordered):
            angle = 2 * math.pi * pos / n - math.pi / 2
            # skew left: 100px shift
            coords[node] = (int(area.centerx - 100 + math.cos(angle) * radius), int(area.centery + math.sin(angle) * radius))
        # 선택된 15명 사이의 간선만(유도 부분그래프) 그린다. 관계는 방향이 없으므로 화살표 없이 색상 선.
        for source in members:
            for target, kind in adjacency.get(source, {}).items():
                if target in member_set:
                    color = REL_COLORS.get(kind, REL_DEFAULT_COLOR)
                    pygame.draw.line(ui.screen, color, coords[source], coords[target], 2)
        for node in members:
            pos = coords[node]
            pygame.draw.circle(ui.screen, CARD, pos, 10)
            # 심사 중인 두 사람은 초록 링으로 강조해 한눈에 찾도록 한다.
            if node in matched:
                pygame.draw.circle(ui.screen, ACCENT, pos, 10, 4)
            else:
                pygame.draw.circle(ui.screen, INK, pos, 10, 2)
            label = ui.fonts["small"].render(node, True, INK)
            ui.screen.blit(label, label.get_rect(center=(pos[0], pos[1] + 18)))
        self._draw_rel_legend(ui, area)

    def _draw_rel_legend(self, ui: UIContext, area: pygame.Rect) -> None:
        rows = [("best_friend", ACCENT), ("ex_partner", BLUE), ("scam_partner", WARN)]
        pad, row_h, seg = 10, 24, 34
        box_w, box_h = 178, pad * 2 + row_h * (len(rows) + 1)
        box = pygame.Rect(area.right - box_w, area.y, box_w, box_h)
        pygame.draw.rect(ui.screen, CARD, box, border_radius=8)
        pygame.draw.rect(ui.screen, LINE, box, 1, border_radius=8)
        for i, (kind, color) in enumerate(rows):
            cy = box.y + pad + row_h * i + row_h // 2
            x1 = box.x + pad
            pygame.draw.line(ui.screen, color, (x1, cy), (x1 + seg, cy), 3)
            label = ui.fonts["small"].render(kind, True, INK)
            ui.screen.blit(label, (x1 + seg + 10, cy - label.get_height() // 2))
        # 심사 중인 두 사람을 표시하는 초록 링 안내
        cy = box.y + pad + row_h * len(rows) + row_h // 2
        x1 = box.x + pad
        pygame.draw.circle(ui.screen, CARD, (x1 + seg // 2, cy), 9)
        pygame.draw.circle(ui.screen, ACCENT, (x1 + seg // 2, cy), 9, 3)
        label = ui.fonts["small"].render("matched pair", True, INK)
        ui.screen.blit(label, (x1 + seg + 10, cy - label.get_height() // 2))

    def _draw_hobby_tree(self, scene: "PlayScene", ui: UIContext, area: pygame.Rect) -> None:
        root = scene.engine.hobbies.root
        if root is None:
            return
        max_depth = max(node.depth for node in scene.engine.hobbies.nodes.values())
        y_step = area.height // (max_depth + 1) if max_depth else 0

        def draw_node(node, x_min: int, x_max: int, y: int) -> None:
            x = (x_min + x_max) // 2
            if node.children:
                width = max(1, (x_max - x_min) // len(node.children))
                for i, child in enumerate(node.children):
                    child_min = x_min + i * width
                    child_max = child_min + width
                    child_x = (child_min + child_max) // 2
                    child_y = y + y_step
                    pygame.draw.line(ui.screen, LINE, (x, y), (child_x, child_y), 3)
                    draw_node(child, child_min, child_max, child_y)
            node_rect = pygame.Rect(x - 48, y - 18, 96, 36)
            pygame.draw.rect(ui.screen, CARD, node_rect, border_radius=6)
            pygame.draw.rect(ui.screen, ACCENT, node_rect, 2, border_radius=6)
            label = ui.fonts["small"].render(node.name, True, INK)
            ui.screen.blit(label, label.get_rect(center=node_rect.center))
        draw_node(root, area.x, area.right, area.y + 28)

    def handle_click(self, scene: "PlayScene", pos: tuple[int, int]) -> bool:
        for button in scene.buttons:
            if button.contains(pos) and button.action == "close_asset":
                scene._play_sound("click")
                scene.close_top_layer()
                return True
        return True


class PlayScene:
    def __init__(self, engine: MatchmakingEngine) -> None:
        self.engine = engine
        self.profiles = self.engine.priority_profiles()
        # 남성/여성 풀을 나눠두고 각 풀에서 한 명씩 뽑아 항상 이성 페어만 만든다.
        self._males = [p for p in self.profiles if p.get("gender") == "male"]
        self._females = [p for p in self.profiles if p.get("gender") == "female"]
        # 모든 조합을 미리 만들지 않고(프로필 수가 커지면 폭증) 매 라운드 무작위 페어를 즉석에서 뽑는다.
        self.pair_index = 0
        self.current_pair = self._random_pair()
        # 관계 그래프에 표시할 15명은 페어가 바뀔 때만 다시 계산하도록 캐시한다.
        self._graph_members: list[str] = []
        self._graph_cache_index = -1
        self.game_state = "playing"
        self.message_queue = deque()
        self.buttons: list[Button] = []
        self.notice_text = ""
        self.notice_timer = 0.0
        self.dialogue_history: list[str] = []
        self.asset_dir = Path(__file__).resolve().parents[1] / "assets" / "data"
        self.avatar_dir = Path(__file__).resolve().parents[1] / "assets" / "img"
        # 초상화는 처음 그릴 때 한 번만 로드/스케일하고 파일명 기준으로 캐시한다.
        self._avatar_cache: dict[str, pygame.Surface | None] = {}
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.engine.ui_stack.clear()
        self.engine.ui_stack.push(DialoguePopup())

    def run(self) -> None:
        pygame.init()
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=1)
            self.sounds = {"click": self._make_tone(520, 0.045, 0.22), "success": self._make_tone(740, 0.08, 0.25), "error": self._make_tone(190, 0.12, 0.28)}
        except pygame.error:
            self.sounds = {}
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("DateStructure, Please")
        clock = pygame.time.Clock()
        fonts = {"title": pygame.font.SysFont(["malgungothic", "applegothic"], 34), "heading": pygame.font.SysFont(["malgungothic", "applegothic"], 24), "body": pygame.font.SysFont(["malgungothic", "applegothic"], 18), "small": pygame.font.SysFont(["malgungothic", "applegothic"], 15), "popup_title": pygame.font.SysFont(["malgungothic", "applegothic"], 20)}
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

    def _make_tone(self, frequency: int, duration: float, volume: float) -> pygame.mixer.Sound:
        sample_rate = 44100
        samples = array("h")
        for i in range(int(sample_rate * duration)):
            fade = 1 - i / max(1, int(sample_rate * duration))
            value = int(32767 * volume * fade * math.sin(2 * math.pi * frequency * i / sample_rate))
            samples.append(value)
        return pygame.mixer.Sound(buffer=samples.tobytes())

    def _play_sound(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def _random_pair(self) -> tuple[dict, dict]:
        # 남성 풀과 여성 풀에서 각각 한 명씩 뽑아 항상 이성 페어를 구성한다.
        pair = [random.choice(self._males), random.choice(self._females)]
        random.shuffle(pair)  # 카드 좌/우 성별이 항상 고정되지 않도록 순서를 섞는다.
        return pair[0], pair[1]

    def _current_pair(self) -> tuple[dict, dict]:
        return self.current_pair

    def _relationship_members(self) -> list[str]:
        """현재 페어 기준으로 관계 그래프에 표시할 15명. 페어가 바뀔 때만 재계산한다."""
        if self._graph_cache_index != self.pair_index:
            first, second = self._current_pair()
            self._graph_members = self.engine.select_graph_members(first["id"], second["id"])
            self._graph_cache_index = self.pair_index
        return self._graph_members

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
            if not button.contains(pos):
                continue
            self._play_sound("click")
            if button.action == "restart":
                self._restart_game()
            elif button.action == "reject":
                self._reject_pair()
            elif button.action == "next":
                self._approve_pair()
            elif button.action in {"tree", "graph_rel", "graph_city"}:
                self.engine.ui_stack.push(AssetPopup(button.action))
                self.notice_text = ""
            return

    def _handle_escape(self) -> bool:
        top_layer = self.engine.ui_stack.peek()
        if isinstance(top_layer, UILayer):
            return top_layer.on_escape(self)
        return False

    def _approve_pair(self) -> None:
        first, second = self._current_pair()
        result = self.engine.evaluate_match(first["id"], second["id"])
        if result.accepted:
            self._play_sound("success")
            # 적합한 매칭 승인 시 SUCCESS_MATCH만큼 명성 상승 (명성 바 최대치 100으로 클램프)
            self.engine.reputation = min(100, self.engine.reputation + self.engine.SUCCESS_MATCH)
            self.message_queue.append("승인 성공! 적합한 매칭입니다.")
        else:
            self._play_sound("error")
            self.engine.reputation = max(0, self.engine.reputation - 10)
            self.message_queue.append(f"오심! 부적합 매칭 승인. 사유: {' / '.join(result.reasons)}")
        self._advance()

    def _reject_pair(self) -> None:
        first, second = self._current_pair()
        result = self.engine.evaluate_match(first["id"], second["id"])
        if not result.accepted:
            self._play_sound("success")
            # 올바른 거절도 성공한 판단이므로 SUCCESS_REJECT만큼 명성 상승
            self.engine.reputation = min(100, self.engine.reputation + self.engine.SUCCESS_REJECT)
            self.message_queue.append(f"정확한 판단입니다! 사유: {result.reasons[0]}")
        else:
            self._play_sound("error")
            self.engine.reputation = max(0, self.engine.reputation - 10)
            self.message_queue.append("오심입니다! 적합한 매칭을 거절했습니다.")
        self._advance()

    def _advance(self) -> None:
        """다음 라운드로. 무작위 페어를 새로 뽑고 게임 상태를 갱신한다."""
        self.pair_index += 1
        self.current_pair = self._random_pair()
        self._update_game_state()

    def close_top_layer(self) -> None:
        if isinstance(self.engine.ui_stack.peek(), UILayer):
            self.engine.ui_stack.pop()

    def _update(self, dt: float) -> None:
        if self.notice_timer > 0:
            self.notice_timer = max(0, self.notice_timer - dt)
            if self.notice_timer == 0:
                self.notice_text = ""
        while self.message_queue:
            self.notice_text = self.message_queue.popleft()
            self.notice_timer = 3.0

    def _draw(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        analysis = self._analysis()
        screen.fill(BG)
        self._draw_background(screen)
        ui = UIContext(screen, fonts)
        ui.text("title", "DateStructure, Please", (40, 26), INK)
        ui.text("body", "Moderator review desk", (44, 68), MUTED)
        self._draw_reputation(ui)
        self._draw_profile_card(ui, analysis.first, pygame.Rect(42, 116, 366, 270))
        self._draw_profile_card(ui, analysis.second, pygame.Rect(552, 116, 366, 270))
        self._draw_decision_hint(ui, analysis)
        self._draw_asset_buttons(ui)
        self._draw_actions(ui)
        overlays = self.engine.ui_stack.items()
        if overlays:
            ui.scrim()
        for depth, layer in enumerate(overlays):
            layer.draw(self, ui, depth)
        self.buttons = ui.buttons
        if self.game_state != "playing":
            ui.buttons = []
            self._draw_end_screen(ui)
            self.buttons = ui.buttons

    def _draw_background(self, screen: pygame.Surface) -> None:
        pygame.draw.rect(screen, (247, 245, 240), pygame.Rect(0, 0, WIDTH, 92))
        pygame.draw.line(screen, LINE, (0, 92), (WIDTH, 92), 2)
        pygame.draw.circle(screen, (226, 239, 232), (470, 245), 92)
        pygame.draw.circle(screen, (237, 230, 214), (496, 255), 56)

    def _draw_reputation(self, ui: UIContext) -> None:
        box = pygame.Rect(724, 24, 194, 54)
        pygame.draw.rect(ui.screen, CARD, box, border_radius=8)
        pygame.draw.rect(ui.screen, LINE, box, 2, border_radius=8)
        fill_width = max(0, min(box.width, int(box.width * self.engine.reputation / 100)))
        if fill_width:
            pygame.draw.rect(ui.screen, ACCENT, pygame.Rect(box.x, box.y, fill_width, box.height), border_radius=8)
        ui.text("body", f"Reputation: {self.engine.reputation}", (box.x + 18, box.y + 16), (255, 255, 255) if fill_width > 130 else INK)

    def _avatar_surface(self, profile: dict) -> pygame.Surface | None:
        gender = profile.get("gender", "unknown")
        if gender not in ("male", "female"):
            gender = "male"
        # 기존 절차적 아바타와 같은 시드라 동일 프로필은 항상 같은 초상화를 받는다.
        seed = sum(ord(ch) for ch in profile["id"] + profile["name"])
        filename = f"{gender}_{seed % AVATAR_VARIANTS + 1}.png"
        if filename not in self._avatar_cache:
            try:
                image = pygame.image.load(self.avatar_dir / filename).convert()
                self._avatar_cache[filename] = pygame.transform.smoothscale(image, (AVATAR_SIZE, AVATAR_SIZE))
            except (pygame.error, FileNotFoundError):
                self._avatar_cache[filename] = None
        return self._avatar_cache[filename]

    def _draw_avatar(self, ui: UIContext, profile: dict, center: tuple[int, int]) -> None:
        half = AVATAR_SIZE // 2
        avatar_rect = pygame.Rect(center[0] - half, center[1] - half, AVATAR_SIZE, AVATAR_SIZE)
        pygame.draw.rect(ui.screen, (0, 0, 0, 24), avatar_rect.move(3, 5))
        portrait = self._avatar_surface(profile)
        if portrait is not None:
            ui.screen.blit(portrait, avatar_rect)
        else:
            pygame.draw.rect(ui.screen, PORTRAIT_BG, avatar_rect)
        pygame.draw.rect(ui.screen, INK, avatar_rect, 3)

    def _draw_profile_card(self, ui: UIContext, profile: dict, rect: pygame.Rect) -> None:
        pygame.draw.rect(ui.screen, (0, 0, 0, 26), pygame.Rect(rect.x + 4, rect.y + 5, rect.width, rect.height), border_radius=10)
        pygame.draw.rect(ui.screen, CARD, rect, border_radius=10)
        pygame.draw.rect(ui.screen, LINE, rect, 2, border_radius=10)
        self._draw_avatar(ui, profile, (rect.x + 84, rect.y + 92))
        gender = profile.get("gender", "unknown")
        badge_color = (217, 82, 108) if gender == "female" else BLUE
        badge = pygame.Rect(rect.x + 188, rect.y + 70, 104, 30)
        pygame.draw.rect(ui.screen, badge_color, badge, border_radius=15)
        ui.text("small", gender.upper(), (badge.x + 18, badge.y + 7), (255, 255, 255))
        ui.text("heading", profile["name"], (rect.x + 188, rect.y + 28), INK)
        ui.text("body", f"ID: {profile['id']}", (rect.x + 188, rect.y + 112), MUTED)
        ui.text("body", f"City: {profile['city']}", (rect.x + 28, rect.y + 184), INK)
        ui.text("body", f"Hobby: {profile['hobby']}", (rect.x + 28, rect.y + 218), INK)
        ui.text("small", f"Success {int(profile['success_rate'] * 100)}%", (rect.x + 188, rect.y + 148), MUTED)

    def _draw_decision_hint(self, ui: UIContext, analysis: MatchAnalysis) -> None:
        panel = pygame.Rect(278, 402, 404, 76)
        pygame.draw.rect(ui.screen, CARD, panel, border_radius=10)
        pygame.draw.rect(ui.screen, LINE, panel, 2, border_radius=10)
        if analysis.forbidden_path is not None:
            text = "Relationship conflict detected: press REJECT"
            color = WARN
        else:
            text = "Review profiles, then approve or reject"
            color = ACCENT
        ui.text("body", text, (panel.x + 22, panel.y + 17), color)
        ui.text("small", "Use gender, city, hobby, and relation graphs to decide.", (panel.x + 22, panel.y + 46), MUTED)
        # 디버그용: 시스템이 계산한 점수와 (관계로 조정된) 통과 기준선을 표시
        ui.text("body", f"score: {analysis.score}", (panel.right + 20, panel.y + 17), INK)
        ui.text("body", f"pass ≥ {analysis.pass_threshold}", (panel.right + 20, panel.y + 41), INK)

    def _draw_asset_buttons(self, ui: UIContext) -> None:
        panel = pygame.Rect(278, 492, 404, 74)
        pygame.draw.rect(ui.screen, CARD, panel, border_radius=10)
        pygame.draw.rect(ui.screen, LINE, panel, 2, border_radius=10)
        ui.button(pygame.Rect(panel.x + 18, panel.y + 16, 112, 42), "Hobby Tree", "tree", ACCENT)
        ui.button(pygame.Rect(panel.x + 146, panel.y + 16, 112, 42), "Relations", "graph_rel", BLUE)
        ui.button(pygame.Rect(panel.x + 274, panel.y + 16, 112, 42), "Cities", "graph_city", ACCENT)

    def _draw_actions(self, ui: UIContext) -> None:
        ui.button(pygame.Rect(42, 512, 174, 54), "REJECT", "reject", WARN)
        ui.button(pygame.Rect(744, 512, 174, 54), "MATCH", "next", ACCENT)
        if self.notice_text:
            pygame.draw.rect(ui.screen, SOFT_RED, pygame.Rect(42, 584, 876, 34), border_radius=8)
            ui.text("small", self.notice_text, (56, 592), WARN)

    def _update_game_state(self) -> None:
        # 무작위 페어가 끝없이 이어지므로 종료 조건은 명성 소진뿐이다.
        if self.engine.reputation <= 0:
            self.game_state = "game_over"
            self.engine.ui_stack.clear()

    def _draw_end_screen(self, ui: UIContext) -> None:
        ui.scrim()
        clear = self.game_state == "clear"
        title = "STAGE CLEAR" if clear else "GAME OVER"
        body = f"업무를 마쳤습니다. 남은 명성: {self.engine.reputation}" if clear else "명성이 바닥나 심사관 자격을 잃었습니다."
        color = ACCENT if clear else WARN
        panel = pygame.Rect(WIDTH // 2 - 210, HEIGHT // 2 - 120, 420, 240)
        ui.popup_frame(panel, title, color, 0)
        ui.text("heading", body, (panel.x + 42, panel.y + 92), INK)
        ui.button(pygame.Rect(panel.centerx - 72, panel.bottom - 76, 144, 42), "RESTART", "restart", BLUE)

    def go_back_dialogue(self) -> None:
        if self.dialogue_history:
            self.engine.dialogue.current_id = self.dialogue_history.pop()

    def _restart_game(self) -> None:
        self.game_state = "playing"
        self.pair_index = 0
        self.engine.reputation = 80
        self.current_pair = self._random_pair()
        self._graph_cache_index = -1  # 캐시 무효화(재시작 후 pair_index가 다시 0이 되므로)
        self.message_queue.clear()
        self.notice_text = ""
        self.notice_timer = 0.0
        self.dialogue_history.clear()
        self.engine.dialogue.reset_to_root()
        self.engine.ui_stack.clear()
        self.engine.ui_stack.push(DialoguePopup())


def run_game(engine: MatchmakingEngine) -> None:
    PlayScene(engine).run()
