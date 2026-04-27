from __future__ import annotations

import tkinter as tk

from maze_game import build_app


def main() -> None:
    root = tk.Tk()
    build_app(root)
    root.mainloop()


if __name__ == "__main__":
    main()

