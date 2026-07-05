# 重构前完整审计 + 执行规划

> 2026-07-05 | 基于全项目逐项审计。本对话第二个 AI 助手接手。
> 每一项有：当前状态、为什么重要、验收标准、对 Rust 重构的意义。

---

## 审计发现摘要

### 严重（已修复）
- [ ] **GAME.md 内部不一致**：头部注释 HP=80/DEF=5/DMG=5 正确，正文表格仍是旧值 100/10/10
- [ ] **check_docs.py 检测盲区**：只检查 3 个值，漏检 CITY_HP/CITY_DEF/CITY_DAMAGE，导致报告假阴性
- [ ] **DECISIONS.md 过时**：坐标系仍标记 OPEN，元数据日期 07-02，缺六边决策记录

### 中等
- [ ] **六边形验证深度不足**：只有 Greedy 冒烟 30 局，无矩阵数据
- [ ] **snapshot.py 不支持六边**：回放浏览器无法加载 hex 对局
- [ ] **测试覆盖率 13.5%**：37 个模块仅 5 个有测试
- [ ] **INFRASTRUCTURE.md 56 条 0 勾选**：多条实际已完成但未标记
- [ ] **CC Memory 缺 07-04/07-05 session**
- [ ] **BUGS.md 空模板**：零条 bug 记录
- [ ] **INDEX.md 重复段落 + 过时日期**
- [ ] **元数据腐烂**：6 处"最后更新"日期不准确

### 低/已确认正确
- [x] 86 tests pass in 0.17s
- [x] 9 AI modules all importable
- [x] check_leaks.py + pre-commit hook working
- [x] cleanup.py atexit working
- [x] eval_matrix.py exports per-unit-type + per-victory-type data
- [x] Session logs complete for 07-01 through 07-05

---

## 执行层级

### 层级 0：真相源修复（硬阻塞）

| # | 任务 | 验收标准 |
|---|------|---------|
| 0.1 | GAME.md 完整同步 + 新增六边章节 | `grep "HP.*100" docs/GAME.md` 在表格中返回 0；check_docs 通过 |
| 0.2 | check_docs.py 补全检测项 | 修复前报错，修复后通过 |
| 0.3 | DECISIONS.md 状态刷新 + 追加密决策 #17 | 坐标系条目已确认，无过时 OPEN 条目 |

### 层级 1：六边形验证补齐（硬阻塞）

| # | 任务 | 验收标准 |
|---|------|---------|
| 1.1 | 六边形最小矩阵（3 AI × 3 对 × 50 seeds = 900 games） | P0 < 55%；建设率/征服率/阶梯率有具体数值 |
| 1.2 | snapshot.py 支持六边 | 回放浏览器能加载 hex 对局 |
| 1.3 | FlatMC 六边深度扫描（depth 5/10/15） | 有 depth-vs-winrate 曲线 |

### 层级 2：开发体系修补（强建议）

| # | 任务 | 验收标准 |
|---|------|---------|
| 2.1 | 集成测试标准文档 | 每模块有具体测试用例 + 阈值 + pass/fail 条件 |
| 2.2 | 回放 JSON Schema v1.0 + 验证器 | validate_replay.py 通过现有回放，拒绝无效文件 |
| 2.3 | 文档瘦身 + INDEX 修复 | INDEX 无"待整理"列表；活跃文档日期戳 >= 07-05 |
| 2.4 | CC Memory 补齐 | Memory 覆盖 07-01 到 07-05 |

### 层级 3：Rust 架构设计（硬阻塞）

| # | 任务 | 验收标准 |
|---|------|---------|
| 3.1 | Rust 架构设计文档（42 → 300+ 行） | 覆盖 ECS/内存模型/RNG/Action trait/PyO3 API/实现顺序 |
| 3.2 | Rust 项目脚手架 | cargo build 通过（空壳） |

### 层级 4：Rust 实现（后续对话）

| # | 模块 | 验收标准 |
|---|------|---------|
| 4.1 | mapgen | 10/10 seeds 地图与 Python 完全一致 |
| 4.2 | movement | 50 测试点合法移动列表全部一致 |
| 4.3 | combat + unit | 全兵种 × 全地形组合一致 |
| 4.4 | game loop + Random AI | 10 seeds × 80 turns 逐回合 GameState 完全一致 |
| 4.5 | Greedy v6 移植 | 10 seeds × 80 turns AI 决策 100% 一致 |
| 4.6 | 集成测试矩阵 | Rust vs Python 矩阵统计不可区分 |

---

## 明确不做（留给以后）

- DQN v2 重新设计（需要重新思考动作空间）
- FlatMC Rust 优化（引擎先跑起来）
- 迷雾实际执行（AI 行为改变 > 引擎能力）
- 回放浏览器六边适配（前端，引擎稳定后）
- Evo 训练 Rust 移植（训练基础设施）
- BC 完整 AI（等参数稳定）
- 多人/API/平台化（本体没有）

---

*本文件替代：2026-07-05-complete-pre-rebuild.md（内容已合并，后者归档）*
