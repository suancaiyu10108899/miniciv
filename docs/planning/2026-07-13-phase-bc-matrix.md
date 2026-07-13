# P1.5 收尾: BC蒸馏(自对弈数据) + 2v2 + 最终矩阵

> 2026-07-13 | 第六个AI | 执行中

## Phase B: BC自对弈数据采集
- FlatMC d32(教师) vs FlatMC d24(对手)
- 300局自对弈(1000局太长, 300局≈3万条数据)
- 每回合记录25维特征+6个决策标签
- 输出: bc-selfplay-data.csv

## Phase C: BC训练+打表
- 6个softmax分类器, 200 epochs
- 打表: BC vs Builder/AlwaysWhite/StateAware/Evo/FlatMC d24(200 seeds each)
- 输出: bc-weights.json + bc-eval.csv

## Phase D: 2v2矩阵
- team-eval (C1参数已更新)
- 14阵容 × 150 seeds

## Phase E: 最终最强矩阵(500 seeds)
- FlatMC(d24) × BC × Evo × StateAware × AlwaysWhite × Builder × Adaptive
- 7×7 full matrix
- 输出: final-matrix-500s.json

## 时间
B(~30min) + C(~10min) + D(~10min) + E(~15min) ≈ 65min
