from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count
from math import dist

Coord = tuple[int, int]


@dataclass(frozen=True)
class Node:
    position: Coord
    cost: int = 1


class Grid:
    def __init__(self, width: int, height: int, walkable: set[Coord], cell_size: int = 32) -> None:
        self.width = width
        self.height = height
        self.walkable = walkable
        self.cell_size = cell_size

    def in_bounds(self, cell: Coord) -> bool:
        x, y = cell
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, cell: Coord) -> bool:
        return cell in self.walkable

    def get_neighbors(self, cell: Coord) -> list[Coord]:
        x, y = cell
        neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
        return [neighbor for neighbor in neighbors if self.in_bounds(neighbor)]

    def world_to_cell(self, x: float, y: float) -> Coord:
        return int(x // self.cell_size), int(y // self.cell_size)


class GridBasedPathfinder(ABC):
    def __init__(self, grid: Grid) -> None:
        self.grid = grid

    @abstractmethod
    def find_path(self, start: Coord, destination: Coord) -> list[Coord]:
        raise NotImplementedError

    def construct_path(self, nodes_path: dict[Coord, Coord], destination: Coord) -> list[Coord]:
        sequence: list[Coord] = [destination]
        step = destination

        while step in nodes_path:
            step = nodes_path[step]
            sequence.append(step)

        sequence.reverse()
        return sequence


class BfsPathfinder(GridBasedPathfinder):
    def find_path(self, start: Coord, destination: Coord) -> list[Coord]:
        queue: deque[Coord] = deque([start])
        visited = {start}
        path_dict: dict[Coord, Coord] = {}

        while queue:
            current = queue.popleft()

            if current == destination:
                return self.construct_path(path_dict, destination)

            for neighbor in self.grid.get_neighbors(current):
                if neighbor in visited or not self.grid.is_walkable(neighbor):
                    continue

                queue.append(neighbor)
                visited.add(neighbor)
                path_dict[neighbor] = current

        return []


class DijkstraPathfinder(GridBasedPathfinder):
    def find_path(self, start: Coord, destination: Coord) -> list[Coord]:
        order = count()
        priority_queue: list[tuple[int, int, Coord]] = [(0, next(order), start)]
        distances: dict[Coord, int] = {start: 0}
        previous: dict[Coord, Coord] = {}

        while priority_queue:
            _, _, current = heappop(priority_queue)

            if current == destination:
                return self.construct_path(previous, destination)

            for neighbor in self.grid.get_neighbors(current):
                if not self.grid.is_walkable(neighbor):
                    continue

                new_cost = distances[current] + 1
                if neighbor not in distances or new_cost < distances[neighbor]:
                    distances[neighbor] = new_cost
                    previous[neighbor] = current
                    heappush(priority_queue, (new_cost, next(order), neighbor))

        return []


class AStarPathfinder(GridBasedPathfinder):
    def find_path(self, start: Coord, destination: Coord) -> list[Coord]:
        order = count()
        open_heap: list[tuple[float, int, Coord]] = []
        heappush(open_heap, (self.heuristic(start, destination), next(order), start))

        came_from: dict[Coord, Coord] = {}
        g_score: dict[Coord, float] = {start: 0.0}
        f_score: dict[Coord, float] = {start: self.heuristic(start, destination)}
        closed_set: set[Coord] = set()

        while open_heap:
            _, _, current = heappop(open_heap)

            if current in closed_set:
                continue

            if current == destination:
                return self.construct_path(came_from, destination)

            closed_set.add(current)

            for neighbor in self.grid.get_neighbors(current):
                if not self.grid.is_walkable(neighbor) or neighbor in closed_set:
                    continue

                tentative_g_score = g_score[current] + 1
                if tentative_g_score < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self.heuristic(neighbor, destination)
                    heappush(open_heap, (f_score[neighbor], next(order), neighbor))

        return []

    @staticmethod
    def heuristic(a: Coord, b: Coord) -> float:
        return dist(a, b)

