"""贪吃蛇吃苹果 —— 纯 Python + tkinter 实现的经典小游戏（无需安装第三方库）。

操作：
    方向键 / WASD  控制移动
    空格          暂停 / 继续
    R             重新开始
    Esc           退出

运行：python snake_game.py
"""

import random
import tkinter as tk
from tkinter import font as tkfont

# ---------------- 游戏参数 ----------------
CELL = 26                      # 单格像素
COLS, ROWS = 22, 22            # 棋盘格数
BOARD_W, BOARD_H = COLS * CELL, ROWS * CELL
HUD_H = 56                     # 顶部信息栏高度
PAD = 14                       # 窗口内边距
WIN_W = BOARD_W + PAD * 2
WIN_H = BOARD_H + HUD_H + PAD * 2

BASE_DELAY = 150               # 初始每步毫秒数（越小越快）
MIN_DELAY = 65                 # 最快速度
SPEED_STEP = 4                 # 每吃一个苹果加速的毫秒数

# ---------------- 配色 ----------------
C_BG = "#0e1118"               # 窗口背景
C_BOARD = "#171b26"            # 棋盘底色
C_GRID = "#1e2331"             # 网格线
C_HUD = "#12151d"
C_TEXT = "#e8edf7"
C_SUB = "#7c879e"
C_APPLE = "#ff4d5f"
C_APPLE_HI = "#ff8a96"
C_LEAF = "#4fd67a"
C_HEAD = "#b6ffc4"
C_SNAKE_TOP = "#6ee78c"
C_SNAKE_BOT = "#249a52"
C_OVER = "#ff5c6c"


def lerp_color(c1, c2, t):
    """在两个 #rrggbb 颜色之间线性插值。"""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return "#%02x%02x%02x" % (
        round(r1 + (r2 - r1) * t),
        round(g1 + (g2 - g1) * t),
        round(b1 + (b2 - b1) * t),
    )


def pick_font(root, size, bold=False):
    """优先选择支持中文的字体，避免部分系统显示方块。"""
    families = set(tkfont.families(root))
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC",
                 "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
                 "SimHei", "Helvetica Neue", "Helvetica", "Arial"):
        if name in families:
            return (name, size, "bold" if bold else "normal")
    return ("TkDefaultFont", size, "bold" if bold else "normal")


class SnakeGame:
    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(
            root, width=WIN_W, height=WIN_H,
            bg=C_BG, highlightthickness=0,
        )
        self.canvas.pack()

        self.f_hud = pick_font(root, 14, bold=True)
        self.f_big = pick_font(root, 34, bold=True)
        self.f_mid = pick_font(root, 15, bold=True)
        self.f_small = pick_font(root, 12)

        # 静态棋盘
        self._draw_board()

        self.best = 0
        self.after_id = None
        self.bind_keys()
        self.reset()

    # ---------------- 初始化 ----------------
    def bind_keys(self):
        self.root.bind("<Key>", self.on_key)
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def reset(self):
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

        cx, cy = COLS // 2, ROWS // 2
        # 蛇身列表，头部在索引 0
        self.snake = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.dir = (1, 0)
        self.next_dir = (1, 0)
        self.score = 0
        self.delay = BASE_DELAY
        self.paused = False
        self.over = False
        self.win = False
        self.apple = None
        self.spawn_apple()
        self.draw()
        self.schedule()

    def spawn_apple(self):
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in self.snake]
        self.apple = random.choice(free) if free else None

    # ---------------- 输入 ----------------
    def on_key(self, event):
        key = event.keysym.lower()
        if key in ("r",):
            self.best = max(self.best, self.score)
            self.reset()
            return
        if key == "space":
            if self.over:
                self.reset()
            else:
                self.paused = not self.paused
                if self.paused:
                    if self.after_id is not None:
                        self.root.after_cancel(self.after_id)
                        self.after_id = None
                    self.draw()
                else:
                    self.draw()
                    self.schedule()
            return
        if self.over or self.paused:
            return

        mapping = {
            "up": (0, -1), "w": (0, -1),
            "down": (0, 1), "s": (0, 1),
            "left": (-1, 0), "a": (-1, 0),
            "right": (1, 0), "d": (1, 0),
        }
        new_dir = mapping.get(key)
        if new_dir is None:
            return
        # 禁止 180° 反向（相对当前实际方向）
        if (new_dir[0] + self.dir[0], new_dir[1] + self.dir[1]) != (0, 0):
            self.next_dir = new_dir

    # ---------------- 主循环 ----------------
    def schedule(self):
        self.after_id = self.root.after(self.delay, self.tick)

    def tick(self):
        self.after_id = None
        if self.paused or self.over:
            return
        self.step()
        self.draw()
        if not self.over:
            self.schedule()

    def step(self):
        self.dir = self.next_dir
        hx, hy = self.snake[0]
        nx, ny = hx + self.dir[0], hy + self.dir[1]

        # 撞墙
        if not (0 <= nx < COLS and 0 <= ny < ROWS):
            self.game_over()
            return
        # 撞自己（尾巴即将移开的格子不算）
        body = self.snake[:-1] if (nx, ny) != self.apple else self.snake
        if (nx, ny) in body:
            self.game_over()
            return

        self.snake.insert(0, (nx, ny))
        if (nx, ny) == self.apple:
            self.score += 1
            self.best = max(self.best, self.score)
            self.delay = max(MIN_DELAY, BASE_DELAY - self.score * SPEED_STEP)
            self.spawn_apple()
            if self.apple is None:      # 填满棋盘，通关
                self.game_over(win=True)
        else:
            self.snake.pop()

    def game_over(self, win=False):
        self.over = True
        self.win = win
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        self.draw()

    # ---------------- 绘制 ----------------
    def _draw_board(self):
        c = self.canvas
        c.create_rectangle(0, 0, WIN_W, WIN_H, fill=C_BG, outline="")
        x0, y0 = PAD, HUD_H + PAD
        c.create_rectangle(x0 - 2, y0 - 2, x0 + BOARD_W + 2, y0 + BOARD_H + 2,
                           fill="#0a0d13", outline="")
        c.create_rectangle(x0, y0, x0 + BOARD_W, y0 + BOARD_H,
                           fill=C_BOARD, outline="")
        for i in range(1, COLS):
            c.create_line(x0 + i * CELL, y0, x0 + i * CELL, y0 + BOARD_H,
                          fill=C_GRID)
        for j in range(1, ROWS):
            c.create_line(x0, y0 + j * CELL, x0 + BOARD_W, y0 + j * CELL,
                          fill=C_GRID)
        c.create_rectangle(PAD, PAD, WIN_W - PAD, HUD_H + PAD - 6,
                           fill=C_HUD, outline="", tags="hud_bg")
        # HUD 纹理：左侧小蛇图标
        c.create_oval(PAD + 14, PAD + 15, PAD + 32, PAD + 33,
                      fill=C_SNAKE_TOP, outline="", tags="hud_icon")
        c.create_text(PAD + 40, PAD + 24, text="贪吃蛇", anchor="w",
                      fill=C_TEXT, font=self.f_hud, tags="hud_icon")

    def cell_rect(self, x, y, inset=0):
        px = PAD + x * CELL + inset
        py = HUD_H + PAD + y * CELL + inset
        return px, py, px + CELL - inset * 2, py + CELL - inset * 2

    def cell_center(self, x, y):
        px, py, px2, py2 = self.cell_rect(x, y)
        return (px + px2) / 2, (py + py2) / 2

    def draw_apple(self):
        if not self.apple:
            return
        x, y = self.apple
        px, py, px2, py2 = self.cell_rect(x, y)
        cx, cy = (px + px2) / 2, (py + py2) / 2 + 1
        r = CELL * 0.32
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=C_APPLE, outline="", tags="dyn")
        self.canvas.create_oval(cx - r * 0.55, cy - r * 0.75,
                                cx - r * 0.05, cy - r * 0.2,
                                fill=C_APPLE_HI, outline="", tags="dyn")
        self.canvas.create_line(cx, cy - r, cx + 1, cy - r - 4,
                                fill="#7a5230", width=2, tags="dyn")
        self.canvas.create_oval(cx + 1, cy - r - 7, cx + 8, cy - r + 1,
                                fill=C_LEAF, outline="", tags="dyn")

    def draw_snake(self):
        n = len(self.snake)
        pts = [self.cell_center(x, y) for x, y in self.snake]
        width = CELL * 0.74

        # 蛇身：用带圆头的粗线段连接各格中心，形成连贯身体 + 渐变色
        for i in range(n - 1):
            t = i / max(1, n - 2)
            color = lerp_color(C_SNAKE_TOP, C_SNAKE_BOT, min(1.0, t))
            self.canvas.create_line(
                pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                fill=color, width=width, capstyle="round",
                joinstyle="round", tags="dyn",
            )

        # 头部
        cx, cy = pts[0]
        r = CELL * 0.43
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                fill=C_HEAD, outline="", tags="dyn")

        # 眼睛：按前进方向偏移，且左右分开
        dx, dy = self.dir
        perp = (-dy, dx) if (dx, dy) != (0, 0) else (0, 1)
        ox, oy = dx * CELL * 0.14, dy * CELL * 0.14
        for s in (1, -1):
            ex = cx + ox + perp[0] * CELL * 0.18 * s
            ey = cy + oy + perp[1] * CELL * 0.18 * s
            self.canvas.create_oval(ex - 2.8, ey - 2.8, ex + 2.8, ey + 2.8,
                                    fill="#0f2318", outline="", tags="dyn")

    def draw_hud(self):
        c = self.canvas
        c.delete("hud_text")
        r = WIN_W - PAD
        pairs = [
            ("分数", self.score, r - 176, r - 130, C_TEXT),
            ("最高", self.best, r - 86, r - 40, C_SUB),
        ]
        for label, value, lx, vx, color in pairs:
            c.create_text(lx, PAD + 25, text=label, anchor="w",
                          fill=C_SUB, font=self.f_small, tags="hud_text")
            c.create_text(vx, PAD + 24, text=str(value), anchor="w",
                          fill=color, font=self.f_hud, tags="hud_text")

    def draw_overlay(self):
        c = self.canvas
        c.delete("overlay")
        x0, y0 = PAD, HUD_H + PAD
        c.create_rectangle(x0, y0, x0 + BOARD_W, y0 + BOARD_H,
                           fill="#05070b", stipple="gray50",
                           outline="", tags="overlay")

        cx, cy = WIN_W / 2, HUD_H + PAD + BOARD_H / 2
        if self.over:
            title = "完美通关！" if self.win else "游戏结束"
            title_color = C_SNAKE_TOP if self.win else C_OVER
            lines = [
                (cy - 44, title, title_color, self.f_big),
                (cy + 6, "本局得分  %d" % self.score, C_TEXT, self.f_mid),
                (cy + 46, "空格 / R  再来一局", C_SUB, self.f_small),
            ]
            card_w, card_h = 340, 200
        elif self.paused:
            lines = [
                (cy - 14, "已暂停", C_TEXT, self.f_big),
                (cy + 32, "按空格继续", C_SUB, self.f_small),
            ]
            card_w, card_h = 300, 150
        else:
            return

        c.create_round_rect(cx - card_w / 2, cy - card_h / 2,
                            cx + card_w / 2, cy + card_h / 2,
                            radius=18, fill="#11151f", outline="#2b3346",
                            width=2, tags="overlay")
        for y, text, color, fnt in lines:
            c.create_text(cx, y, text=text, fill=color, font=fnt,
                          tags="overlay")

    def draw(self):
        self.canvas.delete("dyn")
        self.draw_apple()
        self.draw_snake()
        self.draw_hud()
        if self.paused or self.over:
            self.draw_overlay()
        else:
            self.canvas.delete("overlay")


def create_round_rect(self, x1, y1, x2, y2, radius=8, **kw):
    """在 Canvas 上画一个圆角矩形（用平滑多边形近似）。"""
    r = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return self.create_polygon(pts, smooth=True, **kw)


tk.Canvas.create_round_rect = create_round_rect


def main():
    root = tk.Tk()
    root.title("贪吃蛇 · Snake")
    root.resizable(False, False)
    root.configure(bg=C_BG)
    SnakeGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
