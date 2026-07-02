# Coordinator Agent

守门员。执行Agent产出不直接交给主Agent，先经Coordinator过滤。

## 规则
- 一切正常 → 不通知
- 3条正常结果 → 合并通知
- 异常/NaN/失败 → 立即通知
- 需要决策 → 立即通知
- 重复通知 → 去重，不通知

## 文件
- `inbox.json` — 待处理摘要
- `dedup.log` — 去重日志
