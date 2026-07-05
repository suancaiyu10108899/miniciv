# Rust for C++ Programmers — miniciv 专用速查

> 不需要读完再开始。Phase 2 只用前 4 个小节。其余的用到时再查。

---

## 1. 变量和类型 — 一切都反过来了

```cpp
// C++: 类型在左边
int x = 5;
const int y = 10;
vector<int> nums = {1, 2, 3};

// Rust: 名字在中间，类型在右边（用 : 分隔）
let x: i32 = 5;
let y: i32 = 10;        // 默认不可变（相当于 C++ 的 const）
let mut z: i32 = 10;     // mut = 可修改
let nums: Vec<i32> = vec![1, 2, 3];

// Rust: 类型通常可以自动推断，不需要显式写
let x = 5;               // 自动推断为 i32
let nums = vec![1, 2, 3]; // 自动推断为 Vec<i32>
```

**关键**：Rust 默认不可变。`let` ≈ `const`，`let mut` ≈ 普通变量。这和 C++ 相反。

---

## 2. 基础类型 — 大小写和位数

```
C++              Rust
int              i32       (32位有符号整数)
unsigned int     u32       (32位无符号整数)
short            i16
long long        i64
size_t           usize     (指针大小，64位机器上是 u64)
float            f32
double           f64
bool             bool
char             char      (4字节 Unicode，不是 1 字节 ASCII)
string           String    (堆分配的字符串)
                 &str      (借用的字符串切片，≈ C++ 的 string_view)
```

**不需要记**。Phase 2 只用 `i32`、`u8`、`u16`、`u64`、`bool`。

---

## 3. 函数 — 返回值和分号

```cpp
// C++
int add(int a, int b) {
    return a + b;
}

// Rust
fn add(a: i32, b: i32) -> i32 {
    a + b    // 注意：没有分号！最后一行不带分号 = return
}

// 也可以显式 return（和 C++ 一样）
fn add(a: i32, b: i32) -> i32 {
    return a + b;  // 带分号
}
```

**核心规则**：
- 最后一行不加 `;` → 这就是返回值
- 加了 `;` → 返回 `()`（空元组，相当于 `void`）
- 显式 `return` 总是可以用的

---

## 4. struct 和 impl — 数据 + 方法分离

```cpp
// C++: 数据和方法在同一个 class 里
class Unit {
public:
    int hp;
    int atk;
    
    Unit(int hp_, int atk_) : hp(hp_), atk(atk_) {}
    
    bool is_dead() const {
        return hp <= 0;
    }
};

// Rust: 数据用 struct，方法用单独的 impl 块
struct Unit {
    hp: i32,
    atk: i32,
}

impl Unit {
    // 构造函数（Rust 没有专门的构造函数，用约定俗成的 new）
    fn new(hp: i32, atk: i32) -> Self {  // Self = Unit
        Self { hp, atk }
    }
    
    // 方法：&self ≈ C++ 的 const 成员函数
    fn is_dead(&self) -> bool {
        self.hp <= 0
    }
    
    // 可变方法：&mut self ≈ C++ 的非 const 成员函数
    fn take_damage(&mut self, damage: i32) {
        self.hp -= damage;
    }
}
```

**关键**：`struct` 只管数据，`impl` 块管方法。同一个 struct 可以有多个 `impl` 块（分散在不同文件甚至不同模块都可以）。

---

## 5. enum — 带数据的枚举（C++ 没有直接对应物）

```cpp
// C++: 用 enum + union 或 std::variant
enum TerrainType { PLAIN, FOREST, MOUNTAIN, WATER, CITY };

// Rust: enum 的每个变体可以带数据
enum Terrain {
    Plain,                              // 无数据
    Mountain,                           // 无数据
    City { hp: i32 },                   // 带命名字段
}

// 使用时必须用 match（相当于加强版 switch）
fn describe(t: &Terrain) -> &str {
    match t {
        Terrain::Plain => "平原",
        Terrain::Mountain => "山地",
        Terrain::City { hp } => {
            if *hp > 50 { "坚固的城市" }
            else { "破损的城市" }
        }
    }
}
```

**match 的优势**：编译器会检查你是否覆盖了所有情况。漏了一个 variant → 编译报错。这消除了 C++ switch 最常见的 bug（忘了处理某个 case）。

---

## 6. Option — 替代 NULL

```cpp
// C++: 用 nullptr 或 std::optional
Unit* find_enemy() {
    if (no_enemy) return nullptr;
    return &enemy;
}

// Rust: 用 Option<T>。没有 null，没有 nullptr。
fn find_enemy() -> Option<&Unit> {
    if no_enemy {
        None           // ≈ nullptr
    } else {
        Some(&enemy)   // ≈ 有效值
    }
}

// 使用时必须处理两种情况
match find_enemy() {
    Some(unit) => println!("找到敌人"),
    None => println!("没有敌人"),
}

// 快捷写法（用于"有值就做某事，没有就跳过"）
if let Some(unit) = find_enemy() {
    println!("找到敌人: hp={}", unit.hp);
}
```

**这是 Rust 最常用的模式之一。** miniciv 中大量使用 `Option<T>` 来表示"可能存在也可能不存在"的东西——比如 `winner: Option<u8>`（None = 游戏还在进行）。

---

## 7. Vec 和数组

```cpp
// C++
vector<int> v = {1, 2, 3};
v.push_back(4);
int first = v[0];
size_t len = v.size();

// Rust
let mut v: Vec<i32> = vec![1, 2, 3];
v.push(4);
let first = v[0];        // 如果越界会 panic（相当于 C++ 的 at()）
let len = v.len();       // 返回 usize

// 固定大小数组（栈上分配，编译期已知大小）
let arr: [i32; 6] = [1, 2, 3, 4, 5, 6];  // 6 个 i32
let zeros = [0; 225];    // 225 个 0
```

---

## 8. 字符串 — String vs &str

```cpp
// C++
std::string s = "hello";     // 拥有字符串
std::string_view sv = s;     // 借用/查看字符串

// Rust
let s: String = String::from("hello");  // 拥有字符串（堆分配，可修改）
let sv: &str = "hello";                 // 字符串切片（借用，不可修改）

// 多数时候直接用 &str 就够了
fn greet(name: &str) {
    println!("Hello, {}", name);
}
```

---

## 9. 所有权和借用 — C++ 程序员已经懂了一半

这是 Rust 最独特的特性，但 C++ 程序员其实已经内化了核心概念。

```cpp
// C++ 11: move 语义
std::vector<int> a = {1, 2, 3};
std::vector<int> b = std::move(a);  // a 的内容被转移给 b
// a 现在是空的（或未定义状态）

// Rust: move 是默认行为
let a = vec![1, 2, 3];
let b = a;          // a 的内容被移动到 b
// println!("{:?}", a);  // 编译错误！a 已经被移走了
```

**C++ 程序员已经懂的东西**：
- RAII：资源在构造时获取，析构时释放 → Rust 的 `Drop` trait 是同一个概念
- Move 语义：C++11 引入 → Rust 默认就是 move
- const 引用：`const T&` ≈ Rust 的 `&T`
- 不要返回悬垂引用 → Rust 的 borrow checker 在编译期强制执行这个规则

**需要新学的东西**：
- **借用检查器**：编译器在编译时验证所有引用都是有效的。这不是新概念——C++ 也需要你保证这一点，但 C++ 不会在编译期检查（导致 use-after-free、dangling pointer 等运行时 bug）
- **一个可变引用 XOR 多个不可变引用**：`&mut T` 是独占的——同一时间只能有一个可变引用。这防止了 C++ 中常见的数据竞争

**如果你卡住了**：当编译报错 "cannot borrow x as mutable because it is also borrowed as immutable"——这在 Phase 6 才会大量遇到。先标记下来，AI 会解释怎么修。

---

## 10. 编译器就是你的老师

和 C++ 不同，Rust 的编译错误信息是**人类可读的**。遇到编译错误时：

1. 读错误信息（通常它已经告诉你怎么修了）
2. 如果不懂 → 问 AI
3. 不要猜——Rust 编译器几乎总是对的

例如：
```
error[E0596]: cannot borrow `v` as mutable, as it is not declared as mutable
 --> src/main.rs:3:5
  |
2 |     let v = vec![1, 2, 3];
  |         - help: consider changing this to be mutable: `mut v`
3 |     v.push(4);
  |     ^ cannot borrow as mutable
```

它直接告诉你在第 2 行加 `mut`。C++ 的模板错误通常有 200 行——Rust 的错误通常只有 5-10 行，且带建议。

---

## 11. 模块系统 — 比 C++ 的 include 简单得多

```cpp
// C++: 每个 .cpp 文件独立编译，#include 是文本复制
#include "unit.h"
#include "combat.h"

// Rust: 模块树。src/lib.rs 是根，子模块自动发现
// miniciv-core/src/lib.rs:
pub mod unit;      // 声明 src/unit.rs 为一个公开模块
pub mod combat;    // 声明 src/combat.rs 为一个公开模块

// 在任何文件中使用另一个模块的内容：
use crate::unit::Unit;      // 绝对路径（crate = 当前 crate 的根）
use crate::combat::resolve_melee;
```

**不需要 `#pragma once`、不需要 include guards、不需要前向声明。** 模块系统在编译期处理所有依赖关系。

---

## 12. Phase 2 实际用到的语法（最小子集）

你不需要全部读完以上内容才开始。Phase 2（地图生成）实际只用：

| Rust 概念 | 对应 C++ | 在 Phase 2 中的使用 |
|----------|---------|-------------------|
| `enum Terrain { Plain, Forest, ... }` | `enum TerrainType { ... }` | 5 种地形 |
| `struct Tile { terrain: Terrain, ... }` | `struct Tile { ... }` | 每个格子 |
| `struct Grid { tiles: Vec<Tile> }` | `struct Grid { vector<Tile> tiles; }` | 整个地图 |
| `impl Grid { fn get(&self, q, r) -> &Tile }` | `const Tile& Grid::get(int q, int r) const` | 环面 safe get |
| `fn generate_map(seed: u64) -> Grid` | `Grid generate_map(uint64_t seed)` | 地图生成入口 |
| `let mut v = vec![0; 225]` | `vector<int> v(225, 0)` | 初始化数组 |
| `v.push(item)` | `v.push_back(item)` | 添加元素 |
| `v.len()` | `v.size()` | 数组长度 |
| `for x in 0..15 { ... }` | `for (int x = 0; x < 15; x++)` | 循环 |
| `match terrain { ... }` | `switch (terrain) { ... }` | 分支 |

就这些。和你会的 C++ 语法相比，需要"翻译"的量很少。

---

*使用方式：Phase 2 开始前读 §1-4 和 §12。其余在需要时查阅。*
