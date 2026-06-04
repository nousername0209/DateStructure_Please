from dataclasses import dataclass
import math
from pathlib import Path

import pygame

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


@dataclass(frozen=True)
class Button:
    rect: pygame.Rect
    label: str
    action: str


class PlayScene:
    """Pygame play loop for pair review and contradiction inspection."""

    def __init__(self, engine: MatchmakingEngine) -> None:
        self.engine = engine
        self.profiles = self.engine.priority_profiles()
        self.pair_index = 0
        self.buttons: list[Button] = []
        self.notice_text = ""
        self.notice_timer = 0.0
        self.warning_timer = 0.0
        self.active_view: str | None = None
        self.dialogue_active = True
        self.dialogue_history: list[str] = []
        self.tree_image: pygame.Surface | None = None
        self.graph_image: pygame.Surface | None = None
        self.asset_dir = Path(__file__).resolve().parents[1] / "assets" / "data"
        self.engine.ui_stack.clear()
        self.engine.ui_stack.push("PLAY")

    def run(self) -> None:
        pygame.init()
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("DateStructure, Please")
        clock = pygame.time.Clock()
        self.tree_image = pygame.image.load(str(self.asset_dir / "tree.png")).convert_alpha()
        self.graph_image = pygame.image.load(str(self.asset_dir / "graph.png")).convert_alpha()
        fonts = {
            "title": pygame.font.SysFont("malgungothic", 34),
            "heading": pygame.font.SysFont("malgungothic", 24),
            "body": pygame.font.SysFont("malgungothic", 18),
            "small": pygame.font.SysFont("malgungothic", 15),
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
        first = self.profiles[self.pair_index % len(self.profiles)]
        second = self.profiles[(self.pair_index + 2) % len(self.profiles)]
        return first, second

    def _analysis(self) -> MatchAnalysis:
        first, second = self._current_pair()
        return self.engine.analyze_pair(first["id"], second["id"])

    def _handle_click(self, pos: tuple[int, int]) -> None:
        if self.dialogue_active:
            for button in self.buttons:
                if button.rect.collidepoint(pos):
                    if button.action.startswith("dialogue_choice"):
                        self.dialogue_history.append(self.engine.dialogue.current_id)
                        choice_index = int(button.action.split("_")[-1])
                        self.engine.dialogue.choose(choice_index)
                        return
                    if button.action == "dialogue_back":
                        self._go_back_dialogue()
                        return
            return

        current = self.engine.ui_stack.peek()
        for button in self.buttons:
            if button.rect.collidepoint(pos):
                if current == "WARNING" and button.action != "close_warning":
                    return
                if current == "INSPECT" and button.action != "close_inspect":
                    return
                if button.action == "inspect":
                    self._inspect_pair()
                elif button.action == "next":
                    self.pair_index = (self.pair_index + 1) % len(self.profiles)
                    self.notice_text = ""
                elif button.action == "tree":
                    self.active_view = "tree"
                    self.notice_text = ""
                elif button.action == "graph":
                    self.active_view = "graph"
                    self.notice_text = ""
                elif button.action == "close_warning":
                    self._close_overlay("WARNING")
                elif button.action == "close_inspect":
                    self._close_overlay("INSPECT")
                return

    def _handle_escape(self) -> bool:
        # ESC during dialogue should close the dialogue (not go back).
        if self.dialogue_active:
            self.dialogue_active = False
            return True

        if self.active_view is not None:
            self.active_view = None
            return True

        current = self.engine.ui_stack.peek()
        if current in {"WARNING", "INSPECT"}:
            self._close_overlay(current)
            return True
        return False

    def _inspect_pair(self) -> None:
        analysis = self._analysis()
        self.engine.ui_stack.push("INSPECT")
        if analysis.forbidden_path is None:
            self.notice_text = "INSPECT: 금지 관계 경로가 발견되지 않았습니다."
            self.notice_timer = 2.5
            return

        self.notice_text = f"INSPECT 성공: {' -> '.join(analysis.forbidden_path)}"
        self.notice_timer = 3.5
        self.engine.event_queue.enqueue("warning_print")

    def _close_overlay(self, overlay_name: str) -> None:
        if self.engine.ui_stack.peek() == overlay_name:
            self.engine.ui_stack.pop()
        elif self.engine.ui_stack.peek() == "INSPECT" and overlay_name == "WARNING":
            self.engine.ui_stack.pop()

    def _update(self, dt: float) -> None:
        if self.notice_timer > 0:
            self.notice_timer = max(0, self.notice_timer - dt)
            if self.notice_timer == 0:
                self.notice_text = ""

        if self.warning_timer > 0:
            self.warning_timer = max(0, self.warning_timer - dt)
            if self.warning_timer == 0 and self.engine.ui_stack.peek() == "WARNING":
                self.engine.ui_stack.pop()

        if self.warning_timer == 0 and not self.engine.event_queue.is_empty():
            event_name = self.engine.event_queue.dequeue()
            if event_name == "warning_print":
                self.warning_timer = 2.8
                self.engine.ui_stack.push("WARNING")

    def _draw(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        if self.dialogue_active:
            self._draw_dialogue(screen, fonts)
            return

        analysis = self._analysis()
        if self.active_view is not None:
            self._draw_asset_view(screen, fonts)
            return

        screen.fill(BG)
        self.buttons = []

        self._text(screen, fonts["title"], "DateStructure, Please", (40, 30), INK)
        self._text(screen, fonts["body"], "Moderator review desk", (44, 72), MUTED)
        self._draw_profile_card(screen, fonts, analysis.first, pygame.Rect(46, 128, 350, 250))
        self._draw_profile_card(screen, fonts, analysis.second, pygame.Rect(564, 128, 350, 250))
        self._draw_analysis_panel(screen, fonts, analysis)
        self._draw_actions(screen, fonts)

        current = self.engine.ui_stack.peek()
        if current == "INSPECT":
            self._draw_inspect_overlay(screen, fonts, analysis)
        elif current == "WARNING":
            self._draw_warning_overlay(screen, fonts, analysis)

    def _draw_asset_view(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        screen.fill(BG)
        image = self.tree_image if self.active_view == "tree" else self.graph_image
        if image is None:
            self._text(screen, fonts["heading"], "이미지를 불러올 수 없습니다.", (40, 40), WARN)
            return

        image_rect = image.get_rect()
        max_width = WIDTH - 80
        max_height = HEIGHT - 120
        if image_rect.width > max_width or image_rect.height > max_height:
            scale = min(max_width / image_rect.width, max_height / image_rect.height)
            image = pygame.transform.smoothscale(
                image,
                (round(image_rect.width * scale), round(image_rect.height * scale)),
            )
            image_rect = image.get_rect()

        image_rect.center = (WIDTH // 2, HEIGHT // 2)
        screen.blit(image, image_rect)
        title = "트리" if self.active_view == "tree" else "그래프"
        self._text(screen, fonts["heading"], title, (40, 30), INK)
        self._text(screen, fonts["small"], "ESC를 눌러 돌아가기", (40, HEIGHT - 40), MUTED)

    def _draw_dialogue(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        screen.fill(BG)
        self.buttons = []
        dialogue = self.engine.dialogue.current

        panel = pygame.Rect(60, 80, WIDTH - 120, 320)
        pygame.draw.rect(screen, CARD, panel, border_radius=12)
        pygame.draw.rect(screen, LINE, panel, 2, border_radius=12)
        self._text(screen, fonts["title"], "Dialogue", (panel.x + 24, panel.y + 20), INK)

        text_lines = self._wrap_text(fonts["body"], dialogue.text, panel.width - 48)
        line_y = panel.y + 80
        for line in text_lines:
            self._text(screen, fonts["body"], line, (panel.x + 24, line_y), INK)
            line_y += fonts["body"].get_height() + 6

        if self.dialogue_history:
            back_button = Button(pygame.Rect(panel.right - 116, panel.y + 16, 96, 40), "뒤로", "dialogue_back")
            self._draw_button(screen, fonts, back_button, WARN)

        if dialogue.choices:
            choice_y = line_y + 16
            for index, choice in enumerate(dialogue.choices):
                button_rect = pygame.Rect(panel.x + 24, choice_y, panel.width - 48, 48)
                choice_button = Button(button_rect, choice["label"], f"dialogue_choice_{index}")
                self._draw_button(screen, fonts, choice_button, ACCENT)
                choice_y += 60
        else:
            info_text = "선택지가 없습니다. ESC를 눌러 대화를 종료하거나 뒤로 가기 버튼을 누르세요." if self.dialogue_history else "선택지가 없습니다. ESC를 눌러 대화를 종료하세요."
            self._text(
                screen,
                fonts["small"],
                info_text,
                (panel.x + 24, panel.bottom - 40),
                MUTED,
            )

    def _draw_profile_card(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        profile: dict,
        rect: pygame.Rect,
    ) -> None:
        pygame.draw.rect(screen, CARD, rect, border_radius=8)
        pygame.draw.rect(screen, LINE, rect, 2, border_radius=8)
        self._text(screen, fonts["heading"], profile["name"], (rect.x + 24, rect.y + 24), INK)
        self._text(screen, fonts["body"], f"ID: {profile['id']}", (rect.x + 24, rect.y + 70), MUTED)
        self._text(screen, fonts["body"], f"City: {profile['city']}", (rect.x + 24, rect.y + 106), INK)
        self._text(screen, fonts["body"], f"Hobby: {profile['hobby']}", (rect.x + 24, rect.y + 142), INK)
        self._text(screen, fonts["body"], f"Tier: {profile['tier']}", (rect.x + 24, rect.y + 178), INK)
        self._text(screen, fonts["small"], f"Suspicion: {profile['suspicion']}", (rect.x + 24, rect.y + 218), WARN)

    def _draw_analysis_panel(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        analysis: MatchAnalysis,
    ) -> None:
        panel = pygame.Rect(278, 410, 404, 150)
        pygame.draw.rect(screen, (250, 249, 244), panel, border_radius=8)
        pygame.draw.rect(screen, LINE, panel, 2, border_radius=8)
        self._text(screen, fonts["heading"], "Matching Analysis", (panel.x + 24, panel.y + 18), INK)
        self._text(screen, fonts["body"], f"매칭 적합도 점수: {analysis.score}", (panel.x + 24, panel.y + 62), ACCENT)
        distance_text = "unreachable" if math.isinf(analysis.travel_distance) else f"{analysis.travel_distance:.1f}"
        self._text(screen, fonts["body"], f"예상 이동 거리: {distance_text}", (panel.x + 24, panel.y + 94), BLUE)
        self._text(screen, fonts["small"], f"HobbyTree distance: {analysis.hobby_distance}", (panel.x + 24, panel.y + 124), MUTED)

    def _draw_actions(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        tree_button = Button(pygame.Rect(WIDTH - 236, 30, 100, 42), "트리", "tree")
        graph_button = Button(pygame.Rect(WIDTH - 122, 30, 100, 42), "그래프", "graph")
        inspect = Button(pygame.Rect(46, 514, 170, 52), "INSPECT", "inspect")
        next_pair = Button(pygame.Rect(744, 514, 170, 52), "NEXT PAIR", "next")
        self._draw_button(screen, fonts, tree_button, ACCENT)
        self._draw_button(screen, fonts, graph_button, ACCENT)
        self._draw_button(screen, fonts, inspect, WARN)
        self._draw_button(screen, fonts, next_pair, ACCENT)
        if self.notice_text:
            self._text(screen, fonts["small"], self.notice_text, (46, 588), WARN)

    def _draw_inspect_overlay(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        analysis: MatchAnalysis,
    ) -> None:
        self._scrim(screen)
        rect = pygame.Rect(250, 168, 460, 260)
        pygame.draw.rect(screen, CARD, rect, border_radius=8)
        pygame.draw.rect(screen, WARN, rect, 2, border_radius=8)
        self._text(screen, fonts["heading"], "INSPECT MODE", (rect.x + 28, rect.y + 26), WARN)
        if analysis.forbidden_path is None:
            body = "No forbidden relationship path detected."
        else:
            body = f"Forbidden path: {' -> '.join(analysis.forbidden_path)}"
        self._text(screen, fonts["body"], body, (rect.x + 28, rect.y + 86), INK)
        self._text(screen, fonts["small"], "RelationshipGraph BFS result", (rect.x + 28, rect.y + 124), MUTED)
        close = Button(pygame.Rect(rect.x + 280, rect.y + 184, 132, 44), "CLOSE", "close_inspect")
        self._draw_button(screen, fonts, close, WARN)

    def _draw_warning_overlay(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        analysis: MatchAnalysis,
    ) -> None:
        self._scrim(screen)
        rect = pygame.Rect(286, 190, 388, 220)
        pygame.draw.rect(screen, (255, 249, 235), rect, border_radius=8)
        pygame.draw.rect(screen, WARN, rect, 3, border_radius=8)
        self._text(screen, fonts["heading"], "WARNING NOTICE", (rect.x + 34, rect.y + 30), WARN)
        self._text(screen, fonts["body"], "Contradiction detected.", (rect.x + 34, rect.y + 86), INK)
        path = analysis.forbidden_path or []
        self._text(screen, fonts["small"], " -> ".join(path), (rect.x + 34, rect.y + 120), MUTED)
        close = Button(pygame.Rect(rect.x + 222, rect.y + 150, 116, 42), "OK", "close_warning")
        self._draw_button(screen, fonts, close, WARN)

    def _draw_button(
        self,
        screen: pygame.Surface,
        fonts: dict[str, pygame.font.Font],
        button: Button,
        color: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(screen, color, button.rect, border_radius=8)
        label = fonts["body"].render(button.label, True, (255, 255, 255))
        screen.blit(label, label.get_rect(center=button.rect.center))
        self.buttons.append(button)

    def _scrim(self, screen: pygame.Surface) -> None:
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((20, 20, 20, 120))
        screen.blit(overlay, (0, 0))

    def _text(
        self,
        screen: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        pos: tuple[int, int],
        color: tuple[int, int, int],
    ) -> None:
        screen.blit(font.render(text, True, color), pos)

    def _go_back_dialogue(self) -> None:
        if not self.dialogue_history:
            return
        previous_id = self.dialogue_history.pop()
        self.engine.dialogue.current_id = previous_id

    def _wrap_text(self, font: pygame.font.Font, text: str, max_width: int) -> list[str]:
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


def run_game(engine: MatchmakingEngine) -> None:
    PlayScene(engine).run()
