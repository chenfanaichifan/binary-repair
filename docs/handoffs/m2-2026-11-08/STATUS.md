# M2 状态（2026-11-08，r2）

## 一、完成项

| 项 | 状态 | 提交 |
|---|---|---|
| T7.4 agent shell | 完成 | 早前 |
| T7.5 guided inputs | 完成 | 早前 |
| T7.6 结果屏 5.1/5.2 | 完成 | `dc7a012` |
| T7.6 顶层 obligations 兼容 | 完成 | `c6f2035` |
| T7.8 `/agent` job id 校验 | 完成 | `fb5ace1` |
| attempts + scope/bounded 渲染 | 完成 | `2853f8d` |
| T8.4 assistant 模式 UI | 完成 | `3db4719` + `102d0fb` |
| Review 12 scope/bounded UI | 完成 | `16b2a42` |
| comparison 状态 UI（179 契约） | 完成 | `34d054c` |
| 复核 M1 上传/下载 UI（56e11ca） | 完成 | 本包 `REVIEW-UPLOAD-UI.md` |

## 二、提交链（相对 `4f512f5`，共 8 个）

```text
dc7a012  fix(agent): flag missing evidence and never render blank cells or dead links
fb5ace1  fix(agent): do not redirect a legacy job link that is not an id
c6f2035  feat(agent): accept top-level obligations when routes omit them
2853f8d  feat(agent): render the attempts timeline and scope/bounded as read-only facts
3db4719  feat(agent): label the plan mode as scripted v1 and keep the raw mode visible
102d0fb  docs(agent): record the T8.4 mode badge and metadata behaviour
16b2a42  feat(agent): always render scope/bounded as unknown when the job omits them (Review 12)
34d054c  feat(agent): show comparison status from the API and never infer a pass
```

合并状态（L1 核验，交付分支 `7beb6e3`）：

```text
8/8 均为 7beb6e3 的祖先（git merge-base --is-ancestor 逐个 rc=0）
```

## 三、测试（实测口径）

```text
tests/test_agent_console.py      54
tests/test_agent_honesty.py       9
tests/test_assistant_llm.py      59
tests/test_assistant_tools.py    10
-----------------------------------
合计                            132 passed, 0 failed, 0 skipped
```

环境：交付分支 `7beb6e3`，项目 venv（pydantic 2.x），Windows，2026-11-08。

运行：

```bash
bash run-m2-tests.sh /path/to/repo
```

脚本要求 `pydantic >= 2`，不会回退到系统 Anaconda 的 1.x。
若使用其他解释器：`M2_PYTHON=/path/to/python bash run-m2-tests.sh /path/to/repo`。

> 口径说明：
> - 早期 `62 passed` 只统计前两个文件；
> - 合并提交 `2501120` 上实测 131（console 53）；
> - 交付分支 `7beb6e3` 上实测 132（console 54），多出的 1 个来自
>   `56e11ca` 新增的 `test_deliverable_upload_controls_exist`。

## 四、已被外部确认的事实

```text
V5 字节核验        16/16（HOST）、8/8（内层）、65/65（顶层）
交付分支 head      7beb6e3（freeze c40b694；b6d110b、5f8efa0d 均过时）
P1 job             9247357c54714546a7ff84891f7766f8
verdict            success_within_scope
Review 9-11        PASS（按交付文件）
VMer record 88     NOT AVAILABLE
```

## 五、口径红线

1. `scope` / `bounded` 缺失一律 `unknown`，任何情况不显示通过；
2. `comparison.status=not_provided` 一律不可用，不猜字段名；
3. `exit_code=null` 显示「未知退出码」，不补 0；
4. `mode=deterministic` 显示「脚本 v1（deterministic）」，原始值保留；
5. 回退横幅必须写「不代表模型输出」；
6. Review 12 的 PASS 只表示 UI 如实表达缺失，不代表 scope 已满足；
7. 上传的修复产物 role 为 `operator_deliverable`，只可下载，**不参与验收**，
   不产生 obligation，不改变 verdict。

## 六、依据文件

- `delivery/p1-real-window-2026-11-07/api/attempts.json`
- `delivery/p1-real-window-2026-11-07/api/route-a-evidence.json`
- `delivery/p1-real-window-2026-11-07/api/route-b-evidence.json`
- `delivery/p1-real-window-2026-11-07/controller/snapshot.json`
- `docs/handoffs/179-m2-all-inputs-handoff-2026-11-07.md`
- `docs/handoffs/183-repaired-elf-upload-2026-11-08.md`
- `docs/reviews/review-9-12-*.md`

## 七、r2 修订记录

```text
M2-1  MANIFEST.sha256 由 CRLF 改为 LF；包内文本文件统一 LF
M2-2  run-m2-tests.sh 增加 pydantic >= 2 探测与 M2_PYTHON 覆盖
M2-3  测试数字由 62 更正为 132（按文件拆分）
M2-4  新增 REVIEW-UPLOAD-UI.md
```
