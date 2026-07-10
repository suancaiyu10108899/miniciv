# CLAUDE.md — miniciv

## 当前阶段

**Rust 重构 Phase 9/9 完成 + 门禁1(诚实评估)落地。70 tests 通过 (+2 ignored)。**

> ⚠️ **顶层真相(2026-07-10 第三个 AI,500 seeds paired):**
> **游戏存在 5 回合建设速通支配策略。** 纯建设固定策略(Builder)5 回合合法完成 C5+设施,
> **100% 通杀 Greedy/Evo/Random**,军事/战术全是摆设,同类对决先手 90.8% 决定。
> → 北极星"AI 玩出深度"**当前不合格**:有单一支配解,非丰富博弈。裁决 → `experiments/v0.8.1-honest-eval/VERDICT.md`
> 附带修正:v0.8.0 招牌"Greedy 60.8%/7x"是拿坏 Evo 刷平均的假象(Greedy vs Random 实为 41%,反优化)。
> P0 偏差:✅ 已修(门禁2a,tiebreak murmur3)。镜像 P0 Greedy 49%/Random 53%/Evo 54%。
> **下一步:门禁 3 —— 打破建设速通(设计决策,待人拍板方向)。**

| Phase | 内容 | 状态 | 测试 | 学习笔记 |
|-------|------|------|------|---------|
| 1 | cargo 骨架 | ✅ | — | — |
| 2 | map.rs — 地图生成 | ✅ | 7 | enum/struct ≈ C++，rem_euclid 是 Python % |
| 3 | movement.rs — 移动+距离 | ✅ | 10 | hex_distance 9种wrap取最短，cube distance公式 |
| 4 | unit.rs + combat.rs — 单位+战斗 | ✅ | 21 | &mut 可变引用，split_at_mut 解决双借用 |
| 5 | economy.rs + tech.rs — 经济+科技 | ✅ | 20 | HashSet Borrow 泛型推导坑，static 数组替代 Vec |
| 6 | game.rs + ai/random.rs — 游戏循环+Random | ✅ | 4 | 首次端到端！split_at_mut 实战，所有权移动 |
| 7 | ai/greedy.rs — Greedy AI | ✅ | 4 | 600局参数扫描: TW=0.15最优, hex_distance修复是关键 |
| 8 | ai/evo.rs — Evo AI | ✅ | 3 | 权重从JSON加载, 但需Rust引擎上重训 |
| 9 | 集成验证矩阵 | ✅ | 1 | ~~Greedy 60.8%~~ 30-seed 噪声,见门禁1修正 |
| G1 | eval.rs 批量评估 (第三AI) | ✅ | 3 | 500-seed 诚实矩阵: Greedy vs Random 41.4% |

> **~~Rust 集成矩阵 (30 seeds paired)~~ — 已被 500-seed 修正,勿引用:**
> ~~Greedy 60.8% | Random 78.3%~~ 这是 30-seed 噪声 + 拿坏 Evo 刷平均。
> **诚实版 (500 seeds):Greedy vs Random 41.4% | Evo vs Random 8.6% | Greedy 镜像 P0 50.8%**
> Rust 代码: ~4,600 行, 70 tests (+2 ignored), 0 errors
> 复现: `cd miniciv-core && cargo run --release --bin eval -- 500 balanced out.json`

## 工作模式（铁律）

**每个 Phase 必须按以下流程，不可跳过任何步骤：**

1. **概念讲解**：AI 用 5-10 分钟解释这个 Phase 要做什么、涉及的 Rust 概念、对应的 Python 参照
2. **人提问**：人提出不理解的地方——AI 不准催、不准跳过
3. **AI 写代码**：带 `// NOTE:` 教学注释，中文，标注每个关键决策的原因
4. **人 review**：人需能用自己的话解释核心逻辑
5. **学习笔记**：人在 Phase 进度表里写一句话（学到了什么或哪里模糊）
6. **门禁验证**：`cargo test` 全通过后进入下一个 Phase

**Phase 完成后 AI 必须做：**
- 更新本文件 Phase 进度表（一行 + 测试数）
- 在 session 日志追加一段（5行：做了什么/决定了什么/什么问题/测试数）
- Git commit + push

**反模式（严禁）：**
- ❌ AI 连续写完多个 Phase 不等人 review
- ❌ AI 只给代码不给解释
- ❌ 连续多个 Phase 不更新进度表
- ❌ 追求速度 > 追求理解

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI训练）
- AI 友好 > 人类好玩
- 先手平衡目标：P0 ≤ 55%（当前 49.7% ✅）
- 每局评估必须 paired 设计
- 不设 DDL
- API key 不进 git 追踪文件
- 单位堆叠限制：每格 1 战斗 + 1 平民
- 坐标系：六边形（轴向坐标 + 矩形环面）

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| Phase 进度 + 当前状态 | **本文件**（唯一真相源） |
| 游戏参数（唯一真相源） | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| Rust 架构设计 | `docs/rust-architecture.md` |
| Rust 学习路线 | `docs/planning/2026-07-05-rust-implementation-plan.md` |
| 集成测试标准 | `docs/INTEGRATION-TESTS.md` |
| 工程状态+技术债务 | `docs/ENGINEERING.md` |
| 六边形 AI 基线数据 | `experiments/v0.7.0-hex-baseline/` |
| Rust 代码 | `miniciv-core/src/` |
| Python 六边引擎 | `prototype_hex/` |
| 交接文档 | `docs/HANDOFF.md` |
| Session 日志 | `docs/sessions/` |
| 学习笔记 | `docs/learning/` |
