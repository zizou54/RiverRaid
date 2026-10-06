"""
RIVER RAID - a tribute to the 1982 Activision classic.

Fly up an endless river, shoot ships, helicopters, jets and bridges,
and keep your fuel up by flying over FUEL depots.

Levels (chosen on the title screen with UP/DOWN or 1-4)
    BEGINNER, MEDIUM, HARD, PRINCIPAL - each with its own high score

Controls
    LEFT / RIGHT   steer
    UP             speed up
    DOWN           slow down
    SPACE          fire
    P              pause
    ESC            quit

Requires: pygame  (pip install pygame)
"""
import json
import math
import os
import random
import sys
from array import array

import pygame

# ---------------------------------------------------------------- constants
W, H = 800, 600
HUD_H = 90
PLAY_H = H - HUD_H
FPS = 60

ROW = 10                      # terrain is built from horizontal strips of this height
SEC_ROWS = 300                # rows per river section (one bridge per section)
SEC_LEN = ROW * SEC_ROWS
CENTER = W // 2
CHANNEL_W = 130               # river width at the bridges
BRIDGE_ROW = 15
TRANS = 10                    # rows used to morph from one river shape to the next
PLAYER_OFF = 90               # player distance from the bottom of the play area
PLAYER_SY = PLAY_H - PLAYER_OFF
SEED = 1982                   # fixed seed: the river is the same every game, like the original

SPEED_SLOW, SPEED_NORMAL, SPEED_FAST = 1.8, 3.5, 6.0
EXTRA_LIFE_EVERY = 10000

POINTS = {"ship": 30, "heli": 60, "fuel": 80, "jet": 100, "bridge": 500}

# Difficulty levels, easiest to hardest.
#   offset      - sections of difficulty added up front (narrower river, more islands)
#   enemy_speed - multiplier for ship/heli/jet speed
#   spacing     - extra rows between enemies (negative = denser)
#   drain/refill- fuel use per frame / refuel per frame over a depot
#   jets_from   - first section where jets appear
LEVELS = [
    {"name": "BEGINNER", "desc": "Wide river, slow enemies, 5 lives",
     "offset": 0, "enemy_speed": 0.65, "spacing": 10, "drain": 0.045, "refill": 0.8, "lives": 5, "jets_from": 3,
     "color": (90, 220, 90)},
    {"name": "MEDIUM", "desc": "The classic experience, 3 lives",
     "offset": 0, "enemy_speed": 1.0, "spacing": 0, "drain": 0.065, "refill": 0.55, "lives": 3, "jets_from": 1,
     "color": (232, 232, 74)},
    {"name": "HARD", "desc": "Narrow river, fast enemies, thirsty engine",
     "offset": 4, "enemy_speed": 1.3, "spacing": -3, "drain": 0.08, "refill": 0.5, "lives": 3, "jets_from": 0,
     "color": (255, 150, 40)},
    {"name": "PRINCIPAL", "desc": "Only for the brave - 2 lives, no mercy",
     "offset": 8, "enemy_speed": 1.6, "spacing": -6, "drain": 0.095, "refill": 0.45, "lives": 2, "jets_from": 0,
     "color": (240, 60, 60)},
]
_level = LEVELS[1]

GRASS = (52, 148, 52)
SHORE = (36, 110, 36)
WATER = (45, 75, 205)
ROAD = (70, 70, 70)
HUD_BG = (142, 142, 142)
YELLOW = (232, 232, 74)
WHITE = (245, 245, 245)
BLACK = (0, 0, 0)
RED = (210, 40, 40)

HIGHSCORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "riverraid_highscore.txt")


# ---------------------------------------------------------------- terrain
_sections = {}


def set_level(level):
    """Switch difficulty; the river is regenerated for the new level."""
    global _level
    _level = level
    _sections.clear()


def _shape_edges(shape):
    c, w, iw = shape
    return c - w / 2, c + w / 2, c - iw / 2, c + iw / 2


def _transition_ok(a, b):
    """Keep consecutive river shapes close enough that a skilled pilot can follow."""
    al, ar, ail, air = _shape_edges(a)
    bl, br, bil, bir = _shape_edges(b)
    if abs(a[0] - b[0]) > 100 or abs(al - bl) > 220 or abs(ar - br) > 220:
        return False
    if a[2] and b[2] and (abs(ail - bil) > 200 or abs(air - bir) > 200):
        return False
    return True


def section_data(sec):
    """Rows (left, right, island_left, island_right) and decorations for a section.
    Deterministic per section, so restarting at a checkpoint replays the same river."""
    if sec in _sections:
        return _sections[sec]
    rng = random.Random(SEED * 7919 + sec)
    channel = (CENTER, CHANNEL_W, 0)
    start = (CENTER, 380, 0) if sec == 0 else channel

    diff = min(sec + _level["offset"], 10)
    max_w = 560 - diff * 24
    min_w = max(110, 210 - diff * 9)
    island_p = 0.30 + diff * 0.03

    keys = [(0, start)]
    prev = start
    r = 50
    while r < 170:
        cand = None
        for _ in range(40):
            w = rng.randint(min_w, max_w)
            c = rng.randint(int(prev[0] - 100), int(prev[0] + 100))
            c = max(40 + w // 2, min(W - 40 - w // 2, c))
            iw = 0
            if w >= 300 and rng.random() < island_p:
                iw = rng.randint(int(w * 0.2), w - 170)
            if _transition_ok(prev, (c, w, iw)):
                cand = (c, w, iw)
                break
        if cand is None:
            cand = (prev[0], prev[1], 0)
        keys.append((r, cand))
        prev = cand
        r += rng.choice((18, 24, 30, 36))
    # steer back towards the narrow channel that holds the next bridge
    while not _transition_ok(prev, channel):
        c = prev[0] + max(-100, min(100, CENTER - prev[0]))
        prev = (c, max(CHANNEL_W, prev[1] - 200), 0)
        keys.append((r, prev))
        r += 18
    keys.append((min(r, SEC_ROWS - TRANS - 2), channel))

    rows = []
    ki = 0
    for row in range(SEC_ROWS):
        while ki + 1 < len(keys) and keys[ki + 1][0] <= row:
            ki += 1
        k_row, shape = keys[ki]
        if ki > 0:
            t = min(1.0, (row - k_row) / TRANS)
            p = keys[ki - 1][1]
            shape = tuple(p[j] + (shape[j] - p[j]) * t for j in range(3))
        l, rr, il, ir = _shape_edges(shape)
        if shape[2] < 4:
            rows.append((int(l), int(rr), None, None))
        else:
            rows.append((int(l), int(rr), int(il), int(ir)))

    decos = []
    base = sec * SEC_LEN
    for row in range(0, SEC_ROWS, 3):
        if sec > 0 and BRIDGE_ROW - 3 <= row <= BRIDGE_ROW + 3:
            continue
        if rng.random() > 0.45:
            continue
        l, rr, il, ir = rows[row]
        spots = []
        if l - 22 > 12:
            spots.append((12, l - 22))
        if W - 12 > rr + 22:
            spots.append((rr + 22, W - 12))
        if il is not None and ir - il > 40:
            spots.append((il + 16, ir - 16))
        if spots:
            a, b = rng.choice(spots)
            kind = "house" if rng.random() < 0.18 else "tree"
            decos.append((base + row * ROW + 5, rng.uniform(a, b), kind))

    _sections[sec] = (rows, decos)
    return _sections[sec]


def terrain_row(r):
    if r < 0:
        r = 0
    return section_data(r // SEC_ROWS)[0][r % SEC_ROWS]


def terrain_at(wy):
    return terrain_row(int(wy // ROW))


def on_land(x, wy):
    l, r, il, ir = terrain_at(wy)
    return x < l or x > r or (il is not None and il < x < ir)


def to_screen(wy, cam):
    return PLAY_H - (wy - cam)


# ---------------------------------------------------------------- sound
class Sounds:
    def __init__(self):
        self.ok = False
        try:
            init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, _, self.channels = init
            self.shoot = self._make(lambda t, p: _square(1400 - 1100 * p, t), 0.14, 0.18)
            noise = random.Random(7)
            self.boom = self._make(lambda t, p: noise.uniform(-1, 1) * (1 - p) ** 2, 0.55, 0.45)
            self.big_boom = self._make(lambda t, p: noise.uniform(-1, 1) * (1 - p) ** 1.5, 1.1, 0.55)
            self.fuel = self._make(lambda t, p: math.sin(2 * math.pi * 990 * t) * (1 - p), 0.06, 0.25)
            self.alarm = self._make(lambda t, p: _square(440, t), 0.12, 0.15)
            self.life = self._make(lambda t, p: _square(523 if p < 0.33 else 659 if p < 0.66 else 784, t), 0.36, 0.2)
            self.ok = True
        except pygame.error:
            self.ok = False

    def _make(self, gen, dur, vol):
        n = int(self.rate * dur)
        buf = array("h")
        for i in range(n):
            v = int(max(-1.0, min(1.0, gen(i / self.rate, i / n))) * vol * 32767)
            buf.extend([v] * self.channels)
        return pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.ok:
            getattr(self, name).play()


def _square(freq, t):
    return 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0


# ---------------------------------------------------------------- entities
class Entity:
    SIZES = {"ship": (64, 18), "heli": (36, 22), "jet": (42, 14), "fuel": (30, 56)}

    def __init__(self, kind, x, wy, vx=0.0, mover=False, trigger=0, w=None, h=None):
        self.kind = kind
        self.x = x
        self.wy = wy
        self.w, self.h = (w, h) if w else Entity.SIZES[kind]
        self.vx = vx
        self.mover = mover
        self.trigger = trigger      # screen y at which a mover starts moving
        self.active = False
        self.alive = True
        self.t = 0

    def rect(self, cam):
        sy = to_screen(self.wy, cam)
        return pygame.Rect(int(self.x - self.w / 2), int(sy - self.h / 2), self.w, self.h)

    def update(self, cam):
        self.t += 1
        sy = to_screen(self.wy, cam)
        if self.kind == "jet":
            if sy > -20:
                self.active = True
            if self.active:
                self.x += self.vx
                if (self.vx > 0 and self.x > W + 60) or (self.vx < 0 and self.x < -60):
                    self.alive = False
            return
        if not self.mover:
            return
        if not self.active and sy >= self.trigger:
            self.active = True
        if not self.active:
            return
        self.x += self.vx
        l, r, il, ir = terrain_at(self.wy)
        lo, hi = l, r
        if il is not None:
            if self.x < (il + ir) / 2:
                hi = il
            else:
                lo = ir
        if self.x - self.w / 2 < lo:
            self.x = lo + self.w / 2
            self.vx = abs(self.vx)
        elif self.x + self.w / 2 > hi:
            self.x = hi - self.w / 2
            self.vx = -abs(self.vx)

    def draw(self, s, cam, font):
        sy = int(to_screen(self.wy, cam))
        x = int(self.x)
        d = 1 if self.vx >= 0 else -1
        if self.kind == "ship":
            hull = [(x - 32, sy - 2), (x + 32, sy - 2), (x + 24, sy + 9), (x - 24, sy + 9)]
            pygame.draw.polygon(s, (25, 25, 25), hull)
            pygame.draw.rect(s, RED, (x - 28, sy - 6, 56, 5))
            pygame.draw.rect(s, (210, 210, 210), (x - 18 * d - 7, sy - 14, 14, 9))
            pygame.draw.rect(s, (25, 25, 25), (x - 18 * d - 2, sy - 19, 4, 6))
        elif self.kind == "heli":
            body = pygame.Rect(x - 11, sy - 7, 22, 14)
            pygame.draw.ellipse(s, (40, 120, 40), body)
            pygame.draw.ellipse(s, (150, 210, 230), (x + 2 * d - 4 if d > 0 else x - 8, sy - 4, 8, 6))
            pygame.draw.line(s, (40, 120, 40), (x - 8 * d, sy), (x - 19 * d, sy - 3), 3)
            pygame.draw.line(s, (30, 30, 30), (x - 19 * d, sy - 7), (x - 19 * d, sy + 1), 2)
            span = 17 if (self.t // 4) % 2 else 6
            pygame.draw.line(s, (30, 30, 30), (x - span, sy - 10), (x + span, sy - 10), 2)
            pygame.draw.line(s, (30, 30, 30), (x, sy - 10), (x, sy - 7), 2)
            pygame.draw.line(s, (30, 30, 30), (x - 8, sy + 9), (x + 8, sy + 9), 2)
        elif self.kind == "jet":
            pts = [(x + 21 * d, sy), (x + 6 * d, sy - 3), (x - 4 * d, sy - 11), (x - 10 * d, sy - 11),
                   (x - 6 * d, sy - 3), (x - 17 * d, sy - 3), (x - 21 * d, sy - 8), (x - 21 * d, sy + 5),
                   (x + 6 * d, sy + 5)]
            pygame.draw.polygon(s, (90, 150, 230), pts)
            pygame.draw.polygon(s, (20, 40, 90), pts, 1)
        elif self.kind == "fuel":
            r = pygame.Rect(x - 15, sy - 28, 30, 56)
            for i in range(4):
                col = RED if i % 2 == 0 else WHITE
                pygame.draw.rect(s, col, (r.x, r.y + i * 14, 30, 14))
                letter = font.render("FUEL"[i], True, WHITE if col == RED else RED)
                s.blit(letter, letter.get_rect(center=(x, r.y + i * 14 + 7)))
            pygame.draw.rect(s, (90, 20, 20), r, 1)
        elif self.kind == "bridge":
            r = self.rect(cam)
            pygame.draw.rect(s, (150, 120, 60), r)
            pygame.draw.rect(s, (90, 70, 30), (r.x, r.y, r.w, 4))
            pygame.draw.rect(s, (90, 70, 30), (r.x, r.bottom - 4, r.w, 4))
            for px in range(r.x + 8, r.right - 4, 16):
                pygame.draw.line(s, (220, 200, 60), (px, sy), (px + 7, sy), 2)


# ---------------------------------------------------------------- level spawning
def spawn_section(sec, skip_below_wy):
    rng = random.Random(SEED * 104729 + sec)
    rows, _ = section_data(sec)
    base = sec * SEC_LEN
    ents = []
    if sec > 0:
        l, rr, _, _ = rows[BRIDGE_ROW]
        ents.append(Entity("bridge", (l + rr) / 2, base + BRIDGE_ROW * ROW + 5, w=rr - l, h=26))
    diff = min(sec + _level["offset"], 12)
    speed = (1.0 + diff * 0.15) * _level["enemy_speed"]
    mover_p = min(0.9, 0.35 + diff * 0.06)
    spacing = _level["spacing"]
    r = 60
    while r < SEC_ROWS - 25:
        wy = base + r * ROW + 5
        l, rr, il, ir = rows[r]
        spans = [(l, rr)] if il is None else [(l, il), (ir, rr)]
        a, b = rng.choice(spans)
        roll = rng.random()
        if sec >= max(1, _level["jets_from"]) and roll < 0.10:
            kind = "jet"
        elif roll < 0.28:
            kind = "fuel"
        elif roll < 0.63:
            kind = "ship"
        else:
            kind = "heli"
        ew = Entity.SIZES[kind][0]
        if kind == "jet":
            d = rng.choice((-1, 1))
            ents.append(Entity("jet", -40 if d > 0 else W + 40, wy,
                               vx=d * (4.0 + diff * 0.2) * min(1.3, _level["enemy_speed"])))
        elif b - a >= ew + 12 and wy > skip_below_wy:
            x = rng.uniform(a + ew / 2 + 4, b - ew / 2 - 4)
            mover = kind != "fuel" and rng.random() < mover_p
            v = speed * (1.3 if kind == "heli" else 1.0) * rng.choice((-1, 1))
            ents.append(Entity(kind, x, wy, vx=v, mover=mover, trigger=rng.randint(40, 260)))
        r += rng.randint(max(7, 20 - diff + spacing), max(11, 32 - diff + spacing))
    return ents


# ---------------------------------------------------------------- drawing helpers
def draw_plane(s, x, y, bank=0, color=YELLOW, scale=1.0):
    wing = 14 * (0.65 if bank else 1.0) * scale
    k = scale
    pts = [(x, y - 14 * k), (x + 3 * k, y - 6 * k), (x + wing, y + 2 * k), (x + wing, y + 6 * k),
           (x + 3 * k, y + 4 * k), (x + 6 * k, y + 12 * k), (x - 6 * k, y + 12 * k), (x - 3 * k, y + 4 * k),
           (x - wing, y + 6 * k), (x - wing, y + 2 * k), (x - 3 * k, y - 6 * k)]
    pygame.draw.polygon(s, color, pts)
    pygame.draw.polygon(s, (120, 110, 20), pts, 1)


def draw_terrain(s, cam, title=False):
    s.fill(GRASS, (0, 0, W, PLAY_H))
    r0 = max(0, int(cam // ROW) - 1)
    r1 = int((cam + PLAY_H) // ROW) + 1
    for r in range(r0, r1 + 1):
        l, rr, il, ir = terrain_row(r)
        top = round(PLAY_H + cam - (r + 1) * ROW)
        h = round(PLAY_H + cam - r * ROW) - top
        pygame.draw.rect(s, SHORE, (l - 4, top, rr - l + 8, h))
        pygame.draw.rect(s, WATER, (l, top, rr - l, h))
        if il is not None:
            pygame.draw.rect(s, SHORE, (il, top, ir - il, h))
            pygame.draw.rect(s, GRASS, (il + 4, top, max(0, ir - il - 8), h))

    sec0 = max(0, int(cam // SEC_LEN))
    sec1 = int((cam + PLAY_H) // SEC_LEN) + 1
    for sec in range(sec0, sec1 + 1):
        rows, decos = section_data(sec)
        if sec > 0:   # road leading to the bridge
            l, rr, _, _ = rows[BRIDGE_ROW]
            sy = to_screen(sec * SEC_LEN + BRIDGE_ROW * ROW + 5, cam)
            for x0, x1 in ((0, l - 4), (rr + 4, W)):
                pygame.draw.rect(s, ROAD, (x0, sy - 13, x1 - x0, 26))
                for dx in range(x0 + 6, x1 - 10, 28):
                    pygame.draw.rect(s, YELLOW, (dx, sy - 1, 14, 2))
        for wy, x, kind in decos:
            sy = to_screen(wy, cam)
            if -20 < sy < PLAY_H + 20:
                x, sy = int(x), int(sy)
                if kind == "tree":
                    pygame.draw.rect(s, (110, 70, 30), (x - 2, sy + 2, 4, 7))
                    pygame.draw.circle(s, (20, 90, 30), (x, sy - 2), 8)
                    pygame.draw.circle(s, (40, 120, 45), (x - 2, sy - 4), 4)
                else:
                    pygame.draw.rect(s, (225, 205, 160), (x - 11, sy - 4, 22, 13))
                    pygame.draw.polygon(s, (170, 50, 40), [(x - 14, sy - 4), (x + 14, sy - 4), (x, sy - 15)])
                    pygame.draw.rect(s, (90, 60, 30), (x - 3, sy + 2, 6, 7))


# ---------------------------------------------------------------- game
class Game:
    def __init__(self, screen):
        self.screen = screen
        self.font_big = pygame.font.Font(None, 72)
        self.font = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)
        self.font_tiny = pygame.font.Font(None, 18)
        self.sounds = Sounds()
        self.hiscores = self._load_hiscores()
        self.level_idx = 1
        self.state = "title"
        self.cam = 0.0
        self.particles = []
        self.frame = 0
        self.paused = False

    @property
    def level(self):
        return LEVELS[self.level_idx]

    @property
    def hiscore(self):
        return self.hiscores.get(self.level["name"], 0)

    @hiscore.setter
    def hiscore(self, value):
        self.hiscores[self.level["name"]] = value

    # ---- persistence
    def _load_hiscores(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                data = json.load(f)
            if isinstance(data, int):       # old single-score format: those were MEDIUM settings
                return {"MEDIUM": data}
            return {k: int(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except (OSError, ValueError, AttributeError):
            return {}

    def _save_hiscore(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                json.dump(self.hiscores, f)
        except OSError:
            pass

    # ---- game flow
    def new_game(self):
        set_level(self.level)
        self.score = 0
        self.lives = self.level["lives"]
        self.checkpoint = 0
        self.next_life = EXTRA_LIFE_EVERY
        self.respawn()

    def respawn(self):
        self.cam = self.checkpoint * SEC_LEN + 220.0
        pwy = self.cam + PLAYER_OFF
        l, r, il, ir = terrain_at(pwy)
        if il is None:
            self.px = (l + r) / 2
        else:
            self.px = (l + il) / 2 if il - l > r - ir else (ir + r) / 2
        self.entities = []
        self.next_spawn = self.checkpoint
        self.bullet = None
        self.fuel = 100.0
        self.particles = []
        self.bank = 0
        self.speed = SPEED_NORMAL
        self.refueling = False
        self.state = "ready"
        self._ensure_spawned()

    def _ensure_spawned(self):
        while self.next_spawn * SEC_LEN < self.cam + PLAY_H + 400:
            self.entities += spawn_section(self.next_spawn, self.cam + PLAYER_OFF + 150)
            self.next_spawn += 1

    def add_score(self, pts):
        self.score += pts
        if self.score >= self.next_life:
            self.next_life += EXTRA_LIFE_EVERY
            self.lives += 1
            self.sounds.play("life")
        if self.score > self.hiscore:
            self.hiscore = self.score

    def explode(self, x, wy, n=26, big=False):
        rng = random.random
        for _ in range(n):
            ang = rng() * math.tau
            sp = rng() * (5 if big else 3.5) + 0.5
            col = random.choice(((255, 220, 60), (255, 140, 30), (230, 50, 30), (90, 90, 90), WHITE))
            life = random.randint(25, 55 if big else 40)
            self.particles.append([x, wy, math.cos(ang) * sp, math.sin(ang) * sp, life, life, col])

    def crash(self):
        self.explode(self.px, self.cam + PLAYER_OFF, 60, big=True)
        self.sounds.play("big_boom")
        self.state = "dying"
        self.timer = 100
        self.bullet = None

    # ---- events
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.quit()
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_ESCAPE:
            self.quit()
        if self.state == "title":
            if e.key in (pygame.K_UP, pygame.K_w):
                self.level_idx = (self.level_idx - 1) % len(LEVELS)
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                self.level_idx = (self.level_idx + 1) % len(LEVELS)
            elif pygame.K_1 <= e.key < pygame.K_1 + len(LEVELS):
                self.level_idx = e.key - pygame.K_1
            elif e.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.new_game()
        elif self.state == "gameover" and e.key in (pygame.K_RETURN, pygame.K_SPACE) and self.timer <= 0:
            self.state = "title"
        elif self.state == "ready" and e.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_RIGHT,
                                                 pygame.K_SPACE, pygame.K_DOWN):
            self.state = "play"
        elif self.state == "play" and e.key == pygame.K_p:
            self.paused = not self.paused

    def quit(self):
        self._save_hiscore()
        pygame.quit()
        sys.exit()

    # ---- update
    def update(self):
        self.frame += 1
        if self.state == "title":
            self.cam += 1.2
            return
        if self.paused:
            return
        self._update_particles()
        if self.state == "dying":
            self.timer -= 1
            if self.timer <= 0:
                self.lives -= 1
                if self.lives > 0:
                    self.respawn()
                else:
                    self._save_hiscore()
                    self.state = "gameover"
                    self.timer = 45
            return
        if self.state == "gameover":
            self.timer -= 1
            return
        if self.state != "play":
            return

        keys = pygame.key.get_pressed()
        self.bank = 0
        if keys[pygame.K_LEFT]:
            self.px -= 4.5
            self.bank = -1
        if keys[pygame.K_RIGHT]:
            self.px += 4.5
            self.bank = 1
        self.px = max(10, min(W - 10, self.px))
        self.speed = SPEED_FAST if keys[pygame.K_UP] else SPEED_SLOW if keys[pygame.K_DOWN] else SPEED_NORMAL
        self.cam += self.speed
        pwy = self.cam + PLAYER_OFF

        # fuel
        self.fuel -= self.level["drain"]
        if self.fuel < 25 and self.frame % 30 == 0:
            self.sounds.play("alarm")
        if self.fuel <= 0:
            self.fuel = 0
            self.crash()
            return

        # bullet
        if self.bullet is None and keys[pygame.K_SPACE]:
            self.bullet = [self.px, pwy + 14]
            self.sounds.play("shoot")
        if self.bullet:
            self.bullet[1] += 12 + self.speed
            if to_screen(self.bullet[1], self.cam) < -15:
                self.bullet = None

        self._ensure_spawned()
        for en in self.entities:
            en.update(self.cam)

        # bullet hits
        if self.bullet:
            br = pygame.Rect(int(self.bullet[0]) - 2, int(to_screen(self.bullet[1], self.cam)) - 6, 4, 12)
            for en in self.entities:
                if en.alive and en.rect(self.cam).colliderect(br):
                    en.alive = False
                    self.bullet = None
                    self.add_score(POINTS[en.kind])
                    if en.kind == "bridge":
                        self.explode(en.x, en.wy, 70, big=True)
                        self.checkpoint = int(en.wy // SEC_LEN)
                        self.sounds.play("big_boom")
                    else:
                        self.explode(en.x, en.wy)
                        self.sounds.play("boom")
                    break

        # player vs terrain
        for dx, dy in ((0, 13), (-13, -3), (13, -3), (-5, -11), (5, -11)):
            if on_land(self.px + dx, pwy + dy):
                self.crash()
                return

        # player vs entities
        prect = pygame.Rect(int(self.px) - 11, PLAYER_SY - 11, 22, 22)
        self.refueling = False
        for en in self.entities:
            if en.alive and en.rect(self.cam).colliderect(prect):
                if en.kind == "fuel":
                    self.refueling = True
                    if self.fuel < 100:
                        self.fuel = min(100.0, self.fuel + self.level["refill"])
                        if self.frame % 6 == 0:
                            self.sounds.play("fuel")
                else:
                    en.alive = False
                    self.explode(en.x, en.wy)
                    self.crash()
                    return

        self.entities = [en for en in self.entities
                         if en.alive and to_screen(en.wy, self.cam) < PLAY_H + 80]

    def _update_particles(self):
        alive = []
        for p in self.particles:
            p[0] += p[2]
            p[1] -= p[3]
            p[2] *= 0.96
            p[3] *= 0.96
            p[4] -= 1
            if p[4] > 0:
                alive.append(p)
        self.particles = alive

    # ---- draw
    def draw(self):
        s = self.screen
        s.set_clip((0, 0, W, PLAY_H))
        draw_terrain(s, self.cam)
        if self.state == "title":
            s.set_clip(None)
            self._draw_title()
            return

        for en in self.entities:
            sy = to_screen(en.wy, self.cam)
            if en.alive and -60 < sy < PLAY_H + 60:
                en.draw(s, self.cam, self.font_tiny)
        if self.bullet:
            by = int(to_screen(self.bullet[1], self.cam))
            pygame.draw.rect(s, YELLOW, (int(self.bullet[0]) - 1, by - 6, 3, 12))
        if self.state in ("play", "ready"):
            draw_plane(s, int(self.px), PLAYER_SY, self.bank)
        for x, wy, _, _, life, maxlife, col in self.particles:
            sz = max(1, int(5 * life / maxlife))
            pygame.draw.rect(s, col, (int(x), int(to_screen(wy, self.cam)), sz, sz))
        s.set_clip(None)

        self._draw_hud()
        if self.state == "ready":
            self._center_text("Press an arrow key or SPACE to fly", self.font, PLAY_H // 2 - 60)
        elif self.state == "gameover":
            self._center_text("GAME OVER", self.font_big, PLAY_H // 2 - 40, RED)
            self._center_text("Press ENTER", self.font, PLAY_H // 2 + 20)
        if self.paused:
            self._center_text("PAUSED", self.font_big, PLAY_H // 2 - 30)

    def _center_text(self, text, font, y, color=WHITE):
        img = font.render(text, True, color)
        shadow = font.render(text, True, BLACK)
        rect = img.get_rect(center=(W // 2, y))
        self.screen.blit(shadow, rect.move(3, 3))
        self.screen.blit(img, rect)

    def _draw_title(self):
        s = self.screen
        overlay = pygame.Surface((W, PLAY_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 110))
        s.blit(overlay, (0, 0))
        self._center_text("RIVER RAID", self.font_big, 55, YELLOW)
        self._center_text("a tribute to the 1982 classic", self.font_small, 95)

        # difficulty menu
        self._center_text("SELECT LEVEL", self.font_small, 130, (200, 200, 200))
        box_w, box_h = 440, 50
        for i, lv in enumerate(LEVELS):
            rect = pygame.Rect(W // 2 - box_w // 2, 148 + i * (box_h + 8), box_w, box_h)
            selected = i == self.level_idx
            panel = pygame.Surface(rect.size, pygame.SRCALPHA)
            panel.fill((0, 0, 0, 200) if selected else (0, 0, 0, 110))
            s.blit(panel, rect)
            pygame.draw.rect(s, lv["color"] if selected else (110, 110, 110), rect, 3 if selected else 1)
            name = self.font.render(f"{i + 1}. {lv['name']}", True, lv["color"])
            s.blit(name, (rect.x + 40, rect.y + 6))
            desc = self.font_tiny.render(lv["desc"], True, WHITE if selected else (180, 180, 180))
            s.blit(desc, (rect.x + 40, rect.y + 32))
            best = self.font_tiny.render(f"BEST {self.hiscores.get(lv['name'], 0)}", True, (200, 200, 200))
            s.blit(best, best.get_rect(topright=(rect.right - 14, rect.y + 10)))
            if selected:
                draw_plane(s, rect.x + 20, rect.centery, color=lv["color"], scale=0.8)

        lines = ["UP / DOWN or 1-4  choose level      ENTER  start",
                 "In game:  ARROWS fly    SPACE fire    P pause    ESC quit",
                 "Refuel over FUEL depots. Shoot bridges for checkpoints."]
        for i, ln in enumerate(lines):
            self._center_text(ln, self.font_small, 395 + i * 26)
        if (self.frame // 30) % 2 == 0:
            self._center_text("Press ENTER to start", self.font, 485, self.level["color"])
        s.fill(HUD_BG, (0, PLAY_H, W, HUD_H))
        txt = self.font.render(f"{self.level['name']}  HIGH SCORE  {self.hiscore}", True, BLACK)
        s.blit(txt, txt.get_rect(center=(W // 2, PLAY_H + HUD_H // 2)))

    def _draw_hud(self):
        s = self.screen
        s.fill(HUD_BG, (0, PLAY_H, W, HUD_H))
        pygame.draw.line(s, (80, 80, 80), (0, PLAY_H), (W, PLAY_H), 3)

        score = self.font.render(f"{self.score}", True, YELLOW)
        s.blit(score, score.get_rect(center=(W // 2, PLAY_H + 18)))

        # fuel gauge
        gx, gy, gw, gh = W // 2 - 115, PLAY_H + 36, 230, 40
        low = self.fuel < 25 and (self.frame // 15) % 2 == 0
        pygame.draw.rect(s, BLACK, (gx, gy, gw, gh))
        pygame.draw.rect(s, RED if low else (60, 60, 60), (gx, gy, gw, gh), 3)
        for label, fx in (("E", 0.0), ("1/2", 0.5), ("F", 1.0)):
            img = self.font_small.render(label, True, WHITE)
            s.blit(img, img.get_rect(center=(gx + 14 + fx * (gw - 28), gy + 12)))
            pygame.draw.line(s, WHITE, (gx + 14 + fx * (gw - 28), gy + 22),
                             (gx + 14 + fx * (gw - 28), gy + gh - 5), 1)
        nx = gx + 14 + (self.fuel / 100) * (gw - 28)
        pygame.draw.rect(s, YELLOW, (int(nx) - 3, gy + 20, 6, gh - 23))

        lv = self.font_small.render(self.level["name"], True, BLACK)
        s.blit(lv, (18, PLAY_H + 14))
        # lives
        for i in range(min(self.lives, 8)):
            draw_plane(s, 30 + i * 30, PLAY_H + 58, scale=0.8)
        # hiscore & bridge counter
        hi = self.font_small.render(f"HI {self.hiscore}", True, BLACK)
        s.blit(hi, hi.get_rect(topright=(W - 20, PLAY_H + 20)))
        sec = int((self.cam + PLAYER_OFF) // SEC_LEN)
        br = self.font_small.render(f"BRIDGE {sec}", True, BLACK)
        s.blit(br, br.get_rect(topright=(W - 20, PLAY_H + 50)))


def main():
    pygame.mixer.pre_init(22050, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("River Raid")
    clock = pygame.time.Clock()
    game = Game(screen)
    while True:
        for e in pygame.event.get():
            game.handle_event(e)
        game.update()
        game.draw()
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
