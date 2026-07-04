#!/usr/bin/env python3
"""hex_prototype.py — Hexagonal grid rendering and unit movement demo for miniciv.

A standalone prototype demonstrating axial-coordinate hex grids, terminal rendering
with proper flat-top hex staggering, step-by-step movement using WASD-derived
directional keys, and basic combat resolution.

Usage:
    python hex_prototype.py
"""

import os
import sys
from collections import deque

# =========================================================================
# Constants
# =========================================================================

RADIUS = 6

# Axial direction vectors (flat-top hex orientation):
#   E (+1,0)   NE (+1,-1)   NW (0,-1)
#   W (-1,0)   SW (-1,+1)   SE (0,+1)
DIRECTIONS = [(+1, 0), (+1, -1), (0, -1), (-1, 0), (-1, +1), (0, +1)]

# Key -> direction vector mapping:
#   W = NW    E = NE    D = E
#   A = W     Q = SW    S = SE
KEY_DIR = {
    "w": (0, -1),   # NW
    "e": (+1, -1),  # NE
    "d": (+1, 0),   # E
    "a": (-1, 0),   # W
    "q": (-1, +1),  # SW
    "s": (0, +1),   # SE
}

TERRAIN_CHAR = {
    "PLAIN": ".",
    "FOREST": "T",
    "MOUNTAIN": "^",
    "WATER": "~",
    "CITY": "C",
}

# =========================================================================
# Hex math
# =========================================================================


def hex_dist(a, b):
    """Distance between two axial hex coordinates."""
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


# =========================================================================
# Unit
# =========================================================================


class Unit:
    """A combat unit on the hex grid."""

    def __init__(self, owner, utype, q, r):
        self.owner = owner  # 0 or 1
        self.utype = utype  # 'infantry' or 'cavalry'
        self.q = q
        self.r = r
        if utype == "infantry":
            self.hp = 5
            self.max_hp = 5
            self.atk = 3
            self.defense = 2
            self.moves = 1
        else:  # cavalry
            self.hp = 4
            self.max_hp = 4
            self.atk = 4
            self.defense = 1
            self.moves = 2

    @property
    def pos(self):
        return (self.q, self.r)

    @pos.setter
    def pos(self, value):
        self.q, self.r = value

    def alive(self):
        return self.hp > 0

    def __repr__(self):
        side = "P0" if self.owner == 0 else "P1"
        return f"[{side} {self.utype} ({self.q},{self.r}) HP={self.hp}/{self.max_hp}]"


# =========================================================================
# Grid generation
# =========================================================================


def generate_grid(radius):
    """Generate a hex-shaped grid of the given radius in axial coordinates."""
    cells = {}
    for r in range(-radius, radius + 1):
        q_min = max(-radius, -radius - r)
        q_max = min(radius, radius - r)
        for q in range(q_min, q_max + 1):
            cells[(q, r)] = {"terrain": "PLAIN"}
    return cells


# =========================================================================
# Rendering — canvas-based with proper flat-top hex staggering
# =========================================================================


def _hex_char(pos, cells, units, selected_xy, reachable):
    """Return a 3-character display string for the hex at *pos*."""
    q, r = pos

    # Unit present and alive?
    unit = None
    for u in units:
        if u.alive() and u.q == q and u.r == r:
            unit = u
            break

    if unit:
        if unit.utype == "infantry":
            ch = "I" if unit.owner == 0 else "i"
        else:
            ch = "K" if unit.owner == 0 else "k"
        if selected_xy and pos == selected_xy:
            return f"[{ch}]"
        return f" {ch} "

    # Terrain
    cell = cells.get(pos)
    if cell is None:
        return "   "
    terrain = cell["terrain"]
    ch = TERRAIN_CHAR.get(terrain, ".")

    if pos in reachable:
        return f"({ch})"
    return f" {ch} "


def render(cells, units, radius, selected_xy=None, reachable=None):
    """Render the hex grid as a string.

    Uses the canvas approach with proper flat-top hex column offset
    (``screen_col = q * 4 + r * 2``) so odd-*r* rows are visually
    indented by half a hex width.
    """
    reachable = reachable or set()

    # --- First pass: find bounds ---
    min_start = 0
    max_end = 0
    for r in range(-radius, radius + 1):
        q_min = max(-radius, -radius - r)
        q_max = min(radius, radius - r)
        for q in range(q_min, q_max + 1):
            start = q * 4 + r * 2
            end = start + 2  # 3-char hex
            if start < min_start:
                min_start = start
            if end > max_end:
                max_end = end

    width = max_end - min_start + 1

    # --- Second pass: draw each row ---
    lines = []
    for r in range(-radius, radius + 1):
        row = [" "] * width
        q_min = max(-radius, -radius - r)
        q_max = min(radius, radius - r)
        for q in range(q_min, q_max + 1):
            s = q * 4 + r * 2 - min_start
            chars = _hex_char((q, r), cells, units, selected_xy, reachable)
            # chars is 3 characters guaranteed
            for i, c in enumerate(chars):
                col = s + i
                if 0 <= col < width:
                    row[col] = c
        lines.append("".join(row).rstrip())

    return "\n".join(lines)


# =========================================================================
# Keyboard input (cross-platform)
# =========================================================================


def _getch():
    """Read a single keypress without waiting for Enter.

    Uses ``msvcrt`` on Windows, ``tty`` + ``termios`` on Unix.
    """
    try:
        import msvcrt

        ch = msvcrt.getch()
        # Arrow-key prefix (Windows)
        if ch == b"\xe0":
            ch = msvcrt.getch()
            # Map arrow keys to directions
            arrow_map = {b"H": "w", b"P": "s", b"M": "d", b"K": "a"}
            return arrow_map.get(ch, "")
        return ch.decode("utf-8", errors="replace").lower()
    except ImportError:
        # Unix fallback
        import tty
        import termios

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":  # ESC — check for arrow sequence
                # Read two more bytes for [A, [B etc.
                more = sys.stdin.read(2)
                arrow_map = {"[A": "w", "[B": "s", "[C": "d", "[D": "a"}
                ch = arrow_map.get(more, "")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return ch.lower()


# =========================================================================
# Movement range (BFS)
# =========================================================================


def get_reachable(pos, moves, cells, units, owner):
    """Return a set of (q,r) hexes reachable within *moves* steps.

    Units cannot pass through enemy or friendly units, but an enemy-occupied
    hex *is* a valid destination (attack).  Mountains and water are blocking.
    """
    blocked_terrain = {"MOUNTAIN", "WATER"}

    # Quick lookup
    unit_map = {}
    for u in units:
        if u.alive():
            unit_map[(u.q, u.r)] = u

    visited = {pos: 0}
    q = deque([pos])
    result = set()

    while q:
        cur = q.popleft()
        dist = visited[cur]

        if 0 < dist <= moves:
            result.add(cur)

        if dist >= moves:
            continue

        for dq, dr in DIRECTIONS:
            nb = (cur[0] + dq, cur[1] + dr)

            if nb not in cells:
                continue
            if cells[nb]["terrain"] in blocked_terrain:
                continue

            occupant = unit_map.get(nb)

            if occupant is not None and occupant.owner != owner:
                # Enemy hex — can be a destination (attack) but not traversable
                if dist + 1 <= moves:
                    result.add(nb)
                continue

            if occupant is not None and occupant.owner == owner:
                # Friendly — blocking
                continue

            if nb not in visited:
                visited[nb] = dist + 1
                q.append(nb)

    return result


# =========================================================================
# Combat
# =========================================================================


def resolve_combat(attacker, defender):
    """Apply damage: ``max(1, atk - def)``. Returns damage dealt."""
    damage = max(1, attacker.atk - defender.defense)
    defender.hp -= damage
    return damage


# =========================================================================
# Utility: clear screen + pause
# =========================================================================


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def wait_for_key(msg="Press any key to continue ..."):
    print(msg)
    _getch()


# =========================================================================
# Main game loop
# =========================================================================


def _status_bar(selected_unit, remaining_moves, reachable):
    """One-line status for the movement phase."""
    parts = []
    if remaining_moves < selected_unit.moves:
        parts.append(f"Moved ({remaining_moves} MP left)")
    else:
        parts.append(f"{selected_unit.moves} MP")
    if reachable:
        parts.append(f"{len(reachable)} reachable hexes")
    return " | ".join(parts)


def main():
    # ------------------------------------------------------------------
    # Initialise
    # ------------------------------------------------------------------
    cells = generate_grid(RADIUS)

    # Place cities
    cells[(0, -5)]["terrain"] = "CITY"  # P0
    cells[(0, 5)]["terrain"] = "CITY"   # P1

    # Create units — 2 per side
    units = [
        Unit(0, "infantry", -1, -5),
        Unit(0, "cavalry", 1, -5),
        Unit(1, "infantry", -1, 5),
        Unit(1, "cavalry", 1, 5),
    ]

    turn = 0  # 0 = Player 0, 1 = Player 1

    # ------------------------------------------------------------------
    # Game loop
    # ------------------------------------------------------------------
    while True:
        # -- win check --
        p0_alive = any(u.owner == 0 and u.alive() for u in units)
        p1_alive = any(u.owner == 1 and u.alive() for u in units)
        if not p0_alive:
            clear_screen()
            print(render(cells, units, RADIUS))
            print("\n=== PLAYER 1 WINS! ===")
            break
        if not p1_alive:
            clear_screen()
            print(render(cells, units, RADIUS))
            print("\n=== PLAYER 0 WINS! ===")
            break

        # -- draw --
        clear_screen()
        print("=== HEX PROTOTYPE ===")
        print("Keys:  W=NW  E=NE  D=E  A=W  Q=SW  S=SE")
        print("       X=cancel  .=done  Q=quit")
        print()
        print(render(cells, units, RADIUS))
        print()

        # -- list units --
        player_units = [u for u in units if u.owner == turn and u.alive()]
        print(f"--- Player {turn} ---")
        for i, u in enumerate(player_units):
            print(f"  {i + 1}. {u}")

        # -- select unit --
        sel_idx = None
        while sel_idx is None:
            inp = (
                input(f"Select unit (1-{len(player_units)}) or [Q]uit: ")
                .strip()
                .lower()
            )
            if inp == "q":
                print("Goodbye.")
                return
            if inp.isdigit():
                idx = int(inp) - 1
                if 0 <= idx < len(player_units):
                    sel_idx = idx
                else:
                    print(f"  Invalid: choose 1-{len(player_units)}")
            else:
                print("  Enter a number.")

        unit = player_units[sel_idx]
        remaining_moves = unit.moves
        sel_pos = unit.pos
        reachable = get_reachable(sel_pos, remaining_moves, cells, units, turn)

        # -- movement loop --
        moved = False
        while remaining_moves > 0:
            clear_screen()
            print("=== HEX PROTOTYPE ===")
            print("Keys:  W=NW  E=NE  D=E  A=W  Q=SW  S=SE")
            print("       X=cancel  .=done  Q=quit")
            print(f"  {unit.utype}: {_status_bar(unit, remaining_moves, reachable)}")
            print()
            print(render(cells, units, RADIUS, sel_pos, reachable))
            print()

            key = _getch()
            if not key:
                continue

            if key == "q":
                print("Goodbye.")
                return
            if key == "x":
                break  # Cancel unit selection
            if key == ".":
                moved = True
                break  # End this unit's turn

            if key in KEY_DIR:
                dq, dr = KEY_DIR[key]
                target = (sel_pos[0] + dq, sel_pos[1] + dr)

                # Must be an existing cell on the grid
                if target not in cells:
                    continue

                # Must be adjacent (distance == 1)
                if hex_dist(sel_pos, target) != 1:
                    continue

                # Must be traversable terrain (or city)
                if cells[target]["terrain"] in ("MOUNTAIN", "WATER"):
                    continue

                # Cannot move onto a friendly unit
                friendly_unit = None
                enemy_unit = None
                for u in units:
                    if not u.alive():
                        continue
                    if (u.q, u.r) == target:
                        if u.owner == turn:
                            friendly_unit = u
                        else:
                            enemy_unit = u
                        break

                if friendly_unit is not None:
                    continue

                # Execute the move
                unit.q, unit.r = target
                sel_pos = target
                remaining_moves -= 1
                moved = True

                # Combat?
                if enemy_unit is not None:
                    damage = resolve_combat(unit, enemy_unit)
                    print(
                        f"  {owner_label(unit.owner)} {unit.utype} attacks "
                        f"{owner_label(enemy_unit.owner)} {enemy_unit.utype} "
                        f"for {damage} damage!"
                    )
                    if not enemy_unit.alive():
                        print(f"  {owner_label(enemy_unit.owner)} {enemy_unit.utype} destroyed!")
                    wait_for_key()
                    break  # Combat ends movement

                # Recalculate reachable for next step (cavalry)
                reachable = get_reachable(
                    sel_pos, remaining_moves, cells, units, turn
                )
            # else: invalid key — ignore

        if moved:
            turn = 1 - turn


def owner_label(owner):
    return f"P{owner}"


# =========================================================================
# Entry point
# =========================================================================

if __name__ == "__main__":
    main()
