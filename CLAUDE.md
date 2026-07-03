# CLAUDE.md — miniciv

## 当前阶段

**Python 原型收尾中 — 核心修复（facility=8）已写代码，待验证。**

> ⚠️ "收尾完成"的表述已修正。代码就绪，但最重要的验证数据还没跑。
> 详细 → `docs/planning/2026-07-03-wrapup.md`

## 当前任务（优先级排序）

1. **facility=8 验证** — 跑 2,400 局矩阵，确认建设胜利在新规则下是否平衡（阻塞项）
2. **文档不一致修复** — DEFAULT_SIZE、GAME.md 同步、AI-AUDIT 时效标注
3. **实验目录清理** — 删除 tmp/test 调试残留
4. **人类可玩性测试** — 自己玩 5 局，记录体验
5. **根据数据决定下一步** — 参数锁定 → Rust 设计，或原型第二轮

## 上次做到哪了

- **代码写完**：全矩阵 36,000 局 + C5 成本扫描 + 设施前置条件修复
- **建设胜利代码已改**：C5 研究需先建 8 个设施（`CONSTRUCTION_VICTORY_REQUIRE_FACILITIES=8`）
- ⚠️ **但未验证**：全矩阵数据全部来自修复前规则。新规则下 AI 排名完全未知
- **API Key 泄露已处理**：旧 key 删除，新增 `.env.example` + gitignore
- **eval_matrix 增强**：经济指标、checkpoint、种子确定性、30 workers
- 详细 → `docs/sessions/2026-07-03.md`
- 收尾规划 → `docs/planning/2026-07-03-wrapup.md`
- 长期规划 → `docs/planning/2026-07-03.md`
- Rust 架构草稿 → `docs/rust-architecture.md`（早期草稿，待收尾后重写）
- **长远愿景** → `docs/VISION.md`（新建，项目"宪法"）

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：Random vs Random P0 ≤ 55%（当前 49.2% ✅）
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL，宁缺毋滥
- **API key 不进 git 追踪文件**（教训：泄露 300M tokens）

## Agent 协作速查

| 角色 | 模型 | CC alias | 用于 |
|------|------|----------|------|
| 主 Agent | DeepSeek V4 Pro | `opus`（默认） | 设计、决策、审核、写文档、跑中小规模实验 |
| 子 Agent | DeepSeek V4 Flash | `haiku` | 改代码+验证、简单数据分析 |

- 长实验脚本：主 Agent 写 → 用户手动跑 或 主 Agent 后台跑
- 子 Agent 代码改动：文件隔离，结构化 JSON 输出
- 开发过程中随时 commit + push

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| 长远愿景 | `docs/VISION.md`（项目"宪法"，每个设计决策的最终依据） |
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| 收尾评估与规划 | `docs/planning/2026-07-03-wrapup.md` |
| AI 评估协议 | `docs/AI-EVAL.md` |
| 各 AI 状态 | `docs/AI-AUDIT.md` |
| Session 日志 | `docs/sessions/` |
| 下一步规划 | `docs/planning/2026-07-03.md` |
| 实验数据 | `experiments/` |
| 文档地图 | `docs/INDEX.md` |
| 原始 GDD | `docs/design/`（已冻结） |
| Rust 架构草稿 | `docs/rust-architecture.md` |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
