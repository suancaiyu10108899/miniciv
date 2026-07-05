# Rust 实现阶段规划 + 学习路线

> 2026-07-05 | 从"纯 AI 写代码"到"人-AI 协作学习"的转折点。
>
> 本文档替代原型阶段的快速迭代模式。核心变化：**每个 Phase 不只是写代码，
> 也是学习 Rust 语言、AI 设计、工程规范的一个单元。**
>
> 前置：安装 Rust 工具链（`rustup`）→ `cd miniciv-core && cargo build` 通过。

---

## 一、新的工作模式

### 旧模式（原型阶段）
```
AI 写代码 → AI 跑实验 → AI 写报告 → 人看结果
```
问题：人只看最终数据，不理解代码怎么产出的。适用于"快速验证假设"，不适用于"建造长期拥有的代码基"。

### 新模式（Rust 阶段）
```
AI 解释概念+设计 → 人阅读+提问 → AI 写代码（带教学注释）→ 人 review + AI 验证 → 人总结
```
每个 Phase 完成的标准从"AI 说通过了"变为"你能向别人解释这一层做了什么、为什么这样做"。

---

## 二、每个 Phase 的学习内容

### Phase 2: 地图生成（map.rs）
**Rust 学习**：
- `enum`（Terrain 的 5 种变体，带数据和不带数据的枚举）
- `Vec<T>` 和所有权（Grid 的 tiles 存储）
- `impl` 块（Grid 的方法：get、get_mut）
- 模块系统（`mod map`，`use crate::map::Grid`）
- `todo!()` 宏和渐进实现

**AI/游戏设计学习**：
- 为什么地形需要聚类放置而不是纯随机？（连通性保证）
- 环面拓扑对游戏策略的影响（没有"角落安全"）
- BFS 连通性验证的原理

### Phase 3: 移动+距离（movement.rs）
**Rust 学习**：
- 纯函数（输入 → 输出，无副作用）
- `const` 数组（HEX_DIRS）
- 数学运算和类型转换（`i32` vs `u8`）
- 单元测试（`#[cfg(test)]`）
- `rem_euclid` vs `%` 的区别

**AI/游戏设计学习**：
- 六边形轴向坐标（cube coordinates）原理
- 为什么环面上需要 9 种 wrap 变体求最短距离
- 移动规则对 AI 搜索空间的影响（分支因子 6 vs 4）

### Phase 4: 单位+战斗（combat.rs + unit.rs）
**Rust 学习**：
- `struct` 和字段可见性
- `&mut` 可变引用（战斗函数修改单位 HP）
- `derive` 宏（Clone, Debug, Serialize）
- 枚举方法（`Terrain::def_bonus(&self) -> i32`）
- 模式匹配（`match terrain { ... }`）

**AI/游戏设计学习**：
- 固定伤害公式的设计哲学（为什么不用随机？对 AI 训练有什么影响？）
- 兵种属性的"剪刀石头布"设计空间
- 伤害追踪（damage_dealt/damage_taken）对 AI 评估的意义

### Phase 5: 经济+科技（economy.rs + tech.rs）
**Rust 学习**：
- `HashMap` 和 `HashSet`（科技树的 completed 集合）
- `Option<T>`（researching: Option<String>）
- 方法的可变性（`&self` vs `&mut self`）
- 条件逻辑的 Rust 惯用写法（if let, match）
- DAG 数据结构的建模

**AI/游戏设计学习**：
- 科技树的 DAG 设计：为什么 M4 是"M2 或 M3"而不是"M2 且 M3"？
- "建设胜利"作为非零和路径对游戏策略的影响
- 工人"建 vs 采 vs 造兵"的 tradeoff 经济学

### Phase 6: 游戏循环+Random AI（game.rs + ai/random.rs）
**Rust 学习**：
- 大型 struct 的组织（GameState 包含多个子系统）
- 借用检查器的实际体验（step_game 需要 &mut GameState）
- `impl RngCore` trait 的使用
- JSON 序列化（serde）

**AI/游戏设计学习**：
- 游戏循环的交替先手机制：为什么奇数回合 P0 先？
- 三种胜利条件的判定顺序和优先级
- Random baseline 的意义：为什么需要"随机 AI"作为参照？

### Phase 7: Greedy AI 移植（ai/greedy.rs）
**Rust 学习**：
- trait 定义和实现（`Agent` trait）
- `dyn Agent` vs `impl Agent` 的区别
- 策略模式的实际应用
- 参数扫描的方法论

**AI/游戏设计学习**：
- 手写规则 AI 的架构：战略层 → 战术层 → 执行层
- 部队协调（rally point、wave readiness）的设计思想
- 对手建模的简单实现（跟踪敌方侵略性）
- **为什么同样的逻辑在方格上工作、在六边上不工作**——这是最核心的 AI 设计教训

### Phase 8: Evo AI 移植（ai/evo.rs）
**Rust 学习**：
- JSON 解析（serde_json）
- HashMap 用于参数存储
- 外部文件加载

**AI/游戏设计学习**：
- 进化算法的基本概念：种群、适应度、变异、交叉
- 15 个权重的设计空间：每个权重控制什么行为？
- 为什么权重参数化比硬编码规则更"可进化"？

### Phase 9: 集成验证（eval.rs）
**Rust 学习**：
- 批量处理和性能测量
- 多线程并行（Rayon crate 可选引入）
- 统计数据分析

**AI/游戏设计学习**：
- Paired 评估设计的原理：为什么每 seed 要正反各打一局？
- P0 偏差的来源和消除方法
- "统计不可区分" vs "完全相同"——什么时候差异是可以接受的？

---

## 三、每个 Phase 的执行模板

```
┌─ 第一步：概念讲解（AI 输出，人阅读）─────────────────
│  "这个 Phase 要做什么？涉及的 Rust 概念有哪些？
│   对应的 Python 代码在哪里？关键算法是什么？"
│  时间：10-15 分钟阅读
│
├─ 第二步：人提问 + AI 答疑
│  "我不理解的地方、我想深入了解的地方"
│  时间：灵活
│
├─ 第三步：AI 写实现代码（带教学注释）
│  "代码中标注了每个关键决策的原因、每个 Rust 惯用法的解释"
│  时间：AI 写，人跟随阅读
│
├─ 第四步：人 review + AI 验证
│  "人能解释每段代码在做什么" + AI 跑验证测试
│  时间：20-30 分钟
│
├─ 第五步：人写学习笔记（1-2 段话）
│  "这个 Phase 我学到了什么？哪个概念最有用？哪里还模糊？"
│  写入 docs/learning/phase-N.md
│
└─ 第六步：门禁通过 → 进入下一个 Phase
```

---

## 四、学习辅助结构

### docs/learning/ 目录（新增）
```
docs/learning/
  README.md           ← 学习路线总览
  rust-basics.md      ← Rust 核心概念速查（随着 Phase 推进逐步填充）
  phase-2-mapgen.md   ← 每个 Phase 的学习笔记（你写）
  phase-3-movement.md
  ...
```

### 代码中的教学注释
Rust 代码中会使用 `// NOTE: ` 前缀标注教学注释：
```rust
// NOTE: `rem_euclid` 和 Python 的 `%` 行为相同——
// 对负数也返回非负余数。例如 -1.rem_euclid(15) == 14。
// 这和 C 的 `%` 不同（C 的 `%` 可能返回负数）。
let wq = q.rem_euclid(MAP_W as i32) as usize;
```

### Python ↔ Rust 对照
每个模块实现时，AI 会展示 Python 源码和 Rust 实现的对照：
```
Python:                          Rust:
def wrap(q, r):                  pub fn wrap(q: i32, r: i32) -> (i32, i32) {
    return (q % MAP_W, r % MAP_H)    (q.rem_euclid(MAP_W as i32),
                                       r.rem_euclid(MAP_H as i32))
                                  }
```

---

## 五、学习检查点

每个 Phase 结束后，你能回答这些问题才算通过：

- [ ] 这个模块的 Rust 代码中，哪些部分是我能独立解释的？
- [ ] 对应的 Python 代码中，相同的逻辑是怎么写的？
- [ ] 这个模块解决了一个什么游戏设计问题？
- [ ] 如果这个模块有 bug，AI 对局中会出现什么现象？

---

## 六、Rust 学习资源（按需取用）

| 当你不理解... | 去读... |
|-------------|--------|
| 所有权、借用、生命周期 | Rust Book 第 4 章 + 第 10 章 |
| enum 和 match | Rust Book 第 6 章 |
| Vec、HashMap | Rust Book 第 8 章 |
| trait 和泛型 | Rust Book 第 10 章 |
| 模块系统 | Rust Book 第 7 章 |
| 测试 | Rust Book 第 11 章 |
| 错误处理 | Rust Book 第 9 章 |

> Rust Book 在线地址：https://doc.rust-lang.org/book/
> 不需要通读——用到什么查什么。跟着 Phase 推进，自然覆盖所有核心概念。

---

## 七、不要做的事（防止学习被 AI 替代）

1. **不要让 AI 解释完就直接通过**。看完解释后，尝试用自己的话向 AI 复述一遍——AI 会纠正你的理解偏差。
2. **不要跳过写学习笔记**。哪怕只写 3 句话。"我以为 X，实际是 Y"这种纠正误解的笔记最有价值。
3. **不要在一个 Phase 上卡太久**。如果某个 Rust 概念实在理解不了，标记下来，先继续——后面的 Phase 会用不同的方式再次接触同一个概念。
4. **不要追求"完全理解每行代码"**。理解核心逻辑和数据流即可。Rust 的 borrow checker 细节可以在后续维护中逐渐熟悉。

---

*本文件是 live document——随着 Phase 推进，学习笔记链接会逐步添加。*
