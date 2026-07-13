# P1.5 → P2 交接文档

> 2026-07-13 | 第六个AI | P1.5已关闭, tag: v0.10-p1.5

## P1.5 做了什么

全局压缩把游戏从7-35T延寿到82.9T。红白分叉+支持度系统验证了三个核心主张：
- R-1 处境决定路线: StateAware H2H > AlwaysWhite(65%)
- R-3 频率依赖: WvR 1v1 64%→2v2 15%, 48pp逆转
- 非传递克制环: StateAware > AlwaysWhite > Builder > StateAware

## P1.5 关键发现

1. **FlatMC 对手模型过拟合**: minimax只假设Builder/Rusher/CavRusher, 深度>d40后对所有对手下降
2. **三段搜索跃升**: d2-6(盲)→d8(战术)→d12-16(战略)
3. **线性Evo天花板**: 0.867, 加特征不突破
4. **NN有潜力**: Adam+decay到0.863, 需要更好优化器
5. **BC动作分解失败**: 需要P2用整体turn-plan预测

## 当前 AI 排名 (C1甜点, 500 seeds)

| AI | 全局胜率 | 类型 |
|----|---------|------|
| FlatMC d24 | 87.8% | 搜索型 |
| Evo | 59.5% | 学习型(GA) |
| AlwaysWhite | 49.3% | 固定白线 |
| StateAware | 38.9% | 手写规则 |
| Builder | 34.5% | 纯建设 |
| Adaptive | 30.0% | 自适应 |

## P2 建议优先级

1. **更大棋盘 ≥25×25** — 突破15×15硬天花板(游戏长度/策略空间/)
2. **扩展FlatMC minimax对手集** — 修AlwaysWhite盲区
3. **NN继续训练** — V2b已到0.863, Adam+更多代可能超线性Evo
4. **BC重新设计** — 整体turn-plan预测, 非分解动作
5. **多回合建造/更多科技节点** — 增加决策深度
6. **迷雾FOW** — 信息博弈维度
7. **StateAware 2v2修复** — 需要更大棋盘后才能做

## 复现命令

```
cargo run --release --bin final-matrix  # 最新6AI矩阵
cargo run --release --bin bc-collect-self -- 1000  # BC自对弈数据
cargo run --release --bin train-evo-v2 -- 300 200 8  # NN训练
cargo run --release --bin flatmc-one -- <depth> 500  # FlatMC单深度评估
```

## 关键文件

- 甜点配置: C1 (见 CLAUDE.md 交接清单 §1)
- 完整裁决: experiments/v0.10-redwhite/VERDICT-FINAL.md
- 最终矩阵: experiments/v0.10-redwhite/final-matrix-500s.json
- FlatMC深度: experiments/v0.10-redwhite/flatmc-d{2-96}.csv
- Evo权重: experiments/v0.10-redwhite/evo-trained-weights.json (86.7%)
- BC数据: experiments/v0.10-redwhite/bc-selfplay-data.csv (164K行)
