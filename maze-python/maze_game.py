from __future__ import annotations

from dataclasses import dataclass, field
import tkinter as tk

from level_loader import load_level
from pathfinding import AStarPathfinder, BfsPathfinder, DijkstraPathfinder, Grid, GridBasedPathfinder

CELL_RENDER_SIZE = 24
SIDEBAR_WIDTH = 320
TICK_MS = 250
ALGORITHMS = ("A*", "Dijkstra", "BFS")
PLAYER_COLOR = "#2563eb"
ENEMY_COLORS = ("#ef4444", "#f59e0b", "#a855f7")


@dataclass
class GemState:
    kind: str
    value: int
    cell: tuple[int, int]
    collected: bool = False


@dataclass
class EnemyState:
    name: str
    enemy_type: str
    cell: tuple[int, int]
    algorithm_var: tk.StringVar
    color: str
    pathfinder: GridBasedPathfinder | None = None
    path: list[tuple[int, int]] = field(default_factory=list)


class MazeGameUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Maze Game")
        self.root.configure(bg="#10151c")

        self.level = load_level()
        self.grid: Grid = self.level.grid

        self.canvas_width = self.grid.width * CELL_RENDER_SIZE
        self.canvas_height = self.grid.height * CELL_RENDER_SIZE

        self.root.geometry(f"{self.canvas_width + SIDEBAR_WIDTH}x{max(self.canvas_height, 760)}")
        self.root.minsize(self.canvas_width + SIDEBAR_WIDTH, 760)

        self.debug_enabled = tk.BooleanVar(value=False)
        self.score_var = tk.StringVar()
        self.gems_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.enemy_eta_vars: list[tk.StringVar] = []

        self.player_cell = self.level.player_spawn
        self.gems: list[GemState] = []
        self.enemies: list[EnemyState] = []
        self.enemy_option_vars: list[tk.StringVar] = []
        self.game_over = False

        self.canvas = tk.Canvas(
            self.root,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#111827",
            highlightthickness=0,
            bd=0,
        )
        self.sidebar = tk.Frame(self.root, bg="#1b2430", width=SIDEBAR_WIDTH, padx=18, pady=18)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.sidebar.pack_propagate(False)

        self._build_sidebar()
        self._bind_keys()
        self.reset_game()
        self._schedule_tick()

    def _build_sidebar(self) -> None:
        title = tk.Label(
            self.sidebar,
            text="Maze Game",
            bg="#1b2430",
            fg="white",
            font=("Segoe UI", 22, "bold"),
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            self.sidebar,
            text="Move, collect gems, and avoid enemies.",
            bg="#1b2430",
            fg="#b8c2cf",
            justify="left",
            font=("Segoe UI", 11),
        )
        subtitle.pack(anchor="w", pady=(6, 18))

        score = tk.Label(
            self.sidebar,
            textvariable=self.score_var,
            bg="#1b2430",
            fg="#7dd3fc",
            anchor="w",
            font=("Segoe UI", 13, "bold"),
        )
        score.pack(fill=tk.X)

        gems = tk.Label(
            self.sidebar,
            textvariable=self.gems_var,
            bg="#1b2430",
            fg="#dbe4ee",
            anchor="w",
            font=("Segoe UI", 12),
        )
        gems.pack(fill=tk.X, pady=(6, 4))

        status = tk.Label(
            self.sidebar,
            textvariable=self.status_var,
            bg="#1b2430",
            fg="#dbe4ee",
            anchor="w",
            justify="left",
            wraplength=260,
            font=("Segoe UI", 11),
        )
        status.pack(fill=tk.X, pady=(6, 16))

        show_paths = tk.Checkbutton(
            self.sidebar,
            text="Show enemy paths",
            variable=self.debug_enabled,
            command=self.draw,
            bg="#1b2430",
            fg="white",
            activebackground="#1b2430",
            activeforeground="white",
            selectcolor="#1b2430",
            font=("Segoe UI", 11),
        )
        show_paths.pack(anchor="w", pady=(0, 14))

        reset_button = tk.Button(
            self.sidebar,
            text="Reset",
            command=self.reset_game,
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=8,
            font=("Segoe UI", 11, "bold"),
        )
        reset_button.pack(anchor="w", pady=(0, 20))

        section = tk.Label(
            self.sidebar,
            text="Enemy Algorithms",
            bg="#1b2430",
            fg="white",
            anchor="w",
            font=("Segoe UI", 13, "bold"),
        )
        section.pack(fill=tk.X, pady=(0, 10))

        self.enemy_option_vars = []
        self.enemy_eta_vars = []
        for index, enemy_data in enumerate(self.level.enemies):
            frame = tk.Frame(self.sidebar, bg="#1b2430")
            frame.pack(fill=tk.X, pady=6)

            header = tk.Frame(frame, bg="#1b2430")
            header.pack(fill=tk.X)

            swatch = tk.Canvas(header, width=12, height=12, bg="#1b2430", highlightthickness=0, bd=0)
            swatch.create_oval(1, 1, 11, 11, fill=ENEMY_COLORS[index % len(ENEMY_COLORS)], outline="")
            swatch.pack(side=tk.LEFT, padx=(0, 8))

            label = tk.Label(
                header,
                text=enemy_data.name,
                bg="#1b2430",
                fg="#dbe4ee",
                anchor="w",
                font=("Segoe UI", 11, "bold"),
            )
            label.pack(side=tk.LEFT)

            eta_var = tk.StringVar(value="ETA: --")
            self.enemy_eta_vars.append(eta_var)
            eta_label = tk.Label(
                header,
                textvariable=eta_var,
                bg="#1b2430",
                fg=ENEMY_COLORS[index % len(ENEMY_COLORS)],
                anchor="e",
                font=("Segoe UI", 10, "bold"),
            )
            eta_label.pack(side=tk.RIGHT)

            variable = tk.StringVar(value=enemy_data.algorithm)
            self.enemy_option_vars.append(variable)
            menu = tk.OptionMenu(frame, variable, *ALGORITHMS, command=lambda _value, idx=index: self._change_enemy_algorithm(idx))
            menu.config(
                bg="#273447",
                fg="white",
                activebackground="#334155",
                activeforeground="white",
                highlightthickness=0,
                relief="flat",
                width=14,
                anchor="w",
                font=("Segoe UI", 10),
            )
            menu["menu"].config(bg="#273447", fg="white", activebackground="#334155", activeforeground="white")
            menu.pack(anchor="w", pady=(4, 0))

        controls_title = tk.Label(
            self.sidebar,
            text="Controls",
            bg="#1b2430",
            fg="white",
            anchor="w",
            font=("Segoe UI", 13, "bold"),
        )
        controls_title.pack(fill=tk.X, pady=(22, 8))

        controls_text = tk.Label(
            self.sidebar,
            text="Player is blue\nW A S D or Arrow Keys: Move\nP or Shift+D: Toggle paths\nR: Reset",
            bg="#1b2430",
            fg="#dbe4ee",
            justify="left",
            anchor="w",
            font=("Segoe UI", 11),
        )
        controls_text.pack(fill=tk.X)

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda _event: self.move_player(0, -1))
        self.root.bind("<Down>", lambda _event: self.move_player(0, 1))
        self.root.bind("<Left>", lambda _event: self.move_player(-1, 0))
        self.root.bind("<Right>", lambda _event: self.move_player(1, 0))
        self.root.bind("<w>", lambda _event: self.move_player(0, -1))
        self.root.bind("<s>", lambda _event: self.move_player(0, 1))
        self.root.bind("<a>", lambda _event: self.move_player(-1, 0))
        self.root.bind("<d>", lambda _event: self.move_player(1, 0))
        self.root.bind("<p>", lambda _event: self.toggle_debug())
        self.root.bind("<P>", lambda _event: self.toggle_debug())
        self.root.bind("<D>", lambda _event: self.toggle_debug())
        self.root.bind("<r>", lambda _event: self.reset_game())

    def reset_game(self) -> None:
        self.player_cell = self.level.player_spawn
        self.gems = [GemState(kind=gem.kind, value=gem.value, cell=gem.cell) for gem in self.level.gems]
        self.enemies = []

        for index, enemy_data in enumerate(self.level.enemies):
            variable = self.enemy_option_vars[index]
            enemy = EnemyState(
                name=enemy_data.name,
                enemy_type=enemy_data.enemy_type,
                cell=enemy_data.cell,
                algorithm_var=variable,
                color=ENEMY_COLORS[index % len(ENEMY_COLORS)],
            )
            enemy.pathfinder = self._build_pathfinder(variable.get())
            self.enemies.append(enemy)

        self.game_over = False
        self._collect_gem_if_needed()
        self._refresh_enemy_paths()
        self._update_status("Collect all gems and avoid the enemies.")
        self.draw()

    def _build_pathfinder(self, algorithm_name: str) -> GridBasedPathfinder:
        if algorithm_name == "Dijkstra":
            return DijkstraPathfinder(self.grid)
        if algorithm_name == "BFS":
            return BfsPathfinder(self.grid)
        return AStarPathfinder(self.grid)

    def toggle_debug(self) -> None:
        self.debug_enabled.set(not self.debug_enabled.get())
        self.draw()

    def move_player(self, dx: int, dy: int) -> None:
        if self.game_over:
            return

        next_cell = (self.player_cell[0] + dx, self.player_cell[1] + dy)
        if not self.grid.is_walkable(next_cell):
            return

        self.player_cell = next_cell
        self._collect_gem_if_needed()
        self._refresh_enemy_paths()
        self._check_game_state()
        self.draw()

    def _schedule_tick(self) -> None:
        self.root.after(TICK_MS, self._tick)

    def _tick(self) -> None:
        if not self.game_over:
            self._move_enemies()
            self._check_game_state()
            self.draw()
        self._schedule_tick()

    def _move_enemies(self) -> None:
        for enemy in self.enemies:
            enemy.pathfinder = self._build_pathfinder(enemy.algorithm_var.get())
            enemy.path = enemy.pathfinder.find_path(enemy.cell, self.player_cell)
            if len(enemy.path) > 1:
                enemy.cell = enemy.path[1]
        self._refresh_enemy_paths()

    def _refresh_enemy_paths(self) -> None:
        for index, enemy in enumerate(self.enemies):
            enemy.pathfinder = self._build_pathfinder(enemy.algorithm_var.get())
            enemy.path = enemy.pathfinder.find_path(enemy.cell, self.player_cell)
            self.enemy_eta_vars[index].set(self._format_enemy_eta(enemy.path))

    def _change_enemy_algorithm(self, index: int) -> None:
        if index >= len(self.enemies):
            return
        self.enemies[index].algorithm_var.set(self.enemy_option_vars[index].get())
        self.enemies[index].pathfinder = self._build_pathfinder(self.enemies[index].algorithm_var.get())
        self._refresh_enemy_paths()
        self.draw()

    def _format_enemy_eta(self, path: list[tuple[int, int]]) -> str:
        if not path:
            return "ETA: --"
        steps = max(len(path) - 1, 0)
        seconds = steps * (TICK_MS / 1000)
        return f"ETA: {seconds:.1f}s"

    def _collect_gem_if_needed(self) -> None:
        for gem in self.gems:
            if not gem.collected and gem.cell == self.player_cell:
                gem.collected = True

    def _check_game_state(self) -> None:
        for enemy in self.enemies:
            if enemy.cell == self.player_cell:
                self.game_over = True
                self._update_status(f"You were caught by {enemy.name}. Press R to restart.")
                return

        if all(gem.collected for gem in self.gems):
            self.game_over = True
            self._update_status(f"You win. Score: {self.score}. Press R to play again.")
            return

        self._update_status("Collect all gems and avoid the enemies.")

    @property
    def score(self) -> int:
        return sum(gem.value for gem in self.gems if gem.collected)

    def _update_status(self, message: str) -> None:
        collected = sum(1 for gem in self.gems if gem.collected)
        self.score_var.set(f"Score: {self.score}")
        self.gems_var.set(f"Gems: {collected} / {len(self.gems)}")
        self.status_var.set(message)

    def draw(self) -> None:
        self.canvas.delete("all")
        self._draw_grid()
        if self.debug_enabled.get():
            self._draw_paths()
        self._draw_gems()
        self._draw_player()
        self._draw_enemies()

    def _draw_grid(self) -> None:
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                walkable = self.grid.is_walkable((x, y))
                color = "#d1fae5" if walkable else "#1f2937"
                outline = "#94a3b8" if walkable else "#111827"
                x1 = x * CELL_RENDER_SIZE
                y1 = y * CELL_RENDER_SIZE
                x2 = x1 + CELL_RENDER_SIZE
                y2 = y1 + CELL_RENDER_SIZE
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline=outline)

    def _draw_paths(self) -> None:
        for enemy in self.enemies:
            if len(enemy.path) < 2:
                continue
            points: list[float] = []
            for cell in enemy.path:
                x, y = self._cell_center(cell)
                points.extend((x, y))
            self.canvas.create_line(points, fill=enemy.color, width=3)

    def _draw_gems(self) -> None:
        for gem in self.gems:
            if gem.collected:
                continue
            cx, cy = self._cell_center(gem.cell)
            radius = CELL_RENDER_SIZE * 0.28
            color = "#f59e0b" if gem.kind == "Gold" else "#06b6d4"
            self.canvas.create_polygon(
                cx,
                cy - radius,
                cx + radius,
                cy,
                cx,
                cy + radius,
                cx - radius,
                cy,
                fill=color,
                outline="#0f172a",
                width=2,
            )

    def _draw_player(self) -> None:
        cx, cy = self._cell_center(self.player_cell)
        radius = CELL_RENDER_SIZE * 0.35
        self.canvas.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=35,
            extent=290,
            fill="#facc15",
            outline="#0f172a",
            width=2,
            style=tk.PIESLICE,
        )
        eye = CELL_RENDER_SIZE * 0.06
        self.canvas.create_oval(
            cx - eye,
            cy - radius * 0.38 - eye,
            cx + eye,
            cy - radius * 0.38 + eye,
            fill="#0f172a",
            outline="",
        )

    def _draw_enemies(self) -> None:
        for enemy in self.enemies:
            cx, cy = self._cell_center(enemy.cell)
            body = CELL_RENDER_SIZE * 0.34
            horn = CELL_RENDER_SIZE * 0.18
            foot = CELL_RENDER_SIZE * 0.12

            self.canvas.create_polygon(
                cx - body,
                cy - body * 0.55,
                cx - body * 0.35,
                cy - body - horn,
                cx - body * 0.05,
                cy - body * 0.4,
                cx + body * 0.05,
                cy - body * 0.4,
                cx + body * 0.35,
                cy - body - horn,
                cx + body,
                cy - body * 0.55,
                cx + body,
                cy + body * 0.7,
                cx - body,
                cy + body * 0.7,
                fill=enemy.color,
                outline="#0f172a",
                width=2,
            )

            self.canvas.create_rectangle(
                cx - body * 0.8,
                cy + body * 0.7,
                cx - body * 0.45,
                cy + body * 0.7 + foot * 2,
                fill=enemy.color,
                outline="#0f172a",
                width=1,
            )
            self.canvas.create_rectangle(
                cx - body * 0.15,
                cy + body * 0.7,
                cx + body * 0.15,
                cy + body * 0.7 + foot * 2,
                fill=enemy.color,
                outline="#0f172a",
                width=1,
            )
            self.canvas.create_rectangle(
                cx + body * 0.45,
                cy + body * 0.7,
                cx + body * 0.8,
                cy + body * 0.7 + foot * 2,
                fill=enemy.color,
                outline="#0f172a",
                width=1,
            )

            eye = CELL_RENDER_SIZE * 0.07
            self.canvas.create_oval(
                cx - body * 0.4 - eye,
                cy - body * 0.2 - eye,
                cx - body * 0.4 + eye,
                cy - body * 0.2 + eye,
                fill="white",
                outline="",
            )
            self.canvas.create_oval(
                cx + body * 0.4 - eye,
                cy - body * 0.2 - eye,
                cx + body * 0.4 + eye,
                cy - body * 0.2 + eye,
                fill="white",
                outline="",
            )

    def _cell_center(self, cell: tuple[int, int]) -> tuple[float, float]:
        x, y = cell
        return (
            x * CELL_RENDER_SIZE + CELL_RENDER_SIZE / 2,
            y * CELL_RENDER_SIZE + CELL_RENDER_SIZE / 2,
        )


def build_app(root: tk.Tk) -> MazeGameUI:
    return MazeGameUI(root)
