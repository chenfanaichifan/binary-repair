# MARCX1 `marcx` 二进制修复验收记录（2026-11-14）

用户上传样本：`marcx`（ELF64 x86-64、静态链接、已 strip、713,160 B）

| 项目 | 值 |
|---|---|
| 原始 SHA-256 | `72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5` |
| 修复后 SHA-256 | `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2` |
| 修复后文件 | [`marcx-fixed`](marcx-fixed) |
| 结论 | **`success_within_scope`**（14/14 required checks 通过，含真实 Linux guest PoC/回归差分） |

---

## 1. 现象：为什么原先“修复失败”

GUI 一键修复返回“候选被扣留（未通过验收）”，14 项检查正如截图所示：`format=failed
supported=False`、`candidate.present=failed candidate_bytes=0`、`candidate.identity.patched
=failed`、`patch.scope=failed unsupported mode=unsupported`，`runtime.*` 全部 `not_run`。

这不是验收引擎误判，而是**修复能力缺口 + 验收模型不匹配**，链路如下：

1. 一键修复入口 `app/services/binary_review.py::run_direct_repair()`（第 670 行）对
   ELF x86-64 先走旧字节引擎 `app/services/binary_repair_engine.py::repair_elf()`。
2. 该引擎只识别四类形态（`app/services/binary_repair_engine.py`）：
   预审模板固定哈希（第 27 行 `KNOWN_STRICT`）、`sub rsp,N` + 立即数 `edx` 的栈读写、
   立即数 `memcpy` 长度、`strcpy/strcat` code cave。
3. `marcx` 的漏洞根因（挑战分析已确认）是：`render()` 的 `OP_SPAN` 分支把**输出缓冲区容量
   `out_size`** 的目标校验误写成**输入数据池容量 `data_size`**，而 `memcpy` 的**长度来自归档
   索引记录的运行时值**。于是：
   - 没有立即数 → 引擎四类形态全部不匹配 → `_repair_elf_immediate()` 在
     “No supported immediate-length read/write pattern found.” 处 fail-closed，
     `supported=False`、`mode="unsupported"`、`patched=None`；
   - `run_direct_repair` 再交 `app/services/binary_verification.py::build_verification()`
     （第 148 行）验收，于是 `format/candidate.*/patch.scope` 必然失败；
   - 该验收模型的运行时证据是 Unicorn 全 ELF 执行 + `stack_sentinel_intact`
     （`runtime.no_overflow`，第 337 行），而本缺陷是**堆越界 + 非恒定长度**，
     栈哨兵模型根本无从产生用例 → `runtime.* = not_run`。
4. 同类缺口此前已被记录：`app/services/repair_matrix.py` 第 186 行把
   “heap, global and non-imported inline copy sinks” 列为 non-goal；
   `artifacts/fairness-ablation-2026-11-14/` 中 `hard-nonconst` / CWE121 /
   heap-canary 三个家族确定性基线全部 0 通过。

**一句话根因**：样本属于“两近似容量变量用错一个”的内联范围校验缺陷（CWE-131/697→CWE-787），
旧引擎没有该 sink 类，验收 gate 也没有堆/非恒定长度的运行时证据模型，因此正确 fail-closed，
但**无法完成修复**。

## 2. 本次修复内容（已完成的功能）

### 2.1 新增修复引擎：重复范围校验的容量变量纠正

`app/services/repair/capacity.py`（新文件）

- `detect_capacity_confusion(data)`：在 ELF64 x86-64 `.text` 中识别内联的无符号范围校验块
  `cmp Ra,Rb; jb FAIL; mov T,Ra; sub T,Rb; cmp T,Rl; jcc`，要求
  `Rb` 来自 `[BASE+dst_disp]`、`Rl` 是内存加载的运行时长度；按
  `(函数起点, BASE, dst_disp)` 分组，同组 ≥3 个校验块，容量寄存器恰好 2 种取值且少数派只有 1 个，
  并要求该少数派寄存器在同一函数内还作为**另一个字段（源偏移）的容量**出现
  ——即证明它是“输入大小”变量而非写缓冲区容量。
- `repair_capacity_confusion(data)`：对少数派块做**等长原地重写**（无 code cave、无段表修改）：

  ```
  mov T, GOOD_CAP        ; 用兄弟分支一致的容量寄存器（out_size）
  sub T, dst             ; CF 等价于被删除的 cmp GOOD_CAP, dst（无符号下溢安全）
  jb  FAIL
  cmp T, len
  jae COPY / jb FAIL
  ```

  重写后 re-decode 逐条校验；若分支错误信息仍把缓冲区说错（`... outside the payload pool`），
  则在 `.rodata` 中把该字符串对齐到兄弟分支措辞（独立记录 `rodata_message_align`）；
  最后做白名单 diff，除记录区域外**任何字节变化都 fail-closed**。
- 本样本定位到唯一校验块：vaddr `0x4020d9`，16 字节：

  ```text
  before: 39f3 720c 89df 29f7 39d7 0f83c4feffff   cmp ebx,esi; jb; mov edi,ebx; sub edi,esi; cmp edi,edx; jae
  after:  4489e7 29f7 7209 39d7 0f83c5feffff 90    mov edi,r12d; sub edi,esi; jb; cmp edi,edx; jae; nop
  ```

  `ebx = data_size`（输入大小）→ `r12d = out_size`（输出缓冲区容量）；同一函数内 `literal`
  （`0x401f97`）与 `fill`（`0x40208a`）分支本就用 `r12d`，只有 `span` 分支用错。
- 通用性验证：`fixtures/hard-cases/vuln-capacity-param-x86_64.elf`（另一份 C 源码、不同编译器
  寄存器分配：`rbp`→`r12d`）同样被正确修复并在 guest 中通过差分（见
  `tests/test_capacity_repair.py::test_synthetic_*`）。
- 对仓库内其他 20+ 个 ELF/PE/Mach-O fixture 均不产生候选（fail-closed，见测试）。

### 2.2 真实运行时证据：Linux guest + PoC/回归差分

- `app/services/guest_runner.py`：新增 `find_guest_runner()` / `run_path()`，按
  native Linux → qemu-user → Lima VM（`limactl`）顺序选择执行环境，统一 `crashed/tier/runner`。
- `app/services/poc_runner.py`：PoC manifest 支持逐用例二进制夹具
  `files:[{name,base64}]`（`{tmp}` 替换、暂存目录、原/候选以同一路径顺序执行），
  输出 `status/runner/tier/poc/regression/limitations`。
- 本机为 macOS arm64，x86-64 Linux ELF 只能在 guest 中执行：实际使用运行中的 Lima
  `binaryrepair`（aarch64 Ubuntu，qemu-user/binfmt）→ `runner=limactl, tier=emulated_run`。
  没有 runner 时结果保持 `unavailable`/`not_run`，绝不伪造证据。

### 2.3 验收 gate 扩展（不降低严格性）

- `app/services/unified_verification.py`：新增 required check **`patch.capacity`**——从
  原始字节与候选字节**重新推导**每个重写动作（`original[off:off+size]==before_hex` 且
  `candidate[off:off+size]==after_hex`），引擎报告不被单独信任；
  当 `runtime=None` 且提供 PoC manifest 时，以 **PoC/回归差分**作为该 profile 的运行时证据
  （`runtime.evidence`/`runtime.tier`/`runtime.contract`），runner 不可用时仍 `not_run`。
- `app/services/binary_pipeline.py::repair_any()`：ELF x86-64 旧引擎无候选时回退到
  capacity 引擎（`strategy="capacity"`），并复用同一条 reparse/runtime/gate 尾链；
  无 manifest → `not_verified`（不成功、不提供下载），`allow_static_only` 仍是未验证候选。
- `app/services/repair_matrix.py`：仅 ELF/x86-64 cell 新增 `capacity` 策略与
  `capacity_check_mismatch` sink 类；non-goal 措辞同步更新。
- `app/services/binary_review*.py`：`/api/binary/repair-review` 新增可选 `poc_manifest`
  表单字段（≤64 KiB JSON，否则 422）；该路径命中 capacity profile 时返回 unified 验收包。
- GUI：一键修复面板新增“PoC / 回归用例清单（可选，JSON）”文件选择，随二进制一起提交；
  结果卡片显示 `策略 capacity-check`、`运行时 guest/emulated`、`runner limactl`
  与完整 check 表，成功才提供“下载修复后的 ELF”。

## 3. 验收证据（本目录）

| 文件 | 内容 |
|---|---|
| [`marcx-fixed`](marcx-fixed) | 修复后 ELF：仅 16 B `.text` 重写 + 49 B `.rodata` 错误信息对齐，长度/段表/入口不变 |
| [`patch-record.json`](patch-record.json) | 引擎报告 + before/after 反汇编 + 两个 action 的精确字节 |
| [`poc-manifest.json`](poc-manifest.json) | 4 个 PoC + 10 个回归用例（内嵌夹具，可复跑） |
| [`runtime-evidence.json`](runtime-evidence.json) | 真实 guest 差分：28/28 case 期望一致（4 PoC 原始崩溃/候选拒绝；10 回归原/候选逐字节一致） |
| [`verification-report.json`](verification-report.json) | 确定性 gate 原始报文：14/14 required checks 通过，`outcome=success_within_scope` |
| [`challenge-suite.json`](challenge-suite.json) | 挑战自带 16 例归档矩阵（gate 之外独立确认）：8 例行为不变；5 例原崩溃→现拒绝；1 例原静默越界→现拒绝；`--list` 行为不变；`--dump-index` 原崩溃→现拒绝 |
| [`gui-success.png`](gui-success.png) | GUI 一键修复成功截图（14 项检查全绿、下载按钮可用） |
| [`reproduce.py`](reproduce.py) | 一键复跑：重新生成上述全部证据并校验哈希 |
| [`SHA256SUMS`](SHA256SUMS) | 上述文件摘要 |

关键判据（gate 报文节选）：

```text
format                  passed   elf/x86_64
candidate.present       passed   candidate_bytes=713160
patch.capacity          passed   actions=1 sites=0x4020d9 registers=ebx->r12d
runtime.evidence        passed   runner=limactl tier=emulated_run source=poc_manifest
runtime.contract        passed   poc differential status=pass ...
poc.native.original_failure  passed  cases=4 status=pass
poc.native.candidate_pass    passed  cases=4 status=pass
poc.native.regression        passed  cases=20 status=pass
gate: success=true outcome=success_within_scope reason=all_required_checks_passed
```

## 4. 复现

```bash
cd binary-repair-gui
# 1) 证据一键复跑（需要运行中的 Lima 实例 binaryrepair 或原生 x86-64 Linux/qemu）
.venv/bin/python artifacts/marcx-repair-2026-11-14/reproduce.py

# 2) 单元/集成测试
.venv/bin/python -m pytest tests/test_capacity_repair.py \
    tests/test_binary_pipeline_capacity.py tests/test_poc_runner.py \
    tests/test_guest_runner.py tests/test_binary_review_api.py -q

# 3) 启动 GUI（浏览器打开打印的 http://127.0.0.1:8123/?token=...）
cd binary-repair-gui && ./start-gui.sh
#   一键修复面板：样本选 fixtures/elf/vuln-capacity-confusion-x86_64.elf，
#   “PoC / 回归用例清单”选 fixtures/poc/marcx-capacity.json → 修复成功并可下载
```

## 5. 边界与限制（诚实声明）

- **仅覆盖一类缺陷**：内联、重复、无符号的 `range_ok(dst, len, capacity)` 校验块，且同一
  函数内出现 ≥3 次、少数派容量寄存器可证明是输入大小变量；容量寄存器需为寄存器分配形态。
  编译器把容量每次从结构体字段重载（如 `-O1` 的 `marcx_dbg`、`-DMARC_GUARD_ALLOC` 构建）
  的形态**暂不在本引擎范围内**，会 fail-closed。
- **仅 x86-64 ELF**；不改段表、不注入代码段、不做反汇编-重编译。检测会解码整个可执行区，
  超过 2 MiB 的镜像显式拒绝（`unsupported`），不做部分分析。
- **`verified_patch` 必须提供 PoC/回归 manifest + 可用运行时 runner**；没有证据时只有
  `not_verified`/`inconclusive`，不提供下载。PoC/回归用例由调用方（或本目录 manifest）提供，
  引擎不会自动发现输入格式。
- 该证据是“给定 PoC/回归用例下的修复正确性”，**不是整程序证明**；未覆盖输入空间的
  行为等价性仍需更广泛的差分/fuzz。`runtime-evidence.json` 中 28/28 与
  `challenge-suite.json` 中 16/16 都只说明这些用例上的行为符合预期。
- `--list` 在原始二进制上本来就不做渲染期目标校验（挑战分析 §4.3），修复后行为不变
  （`challenge-suite.json` 中 `poc_overflow--list` 为 `unchanged`）；这不属于本修复范围。
