# Maze Python

Simple Python rebuild of the Godot maze project.

What it keeps:
- The original maze layout from `maze-godot/src/tilemap/Level1.tmx`
- The original player, enemy, and gem placements from `maze-godot/src/game/Scenes/Game.tscn`
- The same three grid-based algorithms: BFS, Dijkstra, and A*

What changes:
- The UI is intentionally simple and uses `tkinter`
- Characters and gems are rendered as shapes instead of Godot sprites
- Movement is tile-based for a cleaner Python implementation

Run it with:

```powershell
python app.py
```

Controls:
- `WASD` or arrow keys: move
- `D`: toggle enemy path display
- `R`: reset
