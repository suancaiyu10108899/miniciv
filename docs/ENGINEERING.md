# 工程状态 + 数据标准

> 2026-07-05 | 当前工程基础设施的真实状态（不是计划）。
> 合并自：INFRASTRUCTURE.md + DATA-MANAGEMENT.md + EXPERIMENT-FORMAT.md

---

## 一、安全与进程

| 项 | 状态 | 备注 |
|----|------|------|
| API key 防泄露 | ✅ | check_leaks.py + .git/hooks/pre-commit 已绑定 |
| 孤儿进程清理 | ✅ | prototype/cleanup.py atexit 注册；eval/eval_matrix/train_evo 已导入 |
| 磁盘空间管理 | ⚠️ | 当前 ~6MB experiments/，安全。无自动清理脚本。 |
| .env 不入 git | ✅ | .gitignore 包含 .env |

**已知缺口**：无自动清理旧实验数据的脚本（`cleanup_experiments.py` 不存在）。

## 二、测试

| 项 | 状态 | 备注 |
|----|------|------|
| 单元测试 | ✅ | 86 tests, 0.17s, 覆盖 combat/mapgen/movement/terrain/unit |
| 未测试模块 | ⚠️ | game/ economy/ tech/ snapshot/ eval/ 全部 9 个 AI 模块 — 零测试 |
| 集成测试标准 | ✅ | `docs/INTEGRATION-TESTS.md` 已定义 |
| check_docs.py | ✅ | 检测 constants.py ↔ GAME.md 一致性（已补全至 8 个值） |

## 三、实验与数据

### 数据目录
```
experiments/v0.4.0/  — ~45,000 games（早期探索）
experiments/v0.5.0/  — ~50,000 games（系统评估）
experiments/v0.6.0/  — facility scan + stacking fix
experiments/v0.6.1/  — Evo convergence + city params
experiments/v0.6.2/  — correlation analysis
experiments/v0.6.3/  — construction first >30%
experiments/v0.7.0-grid-final/ — 方格终版矩阵 (10,000 games)
experiments/v0.7.0-hex-baseline/ — 六边形基线矩阵 (900 games)
eval_final/          — 4×4 核心矩阵 (16,000 games)
```

### 实验格式标准
- 每个实验目录包含：`config.json`（参数+重现命令）+ `results.json`（原始数据）
- 评估使用 paired 设计（每 seed 正反各打一局，消除 P0 偏差）
- `eval_matrix.py` 输出 per-unit-type（alive/dead/damage_dealt/damage_taken）+ per-victory-type 数据

### 已知缺口
- 无数据保留/清理规则（哪些保留、哪些可删）
- 无 `reproduce.py`（给定 config.json 重现实验）
- 无三级数据标准（L1 摘要 / L2 指标 / L3 回放）的强制执行
- 实验数据散落在 JSON 文件中，无 SQLite 索引

## 四、文档体系

| 项 | 状态 |
|----|------|
| Session 日志 (07-01→07-05) | ✅ 完整 |
| CC Memory (07-01→07-03) | ⚠️ 缺 07-04/07-05 |
| 活跃文档日期戳同步 | ✅ 已修复（本次 audit） |
| GAME.md ↔ constants.py 一致性 | ✅ check_docs 已补全 |
| BUGS.md | ❌ 空模板（零条记录） |

## 五、Agent 协作

| 项 | 状态 |
|----|------|
| 5/5 子 Agent 验证 | ✅ 成功（探索阶段） |
| Coordinator 系统 | ❌ 未落地（只有 15 行 README + 07-02 的 inbox） |
| 规划执行纪律 | ⚠️ 已定义但曾违规（WORKFLOW.md 记录） |

**建议**：Rust 重构期间不使用并行 Agent（类型系统 + 模块耦合不适合并行）。coordinator 归档，平台化阶段再启用。

## 六、技术债务（重构前不修，Rust 后再说）

1. **hex Greedy AI 距离计算**：机械翻译自方格版，移动启发式在六边环面上不工作（距离梯度太浅，地形权重过高）
2. **FlatMC 未适配六边**：需改为 hex 距离 + hex Greedy 委托
3. **FOW 未执行**：代码存在但所有 AI 使用全信息
4. **测试覆盖率 13.5%**：核心循环无测试
5. **DQN 生产决策不经 NN**：结构性问题，需动作空间重新设计
6. **BC 完整 AI 未完成**：只有预测器（91.7% acc），per-turn 行为克隆数据格式不匹配
7. **回放浏览器不支持六边**：`replay_viewer.html` 是方格专用
8. **check_docs.py 3 个 warning**：DEFAULT_SIZE/CITY_BASE_FOOD/CAVALRY_CHARGE_BONUS 的 GAME.md 正则需更新

---

*替代：INFRASTRUCTURE.md、DATA-MANAGEMENT.md、EXPERIMENT-FORMAT.md（内容已合并）*
