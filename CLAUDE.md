# CLAUDE.md

Guidance for working in this repository.

## Project

**DateStructure, Please** — a pygame ("DateStructure, Please" moderator desk) game prototype whose
real purpose is to showcase classic data structures driving game logic. The player reviews matched
pairs of dating profiles and judges them; each judgement is backed by a graph/tree/queue/stack
algorithm.

- Python **3.12+** (uses `X | None` unions, modern generics, dataclasses).
- Single runtime dependency: **pygame-ce** (declared in `pyproject.toml`; locked via `uv.lock`).

## Run & dev commands

Always run from the **repository root** — imports are absolute from the `src.` package
(e.g. `from src.engine import build_engine`), so a different CWD breaks imports.

```powershell
python main.py                       # launch the game (opens a 960x640 pygame window)
python -m py_compile src\engine.py src\scene_play.py   # quick syntax check after edits
uv sync                              # install/sync deps from uv.lock (if using uv)
```

There is **no test suite** and no linter/formatter config in the repo. Verify changes by
byte-compiling and by running the game.

## Architecture

`main.py` → `build_engine()` (loads JSON, wires structures) → `run_game(engine)` →
`PlayScene(engine).run()` (the pygame loop).

- **`src/engine.py`** — `MatchmakingEngine`, the persistent game state. Holds the loaded structures
  plus `ui_stack`, `event_queue`, and `reputation` (starts at 80). Profiles are **not** stored as a
  dict — `__init__` `merge_sort`s them into `profiles_by_id` (ID-ascending primary index) and
  `get_profile()` looks them up via `binary_search_by_id` (deliberate, to exercise the sort/search
  code). `priority_profiles()` re-sorts by `(tier_priority, success_rate)` descending. `analyze_pair()`
  computes a `MatchAnalysis` (score + forbidden-path + distances); `evaluate_match()` returns a
  `MatchResult` (accept/reject) and **is** called by the scene (`_approve_pair`/`_reject_pair`).
  Scoring: starts at 100; same-gender pairs (`is_same_gender_pair`) and forbidden relationships
  force score 0; otherwise hobby distance over `hobby_distance_limit` and travel distance over
  `long_distance_limit` subtract `PENALTY_HOBBY`/`PENALTY_TRAVEL`; a pair passes at `PASS_SCORE` (60).
  The forbidden check is **direct-only** (`is_related` + direct blacklist): only a direct relationship
  link between the two profiles — or one blacklisting the other — rejects the pair. There is **no
  multi-hop chaining** (A–B and B–C do *not* reject A–C); when forbidden, the recorded
  `forbidden_path` is simply `[first_id, second_id]`.
- **`src/scene_play.py`** — all UI/rendering. `PlayScene` runs the event/update/draw loop. UI is
  immediate-mode: each frame, drawing code calls `ui.button(...)` which both draws and registers the
  button into `ui.buttons`; after drawing, `self.buttons = ui.buttons`, and `_handle_click` routes by
  `button.action` string. Overlays use the **`UILayer` + `UIStack`** pattern: the top layer
  (`DialoguePopup`, `AssetPopup`, …) intercepts clicks and ESC before base-scene buttons; a
  `DialoguePopup` (the "Briefing" intro) is pushed on the stack at scene start. Profile **avatars**
  (`_draw_avatar`) and **sound effects** (`_make_tone`/`_play_sound`, click/success/error tones) are
  generated procedurally at runtime — no image or audio asset files are loaded.
- **`src/structures/`** — the data structures the project exists to demonstrate:
  - `relationship_graph.py` — undirected relationship graph; `is_related()` checks a **direct** link
    between two users (no path traversal). Each edge stores a `kind` (e.g. `best_friend`/`ex_partner`/
    `scam_partner`). (`has_path()` is a leftover BFS demo, not used by game logic.)
  - `hobby_tree.py` — general tree; LCA-based `distance()` for hobby compatibility.
  - `map_graph.py` — weighted undirected graph; Dijkstra `shortest_distance()` for travel penalties.
  - `ui_stack.py` — generic stack for UI overlays.
  - `event_queue.py` — generic FIFO queue for staged events.
- **`src/utils/`** — `data_loader.py` (JSON → structures, plus the pointer-based `DialogueTree`) and
  `sorter.py` (`merge_sort`, `binary_search_by_id` used for profile ordering/lookup).
- **`assets/data/`** — game content: `profiles.json`, `world_map.json`, `dialogue_tree.json`, and
  pre-rendered structure images (`tree.png`, `graph_rel.png`, `graph_city.png`). **Note:** the in-game
  `AssetPopup` panels draw the tree/relationship/city graphs *procedurally* from the live structures —
  the `.png` files are not loaded by the running game.

## Conventions & gotchas

- **Data loading is not 1:1 with filenames.** `load_game_data()` reads `relationships` out of
  `profiles.json` and `hobbies` out of `dialogue_tree.json` (the standalone `load_*` helpers in
  `data_loader.py` imply separate files, but the real wiring is in `load_game_data`). Check there
  before assuming where a piece of data comes from.
- **Profiles** are dicts (not dataclasses) with keys: `id`, `name`, `gender`, `city`, `hobby`, `tier`,
  `tier_priority`, `success_rate`, `suspicion`, `joined_at`, `blacklist`. `gender` (`"male"`/`"female"`)
  drives same-gender rejection and avatar/badge rendering.
- **UI text is mixed Korean/English**; keep that style when editing on-screen strings.
- **Layout is hard-coded pixel rects** against a fixed `WIDTH=960, HEIGHT=640` window. Color
  constants (`INK`, `MUTED`, `ACCENT`, `WARN`, `GRAY`, …) live at the top of `scene_play.py`; reuse
  them rather than inlining RGB tuples.
- Buttons are identified purely by their `action` string — add a new button by drawing it in a
  `_draw_*` method and adding a matching branch in `_handle_click`.
