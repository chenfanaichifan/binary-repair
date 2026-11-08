# 评审响应（a856afe）· M2 / GUI 部分

来源：`Improve.md` 外部评审，2026-11-05。
本文件只记录 **M2（GUI）** 负责的两项，以及需要转达给其他成员的事项。

---

## 评审给 GUI 的任务

| 项 | 评审原文要点 | 我的完成证据 |
|---|---|---|
| 2 — GUI | Repair session handling; distinguish round-trip, tests and symbolic evidence | 访问检查通过；每条结果标出实际证据域 |
| 2 — GUI | Access checks pass | 未认证页面不再泄露 session token；新增回归测试 |

---

## 1. 访问边界：未认证页面泄露 session token（已修）

评审复现方式：GUI 未认证页面在登录链接里带上 active session token，跟随链接即可获得访问。

**确认属实**：`app/main.py` 的 `_auth_required_page()` 曾把 `SESSION_TOKEN` 直接拼进
`href="/?token=..."`，并渲染成「一键登录」按钮。

**修复**：

- 401 页面不再包含任何 token，也不再出现 `?token=` 字面；
- 凭据只通过受信任的启动器传递：`start.ps1` / `open.bat` 在控制台打印一次性登录地址；
- 页面明确提示令牌保存在本机 `var/session.token`，只应复制到自己的浏览器；
- 新增 `test_unauthenticated_pages_never_embed_the_session_token`，对 `/`、`/jobs/new`、`/agent` 三个入口断言 401 且不含 token。

截图：`docs/assets/screenshots/pages/00-auth-required.png`。

**仍需 M1 处理**（不属 GUI）：controller 接受未认证的跨源 multipart 上传；Host 检查不认证调用者。
建议按评审要求给 controller 加 service 认证与来源限制，或只经已认证 GUI 暴露操作。

---

## 2. 证据域区分：每条结果说明它证明了什么（已做）

评审要求区分 round-trip、tests 与 symbolic evidence，并显示实际 scope。

**实现**：新增 `app/evidence_domains.py`，把 obligation `kind` 映射到证据域与等级：

| 证据域 | 等级 | 说明 |
|---|---|---|
| 冻结输入 Identity | 元数据 | 只核对哈希与契约版本，不执行 |
| 静态结构 Structure | 静态 | 指令边界与改动区间 |
| 接口兼容 Interface | 静态 | 调用约定、载入、ABI |
| 行为测试 Behaviour | 二进制级 | 执行冻结的有效/无效输入 |
| 符号验证 Symbolic | **模型级** | 手写 Z3 模型的证明，**不证明机器指令正确** |
| 可复现重放 Reproducibility | 重放 | 冻结哈希重放，不单独证明修复 |
| 往返行为 Round-trip | 二进制级 | 保持原始行为，**不构成修复证据** |
| 修复后行为 Repaired behaviour | 二进制级 | 唯一可计入修复的行为证据 |

证据页与 HTML 报告都新增「证据域 / Evidence domain」列，并在每行附上该域的实际范围说明；
模型级与未知类型用警示色。`repair_credit` 字段显式区分「能否算作修复证据」。

兼容性：`kind` 既可能是 `symbolic` 这样的短键，也可能是 `Bounded symbolic security` 这样的展示名，
两者都能正确归类；无法识别时显示「未分类证据 / 未知」，不做猜测。

截图：`docs/assets/screenshots/pages/13-job-evidence.png`。

---

## 3. 顺带修掉的两处诚实性问题

1. HTML 报告把 `outcome=null` 渲染成 `"not_run"`，等于替 controller 下结论；已改为
   `none (not reported by the controller)`。
2. 真实 controller 的 `evidence: not_persisted` 未透传；已加入导出与页面，空表明确写
   “an empty table is not a pass”。

---

## 4. 需要转达给其他成员（不是 GUI 能修的）

| 评审项 | 归属 | 要点 |
|---|---|---|
| 1 — 验收信任结果声明 | M1 / Integration | 验收前校验 evidence envelope：原/候选哈希、job/run/route/attempt id、contract/test-manifest/verification-scope 哈希、check type/verifier version/结果/证据文件哈希；重新哈希实际文件，拒绝跨 attempt 证据 |
| 2 — 往返检查可通过 | M4 / Verification | 两次 timeout 相同、测试集为空都能让 `gate4_pass=true`；要求非空冻结测试集 + 完成执行，timeout 视为 inconclusive |
| 3 — 往返映射成修复 | M5 / Route B | `manifest-compare.json` 通过后被映射为 V3 passing；需拆分 round-trip 与 repaired 两类义务，并合并两个 writer |
| 4 — controller 跨源上传 | M1 | 未认证跨源 multipart 上传；需 service 认证 + 来源限制；拒绝畸形 ELF |
| 5 — V4 未建立二进制级性质 | M4 | 单 ELF、函数入口窄性质，先做负控；模型级证据单独标注 |
| 6 — 可复现性 | Lead / Integration | `routeb/out/gate4/roundtrip.elf` 缺失；`var/controller` 与 `var` 启动不一致；需要 canonical 启动流程与版本化证据包 |

GUI 侧已能承载第 3 项的展示（round_trip 与 repaired_behaviour 已分开建模），
但要等 M1/M5 落盘对应 `kind` 才会出现真实行。

---

## 5. 测试

```
tests/test_security.py          5 passed   （含 token 不泄露）
tests/test_evidence_scope.py    6 passed   （证据域映射与页面渲染）
tests/test_report_sync.py      11 passed
tests/test_export_bundle.py    17 passed（合并执行）
```

未 push，提交在 `member2/agent-console`。
