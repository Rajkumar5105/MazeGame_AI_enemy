from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from embedded_level import ENEMIES, GEMS, PLAYER_WORLD, WALKABLE_ROWS
from pathfinding import Coord, Grid

ALGORITHM_BY_ID = {
    0: "A*",
    1: "Dijkstra",
    2: "BFS",
}

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TILEMAP_PATH = WORKSPACE_ROOT / "maze-godot" / "src" / "tilemap" / "Level1.tmx"
DEFAULT_SCENE_PATH = WORKSPACE_ROOT / "maze-godot" / "src" / "game" / "Scenes" / "Game.tscn"


@dataclass(frozen=True)
class GemData:
    kind: str
    value: int
    cell: Coord


@dataclass(frozen=True)
class EnemyData:
    name: str
    enemy_type: str
    algorithm: str
    cell: Coord


@dataclass(frozen=True)
class LevelData:
    grid: Grid
    player_spawn: Coord
    enemies: list[EnemyData]
    gems: list[GemData]


def load_level(
    tilemap_path: Path = DEFAULT_TILEMAP_PATH,
    scene_path: Path = DEFAULT_SCENE_PATH,
) -> LevelData:
    if tilemap_path.exists() and scene_path.exists():
        grid = _load_grid(tilemap_path)
        player_spawn, enemies, gems = _load_scene_entities(scene_path, grid)
        return LevelData(grid=grid, player_spawn=player_spawn, enemies=enemies, gems=gems)

    return _load_embedded_level()


def _load_grid(tilemap_path: Path) -> Grid:
    root = ET.parse(tilemap_path).getroot()
    width = int(root.attrib["width"])
    height = int(root.attrib["height"])
    cell_size = int(root.attrib["tilewidth"])

    walkable_layer = next(layer for layer in root.findall("layer") if layer.attrib.get("name") == "Walkable")
    raw_data = walkable_layer.findtext("data", default="")
    values = [int(value.strip()) for value in raw_data.replace("\n", "").split(",") if value.strip()]

    walkable: set[Coord] = set()
    for index, value in enumerate(values):
        if value == 0:
            continue
        x = index % width
        y = index // width
        walkable.add((x, y))

    return Grid(width=width, height=height, walkable=walkable, cell_size=cell_size)


def _load_scene_entities(scene_path: Path, grid: Grid) -> tuple[Coord, list[EnemyData], list[GemData]]:
    lines = scene_path.read_text(encoding="utf-8").splitlines()
    node_pattern = re.compile(r'^\[node name="([^"]+)"')
    vector_pattern = re.compile(r"Vector2\(([^,]+), ([^)]+)\)")

    player_spawn: Coord | None = None
    enemies: list[EnemyData] = []
    gems: list[GemData] = []
    current: dict[str, object] | None = None

    def finalize(node: dict[str, object] | None) -> None:
        nonlocal player_spawn
        if not node or "position" not in node:
            return

        cell = _snap_to_walkable(grid, grid.world_to_cell(*node["position"]))
        name = str(node["name"])

        if name == "Player":
            player_spawn = cell
            return

        if name.startswith("Enemy"):
            enemy_type = "Yellow" if int(node.get("type", 0)) == 1 else "Red"
            algorithm = ALGORITHM_BY_ID.get(int(node.get("algorithm", 0)), "A*")
            enemies.append(
                EnemyData(
                    name=name,
                    enemy_type=enemy_type,
                    algorithm=algorithm,
                    cell=cell,
                )
            )
            return

        if name.startswith("GoldGem") or name.startswith("DiamondGem"):
            kind = "Gold" if name.startswith("GoldGem") else "Diamond"
            value = 10 if kind == "Gold" else 20
            gems.append(GemData(kind=kind, value=value, cell=cell))

    for raw_line in lines:
        line = raw_line.strip()
        node_match = node_pattern.match(line)
        if node_match:
            finalize(current)
            current = {"name": node_match.group(1)}
            continue

        if current is None:
            continue

        if line.startswith("position = "):
            match = vector_pattern.search(line)
            if match:
                current["position"] = (float(match.group(1)), float(match.group(2)))
        elif line.startswith("Type = "):
            current["type"] = int(line.split("=", 1)[1].strip())
        elif line.startswith("PathfindingAlgorithm = "):
            current["algorithm"] = int(line.split("=", 1)[1].strip())

    finalize(current)

    if player_spawn is None:
        raise ValueError(f"Could not find a player spawn in scene: {scene_path}")

    return player_spawn, enemies, gems


def _snap_to_walkable(grid: Grid, start: Coord) -> Coord:
    if grid.is_walkable(start):
        return start

    queue: deque[Coord] = deque([start])
    visited = {start}

    while queue:
        cell = queue.popleft()
        for neighbor in grid.get_neighbors(cell):
            if neighbor in visited:
                continue
            if grid.is_walkable(neighbor):
                return neighbor
            visited.add(neighbor)
            queue.append(neighbor)

    raise ValueError(f"Unable to find a walkable cell near spawn {start}")


def _load_embedded_level() -> LevelData:
    width = len(WALKABLE_ROWS[0])
    height = len(WALKABLE_ROWS)
    walkable = {
        (x, y)
        for y, row in enumerate(WALKABLE_ROWS)
        for x, value in enumerate(row)
        if value != 0
    }
    grid = Grid(width=width, height=height, walkable=walkable, cell_size=32)

    player_spawn = _snap_to_walkable(grid, grid.world_to_cell(*PLAYER_WORLD))
    enemies = [
        EnemyData(
            name=enemy["name"],
            enemy_type=enemy["enemy_type"],
            algorithm=enemy["algorithm"],
            cell=_snap_to_walkable(grid, grid.world_to_cell(*enemy["world"])),
        )
        for enemy in ENEMIES
    ]
    gems = [
        GemData(
            kind=gem["kind"],
            value=gem["value"],
            cell=_snap_to_walkable(grid, grid.world_to_cell(*gem["world"])),
        )
        for gem in GEMS
    ]

    return LevelData(grid=grid, player_spawn=player_spawn, enemies=enemies, gems=gems)
