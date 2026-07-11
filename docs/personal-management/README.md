# miniciv ↔ 个人管理体系(dev-hub / vault)对接

> 给每个接手 miniciv 的 AI 和三个月后的你。**miniciv 内部交接(HANDOFF)是写给下一个 AI 的;
> 这份是写给 vault 的。两者不能互相替代。**

---

## 个人管理体系在哪

- **dev-hub**:`D:\Dev\dev-hub\` —— 跨项目总控(dashboard/project-index/decision-log/experiment-log)。
- 原则(它的 README):只记结论和链接,不复制项目内细节;轻量,每文档一页。
- **40-Concepts/**(新建):跨项目可复用的"概念卡"。

## 为什么需要主动同步(vault-AI 的判断)

> HANDOFF 是写给下一个 AI 的,不是写给三个月后的你和 vault 的。miniciv 内部交接做得很好,
> 但和 vault 之间的信息断层依然存在——前身 6/24-7/1 的冲刺如果不是那份收尾报告,vault 完全不知道发生了什么。

**教训**:AI 接力 + HANDOFF 只解决"AI→AI"的交接,不解决"项目→管理体系"的同步。要主动同步。

## 同步纪律(每个 miniciv 开发阶段结束时做)

**① 向 dev-hub 同步项目状态(哪怕三行)**
- 更新 `D:\Dev\dev-hub\01-project-index.md` 里 miniciv 的一行(当前阶段/健康度/下一步)。
- 关键决策 → `dev-hub\04-decision-log.md`;关键实验 → `05-experiment-log.md`。
- 阶段总结报告放本目录(`docs/personal-management/YYYY-MM-DD-*.md`),dev-hub 里只放链接。

**② 发现跨项目可复用模式 → 往 dev-hub/40-Concepts 扔一张概念卡**
- **门槛低到"发现即录"**:一句话标题 + 三个验证案例 + 一句话教训,就够了。
- 不要等"完整建模"——三行卡片胜过没有卡片。
- 例:`定义≠实现`(前身 B01 骑兵移速定义没调用 + miniciv B2/B3 move_speed/range_dist 未实现 + 嵌入式 `while(!Serial)`)。

## 本目录已有的阶段报告

| 文件 | 覆盖 |
|------|------|
| [2026-06-24-prior-ailab-closeout.md](2026-06-24-prior-ailab-closeout.md) | 前身 MiniCiv AI Lab 收尾(6/24 Day7→7/1 封存) |
| [2026-07-11-miniciv-progress.md](2026-07-11-miniciv-progress.md) | miniciv 进度(7/1 初始化→硬伤修复+三方制衡甜点) |

## 给新对话的提醒

**你不只是在给下一个 AI 干活,也在给 vault 供给。** 一个阶段做完,除了写 HANDOFF,
记得按上面纪律向 dev-hub 同步一次(三行 + 可能一张概念卡)。这是 miniciv 开发体系的一部分,不是额外负担。
