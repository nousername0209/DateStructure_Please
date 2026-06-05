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

    def draw(self, scene: "PlayScene", ui: UIContext, depth: int) -> None:
        title_map = {
            "tree": "트리",
            "graph_rel": "그래프 - 관계도",
            "graph_city": "그래프 - 도시",
        }
        image_map = {
            "tree": scene.tree_image,
            "graph_rel": scene.graph_rel_image,
            "graph_city": scene.graph_city_image,
        }
        title = title_map.get(self.kind, "Asset")
        rect = pygame.Rect(112 + depth * 28, 74 + depth * 22, WIDTH - 224, HEIGHT - 142)
        ui.popup_frame(rect, title, ACCENT, depth)

        image = image_map.get(self.kind)
        if image is None:
            ui.text("heading", "이미지를 불러올 수 없습니다.", (rect.x + 28, rect.y + 92), WARN)
            ui.button(pygame.Rect(rect.right - 132, rect.y + 14, 104, 34), "CLOSE", "close_asset", WARN)
            return

        image_rect = image.get_rect()
        max_width = rect.width - 64
        max_height = rect.height - 114
        if image_rect.width > max_width or image_rect.height > max_height:
            scale = min(max_width / image_rect.width, max_height / image_rect.height)
            image = pygame.transform.smoothscale(
                image,
                (round(image_rect.width * scale), round(image_rect.height * scale)),
            )
            image_rect = image.get_rect()

        content_rect = pygame.Rect(rect.x + 32, rect.y + 74, rect.width - 64, rect.height - 104)
        image_rect.center = content_rect.center
        ui.screen.blit(image, image_rect)
        ui.button(pygame.Rect(rect.right - 132, rect.y + 14, 104, 34), "CLOSE", "close_asset", WARN)
        ui.text("small", "ESC를 눌러 닫기", (rect.x + 28, rect.bottom - 32), MUTED)

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
        self.pair_index = 0
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
        first = self.profiles[self.pair_index % len(self.profiles)]
        second = self.profiles[(self.pair_index + 2) % len(self.profiles)]
        return first, second

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
                if button.action == "reject":
                    self._reject_pair()
                elif button.action == "next":
                    self.pair_index = (self.pair_index + 1) % len(self.profiles)
                    self.notice_text = ""
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
        # REJECT behavior to be implemented later.
        pass

    def close_top_layer(self) -> None:
        if isinstance(self.engine.ui_stack.peek(), UILayer):
            self.engine.ui_stack.pop()

    def _update(self, dt: float) -> None:
        if self.notice_timer > 0:
            self.notice_timer = max(0, self.notice_timer - dt)
            if self.notice_timer == 0:
                self.notice_text = ""

    def _draw(self, screen: pygame.Surface, fonts: dict[str, pygame.font.Font]) -> None:
        analysis = self._analysis()
        screen.fill(BG)
        ui = UIContext(screen, fonts)

        ui.text("title", "DateStructure, Please", (40, 30), INK)
        ui.text("body", "Moderator review desk", (44, 72), MUTED)
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
        ui.text("body", f"Tier: {profile['tier']}", (rect.x + 24, rect.y + 178), INK)
        ui.text("small", f"Suspicion: {profile['suspicion']}", (rect.x + 24, rect.y + 218), WARN)

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
        
        ui.button(pygame.Rect(start_x, button_y, button_width, button_height), "관계도\n(Tree)", "tree", ACCENT)
        ui.button(pygame.Rect(start_x + button_width + spacing, button_y, button_width, button_height), "관계\n그래프", "graph_rel", ACCENT)
        ui.button(pygame.Rect(start_x + (button_width + spacing) * 2, button_y, button_width, button_height), "도시\n그래프", "graph_city", ACCENT)
        
        if self.notice_text:
            ui.text("small", self.notice_text, (46, 588), WARN)

    def go_back_dialogue(self) -> None:
        if not self.dialogue_history:
            return
        previous_id = self.dialogue_history.pop()
        self.engine.dialogue.current_id = previous_id


def run_game(engine: MatchmakingEngine) -> None:
    PlayScene(engine).run()
