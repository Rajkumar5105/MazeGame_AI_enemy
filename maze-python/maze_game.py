from __future__ import annotations

from dataclasses import dataclass, field
import tkinter as tk
from tkinter import ttk

from level_loader import EnemyData, GemData, load_level
from pathfinding import AStarPathfinder, BfsPathfinder, DijkstraPathfinder, Grid, GridBasedPathfinder

CELL_RENDER_SIZE = 24
SIDEBAR_WIDTH = 280
TICK_MS = 250
ALGORITHMS = ("A*", "Dijkstra", "BFS")
PATH_COLORS = ("#cf4446", "#8b5cf6", "#0284c7")


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
        self.root.title("Maze Python")
        self.level = load_level()
        self.grid: Grid = self.level.grid

        canvas_width = self.grid.width * CELL_RENDER_SIZE
        canvas_height = self.grid.height * CELL_RENDER_SIZE
        self.root.geometry(f"{canvas_width + SIDEBAR_WIDTH}x{canvas_height}")
        self.root.minsize(canvas_width + SIDEBAR_WIDTH, canvas_height)

        self.debug_enabled = tk.BooleanVar(value=False)
        self.score_var = tk.StringVar()
        self.gems_var = tk.StringVar()
        self.status_var = tk.StringVar()

        self.canvas = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg="#111827",
            highlightthickness=0,
        )
        self.sidebar = ttk.Frame(self.root, padding=16)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)

        self.player_cell = self.level.player_spawn
        self.gems: list[GemState] = []
        self.enemies: list[EnemyState] = []
        self.game_over = False

        self._build_sidebar()
        self._bind_keys()
        self.reset_game()
        self._schedule_tick()

    def _build_sidebar(self) -> None:
        ttk.Label(self.sidebar, text="Maze Python", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(self.sidebar, text="Simple UI, original maze, same core algorithms.").pack(anchor="w", pady=(4, 16))

        ttk.Label(self.sidebar, textvariable=self.score_var, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(self.sidebar, textvariable=self.gems_var).pack(anchor="w", pady=(4, 8))
        ttk.Label(self.sidebar, textvariable=self.status_var, wraplength=240, justify="left").pack(anchor="w", pady=(0, 12))

        ttk.Checkbutton(
            self.sidebar,
            text="Show enemy paths",
            variable=self.debug_enabled,
            command=self.draw,
        ).pack(anchor="w", pady=(0, 12))

        ttk.Button(self.sidebar, text="Reset", command=self.reset_game).pack(anchor="w", pady=(0, 16))

        ttk.Label(self.sidebar, text="Enemy Algorithms", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))

        for index, enemy_data in enumerate(self.level.enemies):
            frame = ttk.Frame(self.sidebar)
            frame.pack(fill=tk.X, pady=4)
            ttk.Label(frame, text=enemy_data.name).pack(anchor="w")
            algorithm_var = tk.StringVar(value=enemy_data.algorithm)
            option = ttk.OptionMenu(
                frame,
                algorithm_var,
                enemy_data.algorithm,
                *ALGORITHMS,
                command=lambda _value, idx=index: self._change_enemy_algorithm(idx),
            )
            option.pack(anchor="w", fill=tk.X)

        ttk.Label(
            self.sidebar,
            text="Controls\nWASD / Arrow Keys: move\nD: toggle paths\nR: reset",
            justify="left",
        ).pack(anchor="w", pady=(16, 0))

    def _bind_keys(self) -> None:
        self.root.bind("<Up>", lambda _event: self.move_player(0, -1))
        self.root.bind("<Down>", lambda _event: self.move_player(0, 1))
        self.root.bind("<Left>", lambda _event: self.move_player(-1, 0))
        self.root.bind("<Right>", lambda _event: self.move_player(1, 0))
        self.root.bind("<w>", lambda _event: self.move_player(0, -1))
        self.root.bind("<s>", lambda _event: self.move_player(0, 1))
        self.root.bind("<a>", lambda _event: self.move_player(-1, 0))
        self.root.bind("<d>", self._toggle_debug_key)
        self.root.bind("<r>", lambda _event: self.reset_game())

    def reset_game(self) -> None:
        self.player_cell = self.level.player_spawn
        self.gems = [GemState(kind=gem.kind, value=gem.value, cell=gem.cell) for gem in self.level.gems]
        self.enemies = []

        option_menus = [child for child in self.sidebar.winfo_children() if isinstance(child, ttk.Frame)]
        for index, enemy_data in enumerate(self.level.enemies):
            algorithm_var = next(
                widget["textvariable"]
                for widget in option_menus[index].winfo_children()
                if isinstance(widget, ttk.OptionMenu)
            )
            variable = self.root.getvar(algorithm_var)
            tk_var = tk.StringVar(value=variable)
            self.root.setvar(algorithm_var, variable)
            enemy = EnemyState(
                name=enemy_data.name,
                enemy_type=enemy_data.enemy_type,
                cell=enemy_data.cell,
                algorithm_var=tk_var,
                color=PATH_COLORS[index % len(PATH_COLORS)],
            )
            enemy.pathfinder = self._build_pathfinder(enemy.algorithm_var.get())
            self.enemies.append(enemy)

        self.game_over = False
        self._collect_gem_if_needed()
        self._update_status("Collect every gem and avoid all three enemies.")
        self.draw()

    def _build_pathfinder(self, algorithm_name: str) -> GridBasedPathfinder:
        if algorithm_name == "Dijkstra":
            return DijkstraPathfinder(self.grid)
        if algorithm_name == "BFS":
            return BfsPathfinder(self.grid)
        return AStarPathfinder(self.grid)

    def _change_enemy_algorithm(self, index: int) -> None:
        frame = [child for child in self.sidebar.winfo_children() if isinstance(child, ttk.Frame)][index]
        option = next(widget for widget in frame.winfo_children() if isinstance(widget, ttk.OptionMenu))
        variable_name = option["textvariable"]
        value = self.root.getvar(variable_name)
        self.enemies[index].algorithm_var.set(value)
        self.enemies[index].pathfinder = self._build_pathfinder(value)
        self.draw()

    def _toggle_debug_key(self, _event: tk.Event[tk.Misc]) -> None:
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
            enemy.pathfinder = enemy.pathfinder or self._build_pathfinder(enemy.algorithm_var.get())
            enemy.path = enemy.pathfinder.find_path(enemy.cell, self.player_cell)
            if len(enemy.path) > 1:
                enemy.cell = enemy.path[1]

    def _collect_gem_if_needed(self) -> None:
        for gem in self.gems:
            if not gem.collected and gem.cell == self.player_cell:
                gem.collected = True

    def _check_game_state(self) -> None:
        score = self.score

        for enemy in self.enemies:
            if enemy.cell == self.player_cell:
                self.game_over = True
                self._update_status(f"You were caught by {enemy.name}. Press R to try again.")
                return

        if all(gem.collected for gem in self.gems):
            self.game_over = True
            self._update_status(f"You win with {score} points. Press R to play again.")
            return

        self._update_status("Collect every gem and avoid all three enemies.")

    @property
    def score(self) -> int:
        return sum(gem.value for gem in self.gems if gem.collected)

    def _update_status(self, message: str) -> None:
        remaining = sum(1 for gem in self.gems if not gem.collected)
        self.score_var.set(f"Score: {self.score}")
        self.gems_var.set(f"Remaining gems: {remaining}")
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
                outline = "#c7d2fe" if walkable else "#111827"
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
            self.canvas.create_line(points, fill=enemy.color, width=3, smooth=False)

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
        self.canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            fill="#2563eb",
            outline="#0f172a",
            width=2,
        )

    def _draw_enemies(self) -> None:
        for enemy in self.enemies:
            cx, cy = self._cell_center(enemy.cell)
            radius = CELL_RENDER_SIZE * 0.35
            fill = "#ef4444" if enemy.enemy_type == "Red" else "#eab308"
            self.canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=fill,
                outline="#0f172a",
                width=2,
            )
            self.canvas.create_text(
                cx,
                cy,
                text=enemy.algorithm_var.get()[0],
                fill="#111827",
                font=("Segoe UI", 9, "bold"),
            )

    def _cell_center(self, cell: tuple[int, int]) -> tuple[float, float]:
        x, y = cell
        return (
            x * CELL_RENDER_SIZE + CELL_RENDER_SIZE / 2,
            y * CELL_RENDER_SIZE + CELL_RENDER_SIZE / 2,
        )


def build_app(root: tk.Tk) -> MazeGameUI:
    return MazeGameUI(root)

