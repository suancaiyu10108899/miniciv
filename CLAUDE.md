# CLAUDE.md — miniciv

## 当前阶段

**v0.7.0-dev — 方格终版完成，六边形原型就绪，等决策后重构。**

> 方格终版矩阵：建设 31.5%，征服 24.1%，决定性 55.7%，P0=49.7%。
> 六边形引擎可用（mapgen+movement+game+Greedy），hex_viewer.html 可评估。
> 最后决策：方格 vs 六边形 → Rust 重构。
> 完整路线 → `docs/planning/2026-07-05-pre-rebuild-roadmap.md`

## 当前任务

1. **你评估六边形** — `hex_viewer.html`（环面 15×15），`hex_prototype.py`（终端双人对战）
2. **方格 vs 六边决策** — 基于评估 + 对比数据
3. **文档/体系收尾** — 集成测试标准，回放 schema，训练记录
4. **Rust 重构** — 坐标系选定后开工

## 上次做到哪了

- **方格终版 v0.7.0**：5AI 矩阵 10,000 games，建设 31.5%, 征服 24.1%, 决定性 55.7%
- **六边形引擎**：`prototype_hex/` — mapgen_hex + movement_hex + game_hex + ai_greedy_hex
- **六边形首次数据**：Greedy mirror 建设 66.7%（vs 方格 25%——六边设施更密）
- **AI 全部重训**：Evo #3 (89.8%, 骑兵 41%), DQN #2 (73.0%, 纯步兵), BC 预测器 91.7%
- **兵种转型**：Greedy 从纯步兵→骑 2.4+弓 2.9；弓手从 0→4.4/game
- **子 Agent 验证**：Agent D(弓手)/E(骑兵)/G(六边原型)/H(相关性)/I(战术分析) 全成功
- **数据基础设施**：per-unit-type + damage_dealt/taken + facility类型 + per-victory-type P0
- 详细 → `docs/sessions/2026-07-05.md`（待更新）
- 规划 → `docs/planning/2026-07-05-pre-rebuild-roadmap.md`

## 关键约束

- 语言：Rust（核心引擎）+ Python（原型/AI 训练）
- AI 友好 > 人类好玩
- 先手平衡目标：P0 ≤ 55%（当前 49.7% ✅）
- 每局评估必须 paired 设计（P0+P1 各执先手一次）
- 不设 DDL
- **API key 不进 git 追踪文件**
- **单位堆叠限制**：每格 1 战斗 + 1 平民

## Agent 协作速查

| 角色 | 模型 | CC alias | 用于 |
|------|------|----------|------|
| 主 Agent | DeepSeek V4 Pro | `opus`（默认） | 设计、决策、审核、核心代码、跑中小规模实验 |
| 子 Agent | DeepSeek V4 Flash | `haiku` | 需求明确的独立任务（UI/文档/格式化/机械翻译），结构化 JSON 输出 |

- 子 Agent 适用于：需求明确、技术简单、工作量大、不碰核心游戏逻辑
- 核心游戏逻辑必须主 Agent 自己做
- 子 Agent 产出需人类验收
- **规划落定后必须按规划执行**（WORKFLOW.md §四 规划执行纪律）
- 开发过程中随时 commit + push

## 快速导航

| 找什么 | 去哪 |
|--------|------|
| 长远愿景 | `docs/VISION.md`（项目"宪法"） |
| 设计三原则 | `docs/DESIGN-PRINCIPLES.md` |
| 数据管理规划 | `docs/DATA-MANAGEMENT.md` |
| 实验格式标准 | `docs/EXPERIMENT-FORMAT.md` |
| 游戏分析维度 | `docs/ANALYSIS-DIMENSIONS.md` |
| 当前游戏参数 | `docs/GAME.md` |
| 设计决策 | `docs/DECISIONS.md` |
| 开发纪律 | `docs/WORKFLOW.md` |
| 基础设施 | `docs/INFRASTRUCTURE.md` |
| UI 开发计划 | `docs/UI-PLAN.md` |
| AI 评估协议 | `docs/AI-EVAL.md` |
| 各 AI 状态 | `docs/AI-AUDIT.md` |
| Session 日志 | `docs/sessions/` |
| Bug/Insight | `docs/journal/` |
| 实验数据 | `experiments/` |
| 回放数据 | `experiments/.../replays/_index.json` |
| 六边形引擎 | `prototype_hex/` |
| 六边形评估 | `hex_viewer.html` / `hex_prototype.py` |
| 文档地图 | `docs/INDEX.md` |
| 重构路线图 | `docs/planning/2026-07-05-pre-rebuild-roadmap.md` |
| 原始 GDD | `docs/design/`（已冻结） |
| Rust 架构草稿 | `docs/rust-architecture.md` |
| 旧项目参考 | `docs/reference/old-project-index.md` |

## CC Memory

`C:\Users\tb137\.claude\projects\D--Dev-miniciv\memory\`
