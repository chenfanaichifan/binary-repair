# 转发 — Gate 3 签名顺序（2026-10-22）

**接收方：** M4（gate3-record 维护者）/ M3（VMer 证据回传）/ M5（build/hash 复放）
**发送方：** Lead
**日期：** 2026-10-22

## 消息正文

签名顺序按 handoff 19 §5 和 gate3-record §9：

1. **M4 verifier 行**：只在 items 3–6 有实际证据并全部 `PASS` 后填写。M4 的签名只覆盖
   verifier 行，不是批准，也不是 gate pass。
2. **M5 build/hash replay 行**：记录实际复放值——candidate `c4a159…aa82`、contract
   canonical `24bfe568…4e37`、重算的 bundle `SHA256SUMS` 与 bundle hash；不匹配则退回
   `NOT VERIFIED`，不修改 candidate。
3. **Lead approval 行**：最后填写，作为 gate 决定。

Lead 批准前，gate3-record 保持 **DRAFT**、签名栏空白。

## 唯一权威 draft

```text
docs/route-a/gate3-record.md
origin/member-4-verification @ 2ecab3d
SHA-256 bddccbfee70733223a43bed0d0420c1ec130cb6fa07338c402a8355cc6a9e081
```

`delivery/gate3-record-draft.md` 内容相同（同 hash）。请用它覆盖本地 draft，不要保留两份；
如需合并差异，请给出针对该 SHA-256 的 diff。

## 六项状态

保持：1 PASS、2 PASS、3–6 `NOT VERIFIED`；结论 **CONDITIONALLY FEASIBLE**。

## 下一步

- VMer 在 `gate3-harness-v2` 还原后跑六例 + LIEF/NX/RELRO/canary diff + 隔离原始输出 +
  正式 bundle；
- M5 做 build/hash 复放；
- 两项齐后 M4 才能填 3–6 状态与 verifier 签名，Lead 最后批准。

## 发送前已核对（Lead 侧，非本 checkout）

- 本地 HEAD = `2ecab3d`；
- `docs/route-a/gate3-record.md` 与 `delivery/gate3-record-draft.md` 的 SHA-256 均为
  `bddccbfe…a9e081`；
- `docs/route-a/SHA256SUMS` 中该文件条目一致；
- gate3-record §9 签名表三行均为空白（DRAFT）。
