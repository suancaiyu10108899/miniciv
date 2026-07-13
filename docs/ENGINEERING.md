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
| 单元测试 | ✅ | 103 tests (+3 ignored), 覆盖 combat/mapgen/movement/terrain/unit/config/flatmc/game(P1.5) |
| 未测试模块 | ⚠️ | game/ economy/ tech/ snapshot/ eval/ 部分 AI 模块单测薄(但 eval/flatmc 有确定性测试) |
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
experiments/v0.10-redwhite/ — P1.5全部(~120万局+164K BC样本)
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
| BUGS.md | ✅ B1-B7 已记录并全修(B6 于 S2 修复) |

## 五、Agent 协作

| 项 | 状态 |
|----|------|
| 5/5 子 Agent 验证 | ✅ 成功（探索阶段） |
| Coordinator 系统 | ❌ 未落地（只有 15 行 README + 07-02 的 inbox） |
| 规划执行纪律 | ⚠️ 已定义但曾违规（WORKFLOW.md 记录） |

**建议**：Rust 重构期间不使用并行 Agent（类型系统 + 模块耦合不适合并行）。coordinator 归档，平台化阶段再启用。

## 六、技术债务

### Python 端（预重构遗留）
1. **DQN 生产决策不经 NN**：结构性问题，需动作空间重新设计
2. **BC 完整 AI 未完成**：只有预测器（91.7% acc），per-turn 行为克隆数据格式不匹配
3. **FOW 未执行**：代码存在但所有 AI 使用全信息
4. ~~**回放浏览器不支持六边**~~：✅ 已解决 — 根目录 `replay_viewer.html` 是六边版(读 Rust GameReplay JSON, M4)。
5. **check_docs.py 3 个 warning**：正则需更新

### Rust 端（v0.8.0 新增，v0.8.1 更新）
6. **Evo 权重失效**：Python MT19937 下进化的权重在 Rust ChaCha12 上不工作（Evo vs Random 仅 8.6%）。需在 Rust 引擎上重训。
7. ~~**snapshot.rs todo!()**~~：✅ **已解决(阶段0.2)** — `snapshot_turn`+`run_replay` 落地,`bin/replay` CLI 可逐回合看一局。
8. ~~**eval.rs todo!()**~~：✅ **已解决(门禁1)** — eval.rs 落地为批量 paired 评估 + `bin/eval` CLI + 3 测试。500-seed 矩阵见 `experiments/v0.8.1-honest-eval/`。
9. ~~**tiebreak P0 偏向**~~：✅ **已修(门禁2a)** — tiebreak 随机分支原用 `gs.turn % 2`,但恒在 turn==80(偶数)触发→恒判 P0。改为 `unbiased_coin(seed)`(murmur3 双轮 + 单测)。镜像 P0:Greedy 49% / Random 53% / Evo 54%(全达标)。剩余 ~3% 是随机对局真实先手优势(Greedy 建设 P0=47.7% 证明引擎干净)。
10. ~~**存在意义级:5 回合建设速通支配**~~：✅ **已解决(2026-07-10)** — 门禁2b 发现纯建设 Builder 5T 速通 100% 通杀。修完硬伤(B1-B7 攻城/移速/射程/冲锋/遇林停)+ 甜点带(C线成本×2 + city_hp160)后,变成**建设↔军事↔防守三方制衡、有克制环(骑兵>步兵>防守>骑兵)、无单一支配、征服43/建设47均衡**。见 `experiments/v0.8.2-balance-scan/SCAN-FINDINGS.md` + `docs/BUGS.md`。
11. **待深化/待修**：B6 ✅ S2已修复(BTreeMap)、骑兵精确平衡(P1.5深度参数下CavRusher崩溃待修✅第六AI已修)、弓箭手 kiting 未充分利用、FOW 未实现(迷雾深化时做)。详见 `docs/BUGS.md`。

### Rust 端（v0.9 S2 新增）
12. **默认配置已落地为甜点**(成本×2 HP160): 消除"甜点只活在 CLI 参数"的漂移源。见 DECISIONS #19。
13. **FlatMC 裁判**(`ai/flatmc.rs` + `bin/judge`): 首个非循环深度裁判。裁决"深度温和偏浅"。P1.5深度推进中待升级分层评估。见 `experiments/v0.9-judge/S2-VERDICT.md`。
14. **性能债(✅ P1.5 Step 0 已修)**: rayon 并行 `run_pair_par`/`run_matrix_par`, `bin/eval`/`bin/judge` 默认走并行,"并行==串行"确定性测试守卫。

---

*替代：INFRASTRUCTURE.md、DATA-MANAGEMENT.md、EXPERIMENT-FORMAT.md（内容已合并）*
