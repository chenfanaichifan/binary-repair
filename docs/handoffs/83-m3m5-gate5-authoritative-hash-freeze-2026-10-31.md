# 83 — M3/VMer Gate 5 权威 hash 定格声明（对齐 Lead split-chain 裁定）

**From:** M3 (producer) / M5 (adapter)
**To:** M1, M4, Lead
**Date:** 2026-10-31 23:24 (Asia/Hong_Kong)
**Scope:** 对 Gate 5 Route B 的 probe / successor 二进制做**权威 hash 定格**，消除
`e635d646` vs `05d9a2cd`、`90af91ef` vs `0066973d` 的歧义，并显式对齐 Lead 的
split-chain 裁定（`docs/handoffs/82-lead-successor-split-chain-and-rehash`）。

---

## 1. 权威版本裁定（终局）

**Route B 权威版本：probe `05d9a2cd…edb82`，successor `0066973d…9eee`。**
`e635d646` 与 `90af91ef` **不是** Route B 的权威值，无需据此重出包。

| 对象 | 非权威值（已废弃/分链） | **权威值** | 处置 |
|---|---|---|---|
| Route B probe | `e635d646…`（R4 regex bug） | **`05d9a2cd…edb82`** | commit `5023021` 已修复并钉死 |
| Route B successor | `90af91ef…ff20`（仅 Route A 模式） | **`0066973d…9eee`** | 重编译加入 `m4-gate5b` 模式 |
| Route B candidate | — | **`208574ab…6717`** | 不变 |
| Route B original | — | **`aa428157…8393`** | 不变 |
| Route A probe | — | **`f39a0302…d146cb`** | 不变 |
| Route A successor | — | **`90af91ef…ff20`** | 保留，分链绑定 Route A |

## 2. 版本演变链（为何 05d9a2cd 正确）

1. `7aed746`：successor 源码首次加入 Route B 支持，钉死 Route B probe blob
   `e635d646…`（当时 `.tmp/integration/scripts/m4_gate5b_probe.py` 的 hash）。
2. `5023021`：修复 `m4_gate5b_probe.py` 的 R4 gdb `x/2i` redirect regex（旧正则
   无法匹配 `=> 0x4012b0 <sym>:\tjmp 0x<target>` 格式），probe hash 由
   `e635d646…` → **`05d9a2cd…`**，同步更新 `jobwrap_gate5.c` 的
   `PROBE_B_SHA256_HEX` 与 `build-recipe.md`，并把 probe 脚本纳入 git（此前在
   gitignored `.tmp/` 里，M5 无法 checkout 验证）。
3. `be11c5c`：M3/VMer 在 guest 内用修复后的 probe 重编 successor，得到
   `0066973d…`，跑完 Route B placement probe（16 PASS），交付证据。

**结论**：`e635d646` 是「被修复的中间态」，`05d9a2cd` 才是「修复后的终态」。任何
以 `e635d646` 为依据的要求都应指向 `05d9a2cd`。

## 3. successor 二进制变更（90af91ef → 0066973d）

Route B 需要独立的 M4 placement probe 模式（`m4-gate5b`），而 Route A 版
successor `90af91ef` 只含 `m4-gate5`。因此 successor **重编译一次**：

- 新增 `m4-gate5b` 模式 + 钉死 Route B probe blob `05d9a2cd…`。
- **Route A 的 `m4-gate5` probe blob `f39a0302…` 与隔离语义完全不变**。
- 得到新 binary `0066973d…9eee`（`gcc -O2 -Wall -Wextra -Werror -static`，
  Ubuntu 24.04 / gcc 13.3.0）。

## 4. 对齐 Lead split-chain 裁定（82 号）

Lead 已裁定 **split-chain binding 被接受**：

- **Route A 证据仍绑定 `90af91ef…ff20` + `f39a0302…d146cb`**，不重跑。
- **Route B 证据绑定 `0066973d…9eee` + `05d9a2cd…edb82`**。
- 本次提交**不需要** Route A 在 `0066973d` 下重跑（记为已知限制，非 blocker）。

M3/VMer 交付物与 Lead 裁定**完全一致**：

```
probe 实体       05d9a2cd…edb82  == Lead 82 §1 ✅
successor 实体   0066973d…9eee   == Lead 82 §1 ✅
candidate 实体   208574ab…6717   == Lead 82 §1 ✅
Route B manifest 0eafc14b…7d19   == Lead 82 §1（root 43/43）✅
```

## 5. 三方一致性证明（本机实测）

- git HEAD 源码 `PROBE_B_SHA256_HEX` = `05d9a2cd…edb82`
- 交付 probe 实体 `routeb-successor/m4_gate5b_probe.py` = `05d9a2cd…edb82`
- 交付 successor 二进制内钉死值 = `05d9a2cd…edb82`（`grep -a` 命中，无 `e635d646`）
- 交付 successor 源码钉死值 = `05d9a2cd…edb82`

四方（源码 / 脚本实体 / 二进制 / build-recipe）对 Route B probe 的钉死值全部一致。

## 6. 给 M1 的落点提示

- 权威 freeze 记录在 lead 分支（`80` Route B PASS、`81` full MVP、`82` split-chain），
  尚未合并进 main；合并 + final tag 是 M1 职责。
- 本分支（`member-3-route-a`）交付物即权威证据，**无需重出包**。
- 若未来有需求要求「单一二进制绑定全部 Gate 5 证据」，需在 `0066973d` 下重跑一次
  Route A；当前 MVP 验收不需要。
