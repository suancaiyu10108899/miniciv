# prototype_hex/game_hex.py — Hex grid game loop
# Adapts prototype/game.py for hex coordinates.
# Shares combat/economy/tech/unit logic.

import random
from dataclasses import dataclass, field
from prototype_hex.mapgen_hex import generate_map_hex, get_terrain_hex, MAP_W, MAP_H
from prototype.terrain import Terrain
from prototype.unit import Unit, City
from prototype.combat import resolve_melee, resolve_ranged, city_occupation_damage
from prototype.economy import Economy, worker_action_build, worker_action_produce, produce_unit, destroy_facility, city_base_income
from prototype.tech import TechManager, apply_tech_to_unit
from prototype.constants import MAX_TURNS, CITY_HP, UNIT_STATS, CITY_DAMAGE
from prototype_hex.movement_hex import (
    HEX_DIRS, wrap, hex_distance, get_single_step_moves_hex, cavalry_forest_check_hex
)

SIZE = MAP_W  # for compatibility


@dataclass
class GameState:
    seed: int
    size: int
    generator_id: str
    turn: int = 0
    grid: list = field(default_factory=list)
    units: list[Unit] = field(default_factory=list)
    cities: list[City] = field(default_factory=list)
    economies: list[Economy] = field(default_factory=list)
    techs: list[TechManager] = field(default_factory=list)
    winner: int | None = None
    victory_type: str | None = None
    rng: random.Random = field(default_factory=lambda: random.Random(0))
    dead_units: list[Unit] = field(default_factory=list)
    action_log: list[dict] = field(default_factory=list)
    turn_snapshots: list[dict] = field(default_factory=list)


def init_game_hex(seed: int, generator_id: str = "balanced") -> GameState:
    gs = GameState(seed=seed, size=SIZE, generator_id=generator_id)
    gs.rng = random.Random(seed)
    gs.grid = generate_map_hex(seed=seed, generator_id=generator_id)

    # Find city positions
    cities_info = []
    for r in range(MAP_H):
        for q in range(MAP_W):
            if gs.grid[r][q]["terrain"] == Terrain.CITY:
                cities_info.append((q, r))

    cities_info.sort(key=lambda c: (c[1], c[0]))
    (cx0, cy0), (cx1, cy1) = cities_info[:2]  # (q, r) stored as (x, y) in Unit

    gs.cities = [City(0, cx0, cy0), City(1, cx1, cy1)]

    # Initial units (same as square)
    from prototype.constants import STARTING_UNITS
    gs.units = []
    n_workers = STARTING_UNITS.get("worker", 3)
    n_scouts = STARTING_UNITS.get("scout", 1)

    for pid, (cx, cy) in enumerate([(cx0, cy0), (cx1, cy1)]):
        for _ in range(n_workers):
            for dq, dr in HEX_DIRS:
                nq, nr = wrap(cx + dq, cy + dr)
                t = get_terrain_hex(gs.grid, nq, nr)
                if t == Terrain.PLAIN:
                    occupied = any(u.x == nq and u.y == nr for u in gs.units)
                    if not occupied:
                        gs.units.append(Unit.create("worker", pid, nq, nr))
                        break
        for _ in range(n_scouts):
            for dq, dr in HEX_DIRS:
                nq, nr = wrap(cx + dq, cy + dr)
                t = get_terrain_hex(gs.grid, nq, nr)
                if t == Terrain.PLAIN:
                    occupied = any(u.x == nq and u.y == nr for u in gs.units)
                    if not occupied:
                        gs.units.append(Unit.create("scout", pid, nq, nr))
                        break

    gs.economies = [Economy(0), Economy(1)]
    gs.techs = [TechManager(0), TechManager(1)]
    return gs


def step_game_hex(gs: GameState, actions_p0: list[dict], actions_p1: list[dict]) -> dict:
    gs.turn += 1
    gs.action_log.append({"turn": gs.turn, "p0": actions_p0, "p1": actions_p1})

    player_order = [(0, actions_p0), (1, actions_p1)] if gs.turn % 2 == 1 else [(1, actions_p1), (0, actions_p0)]
    for pid, actions in player_order:
        units = [u for u in gs.units if u.player_id == pid and u.alive]
        econ = gs.economies[pid]
        tech = gs.techs[pid]
        bonuses = tech.get_tech_bonuses()

        for act in actions:
            atype = act.get("type", "end_turn")
            ui = act.get("unit_idx", -1)
            unit = units[ui] if (0 <= ui < len(units)) else None

            if atype == "move" and unit:
                dq, dr = act.get("dx", 0), act.get("dy", 0)
                _do_move_hex(unit, gs, dq, dr)
            elif atype == "build" and unit and unit.unit_type == "worker":
                worker_action_build(unit, gs.grid, pid)
            elif atype == "produce" and unit and unit.unit_type == "worker":
                worker_action_produce(unit, gs.grid, pid, econ, bonuses)
            elif atype == "produce_unit":
                utype = act.get("unit_type", "infantry")
                city = gs.cities[pid]
                produce_unit(gs.grid, city, econ, utype, gs.units)
            elif atype == "research":
                tech_id = act.get("tech_id")
                if tech_id:
                    cost = TECH_TREE_COST.get(tech_id, (0, 0, 0))
                    if econ.can_afford(cost) and tech.start_research(tech_id):
                        econ.spend(cost)
            elif atype == "destroy" and unit:
                destroy_facility(gs.grid, unit.x, unit.y)

        food_bonus = bonuses.get("city_food", 0)
        city_base_income(econ, food_bonus)

    # Tech tick (simultaneous)
    for pid in (0, 1):
        gs.techs[pid].tick_research()

    # Construction victory check (every turn)
    from prototype.constants import CONSTRUCTION_VICTORY_REQUIRE_FACILITIES
    from prototype_hex.mapgen_hex import get_facility_hex
    for pid in (0, 1):
        if "C5" in gs.techs[pid].completed and gs.winner is None:
            fc = 0
            for r in range(MAP_H):
                for q in range(MAP_W):
                    f = get_facility_hex(gs.grid, q, r)
                    if f is not None and f.player_id == pid:
                        fc += 1
            if fc >= CONSTRUCTION_VICTORY_REQUIRE_FACILITIES:
                gs.winner = pid
                gs.victory_type = "construction"

    # City defense
    for pid in (0, 1):
        city = gs.cities[pid]
        for u in gs.units:
            if u.alive and u.player_id != pid and u.x == city.x and u.y == city.y:
                u.hp -= CITY_DAMAGE
                if u.hp <= 0:
                    u.hp = 0
                    u.alive = False

    # Conquest check
    for pid in (0, 1):
        if gs.cities[1 - pid].hp <= 0:
            gs.winner = pid
            gs.victory_type = "conquest"

    # Tiebreak
    if gs.turn >= MAX_TURNS and gs.winner is None:
        _tiebreak(gs)

    # Cleanup
    gs.dead_units.extend([u for u in gs.units if not u.alive])
    gs.units = [u for u in gs.units if u.alive]

    # Snapshot for replay
    from prototype.snapshot import snapshot_turn
    gs.turn_snapshots.append(snapshot_turn(gs))

    return {"turn": gs.turn, "winner": gs.winner, "victory_type": gs.victory_type}


def _unit_category(ut): return "civilian" if ut == "worker" else "combat"
MAX_COMBAT = 1; MAX_CIVILIAN = 1


def _do_move_hex(unit, gs, dq, dr):
    if not unit.alive: return
    dq, dr = cavalry_forest_check_hex(unit, gs.grid, dq, dr)
    nq, nr = wrap(unit.x + dq, unit.y + dr)

    cat = _unit_category(unit.unit_type)
    max_ok = MAX_COMBAT if cat == "combat" else MAX_CIVILIAN
    friend_same = sum(1 for u in gs.units if u.alive and u.player_id == unit.player_id
                      and u.x == nq and u.y == nr and _unit_category(u.unit_type) == cat)
    if friend_same >= max_ok: return

    blocker = next((u for u in gs.units if u.alive and u.player_id != unit.player_id
                    and u.x == nq and u.y == nr), None)

    if blocker:
        if unit.ranged:
            resolve_ranged(unit, blocker, get_terrain_hex(gs.grid, blocker.x, blocker.y))
        else:
            t_att = get_terrain_hex(gs.grid, unit.x, unit.y)
            t_def = get_terrain_hex(gs.grid, blocker.x, blocker.y)
            charged = (unit.unit_type == "cavalry" and abs(dq)+abs(dr) == 2
                       and get_terrain_hex(gs.grid, unit.x, unit.y) == Terrain.PLAIN)
            result = resolve_melee(unit, blocker, t_att, t_def, attacker_just_charged=charged)
            if result["attacker_alive"] and not result["defender_alive"]:
                unit.x, unit.y = nq, nr
                opp_city = gs.cities[1 - unit.player_id]
                if nq == opp_city.x and nr == opp_city.y:
                    opp_city.hp -= city_occupation_damage(unit, opp_city)
    else:
        unit.x, unit.y = nq, nr
        opp_city = gs.cities[1 - unit.player_id]
        if nq == opp_city.x and nr == opp_city.y:
            opp_city.hp -= city_occupation_damage(unit, opp_city)


def _tiebreak(gs):
    c0 = gs.techs[0].construction_count()
    c1 = gs.techs[1].construction_count()
    if c0 > c1: gs.winner, gs.victory_type = 0, "tiebreak_construction"
    elif c1 > c0: gs.winner, gs.victory_type = 1, "tiebreak_construction"
    elif gs.cities[0].hp > gs.cities[1].hp: gs.winner, gs.victory_type = 0, "tiebreak_city_hp"
    elif gs.cities[1].hp > gs.cities[0].hp: gs.winner, gs.victory_type = 1, "tiebreak_city_hp"
    else: gs.winner = gs.rng.randint(0, 1); gs.victory_type = "tiebreak_random"


from prototype.constants import TECH_TREE as _TECH_TREE
TECH_TREE_COST = {k: v["cost"] for k, v in _TECH_TREE.items()}
