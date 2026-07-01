# 环境配置备忘录

> 记录开发环境的关键配置。换了电脑或重装系统后看这个。

---

## API 认证

Claude Code 通过 DeepSeek API 运行。**只需要在 PowerShell profile 中设置：**

```powershell
$env:ANTHROPIC_AUTH_TOKEN = "sk-bc94dc839b6c4fbb9806ca3f758f721f"
$env:ANTHROPIC_BASE_URL = "https://api.deepseek.com/anthropic"
$env:ANTHROPIC_MODEL = "deepseek-v4-pro[1m]"
```

**注意**：`ANTHROPIC_API_KEY` 和 `ANTHROPIC_AUTH_TOKEN` 不能同时存在——CC 会报错不知道用哪个。已从 Windows 系统环境变量中删除了 `ANTHROPIC_API_KEY`。

配置文件位置：`C:\Users\tb137\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1`

---

## 当前硬件

| 项目 | 值 |
|---|---|
| 设备 | 联想拯救者 Y9000P 2024 |
| CPU | i9-14900HX（24 物理核 / 32 逻辑核） |
| GPU | RTX 4060 Laptop（8GB, CUDA 12.6 驱动） |
| 内存 | 32GB |

---

## 关键工具

| 工具 | 版本 | 备注 |
|---|---|---|
| Python | 3.11.9 (`D:\python-3.11.9\`) | |
| Git | 2.49 + LFS 3.6.1 + gh 2.89 | |
| Claude Code | 2.1.197 | npm 全局安装 |
| VS Code | 1.126.0 | 含 Cline 扩展 |

---

## 安装 Rust（GDD 定稿 + Python 验证通过后）

```powershell
# 下载 rustup-init.exe → 默认安装
# 验证:
rustc --version
cargo --version

# VSCode 扩展:
# rust-analyzer
```

---

## 缺失但暂不需要

| 工具 | 何时需要 |
|---|---|
| CUDA Toolkit | GPU 训练时（当前用 CPU） |
| matplotlib / pandas | 实验数据可视化时 |
| WSL | 暂无 Linux 依赖 |

---

> 完整开发工具列表：旧项目 `docs/reference/dev-tools-inventory.md`
