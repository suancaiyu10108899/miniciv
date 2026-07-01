# prototype/render_ascii.py — 终端 ASCII 渲染

from prototype.terrain import Terrain, TERRAIN_CHAR


def render_map(gs, pid: int = 0, fogs=None) -> str:
    """
    渲染 ASCII 地图。
    pid: 视角玩家（迷雾渲染按此玩家）。
    fogs: per-player fog state, None = 无迷雾(全可见)。
    """
    size = gs.size
    # 列标
    lines = ["   " + "".join(f"{i:2}"[-1] for i in range(size))]
    for y in range(size):
        row = [f"{y:2} "]
        for x in range(size):
            row.append(_cell_char(gs, x, y, pid, fogs))
        row.append(f" {y:2}")
        lines.append("".join(row))
    lines.append("   " + "".join(f"{i:2}"[-1] for i in range(size)))
    return "\n".join(lines)


def _cell_char(gs, x, y, pid, fogs) -> str:
    """单格渲染字符"""
    size = gs.size
    # 迷雾检查
    if fogs:
        from prototype.fow import Visibility
        vis = fogs[pid][y][x]
        if vis == Visibility.UNKNOWN:
            return " "
        if vis == Visibility.EXPLORED:
            # 显示地形但不显示单位
            t = gs.grid[y][x]["terrain"]
            return TERRAIN_CHAR.get(t, "?")
    # VISIBLE 或无迷雾 → 全部渲染
    # 优先级：单位 > 城市 > 设施 > 地形
    for u in gs.units:
        if u.alive and u.x == x and u.y == y:
            return _unit_char(u)
    t = gs.grid[y][x]["terrain"]
    if t == Terrain.CITY:
        # 找城市所属
        for c in gs.cities:
            if c.x == x and c.y == y:
                return str(c.player_id)
    # 设施
    f = gs.grid[y][x].get("facility")
    if f:
        return {"farm": "f", "lumbermill": "l", "mine": "m"}.get(f.facility_type, "?")
    return TERRAIN_CHAR.get(t, "?")


_UNIT_CHAR_MAP = {
    "infantry": "I", "cavalry": "C", "archer": "A",
    "scout": "S", "worker": "W",
}


def _unit_char(u) -> str:
    c = _UNIT_CHAR_MAP.get(u.unit_type, "?")
    return c.upper() if u.player_id == 0 else c.lower()


def render_status(gs, pid: int) -> str:
    """渲染信息面板"""
    econ = gs.economies[pid]
    tech = gs.techs[pid]
    opp = 1 - pid
    opp_econ = gs.economies[opp]
    opp_tech = gs.techs[opp]

    my_units = [u for u in gs.units if u.player_id == pid and u.alive]
    opp_units = [u for u in gs.units if u.player_id == opp and u.alive]

    lines = [
        f"=== 回合 {gs.turn}/{100} | P{pid} 视角 ===",
        f"资源: 粮{econ.food} 木{econ.wood} 金{econ.gold}",
        f"城市 HP: {gs.cities[pid].hp}",
        f"科技: {len(tech.completed)}完成 | "
        f"研究中: {tech.researching or '无'} "
        f"({tech.research_ticks}/{_get_tech_ticks(tech.researching) if tech.researching else 0})",
        f"建设项目: {tech.construction_count()}/5",
        f"",
        f"我方单位({len(my_units)}): {', '.join(f'{_unit_char(u)}@{u.x},{u.y}({u.hp}hp)' for u in my_units)}",
        f"",
        f"敌方情报: {opp_econ.food}粮 {opp_econ.wood}木 {opp_econ.gold}金 | "
        f"科技:{len(opp_tech.completed)} 建设:{opp_tech.construction_count()}/5",
        f"敌方单位({len(opp_units)}): {', '.join(f'{_unit_char(u)}@{u.x},{u.y}' for u in opp_units)}",
    ]
    if gs.winner is not None:
        lines.append(f"\n>>> P{gs.winner} 获胜! ({gs.victory_type})")
    return "\n".join(lines)


def _get_tech_ticks(tech_id):
    if tech_id is None:
        return 0
    from prototype.constants import TECH_TREE
    return TECH_TREE.get(tech_id, {}).get("turns", 1)
