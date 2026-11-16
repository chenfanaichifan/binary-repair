# M2 交付说明（跨函数语义最小原型 · Phase-9 起点）

> 2026-11-16 · M2 · 只读分析证据，**不是修复能力**。不接 gate、不产出候选、不调用 live 模型、未做任何 git 写操作。

## 一、结论（一句话）

当前 same-function/leaf-only 引擎修不了跨函数/全局容量漏洞，原因是**sink 处的容量在调用者栈帧/全局符号里，被看的函数只拿到一个不透明指针**；M2 原型用 CFG + 直接调用图 + 跨函数值来源回溯 + 保守别名，在这两类夹具上**定位到了 sink 与容量来源**，而现有确定性引擎在同样输入上返回 analysis_only（无候选）。

## 二、已完成（P0-1 / P0-2 / P0-3）

1. **P0-1 CFG + 直接调用图最小实现**（新增 app/services/analysis/{cfg,callgraph}.py）
   - 真实 ELF（fixtures/elf/vuln-strcpy-x86_64.elf）：1256 functions / 21417 blocks / 120834 reachable instructions / 3605 调用边；
   - 直接调用 resolved=true（vuln_copy→strcpy、main→vuln_copy 可复现）；间接调用 **834 条全部 resolved=false + reason**，不猜目标；
   - arm64 夹具暴露“手写汇编无 .type 符号”问题：用“直接调用目标”作为函数种子（source=call_target，名称仅取自 NOTYPE 符号），x86_64 静态夹具 0 个孤儿调用目标；
   - 固定 JSON：{format,arch,bits,entry,functions:[{va,name,blocks}],edges:[{from,to,kind,resolved,callee,site_va}],limitations,statistics}。

2. **P0-2 跨函数数据流 + 保守别名**（新增 dataflow.py / alias.py / scripts/analyze_crossfn.py）
   - 新夹具 1：sink 在 copy_payload 的 strcpy；原型回溯出两条调用者路径：wrapper（栈帧几何容量上界 32）、wrapper2（经 ret_buffer() 返回值 → 静态 s_ret[16]，STT_OBJECT 精确 16）；两条路径容量不一致 → 报告 conflict，**不取平均不硬选**；
   - 新夹具 2：sink 在 store_out 的 strcpy，目标是全局 g_out[16]；原型用 ELF STT_OBJECT 符号给出**精确容量 16**；来源是 caller 的 argv[1]（无界输入，只报告不修复）；
   - 既有 hard-case heap-canary 交叉验证：原型恢复 malloc 立即数容量 24，并显式标注这是 LIMITATIONS §21 的记录性高估（真实成员 16）——与已知残留一致，不是新能力；
   - 别名模块 fail-closed：不确定即 may-alias/unknown；must_not_alias 只对两个具体单值成立；参数一律 may-alias 任何位置。

3. **P0-3 夹具 + 失败/定位证据**（新增 fixtures/crossfn/**、artifacts/m2-analysis-2026-11-16/**）
   - 2 个最小 C 源 + build.sh（zig 0.17.1，离线、确定性、两次构建 sha 一致）+ original.elf + PoC manifest（evidence_level=declared_not_run）+ 说明；
   - 证据 JSON 9 个文件 + SHA256SUMS：envelope（环境/不运行清单）、cfg 证据、两个跨函数分析、heap 交叉验证、capacity 类对照、引擎只读探针、对比表；
   - 引擎探针（只读 repair_any，候选字节不落盘）：新夹具全部 analysis_only、无候选；同函数夹具 vuln-strcpy-x86_64.elf target=vuln_copy 为 verified_patch（说明引擎在同函数类正常，问题确在跨函数/全局）。

## 三、明确未运行 / 限制（not_run，不得当完成）

- 新夹具的运行时 PoC/回归：本机 macOS arm64，夹具是 x86_64 Linux ELF，**not_run**；manifest 标记 declared_not_run，需 Linux x86_64 + 参考修复后才可填实测值；
- DWARF 对象大小：未实现；栈容量只给 frame_geometry **上界**（16 字节 buf 报 32）——因此**上界容量不能直接当修复容量**（按 32 做 guard 仍会溢出）；
- 间接调用目标、路径敏感、并发、结构体成员布局：not_run（间接调用显式 unresolved）；
- stripped 镜像（vuln-capacity-param-x86_64.elf，-s 构建）：函数发现以符号为准，只能恢复入口+直接调用目标，未发现 sink——已在对照 JSON 中如实记录；
- 不接 gate、不产出候选、不宣称支持 whole-program / 跨函数修复；不调用 live 模型。

## 四、P1 / P2

- P1：docs/operations/m2-analysis-api.md（ASCII-English）给出“分析结果 → RepairSpec 输入”草案，含 fail-closed 规则（上界容量不可用、conflict 不合并、unsupported/unknown 一律 analysis_only）与两个真实例子；标注“草案，未经 gate 验证”。
- P2：capacity-param.crosscheck.json + 本文第二节说明：capacity_confusion 类容量是**同函数参数**，现有容量策略能处理；跨函数夹具的容量在**调用者帧/全局**，才需要 Phase-9 能力——两者不是同一个 gap。

## 五、复现

```bash
cd binary-repair-gui
.venv/bin/python artifacts/m2-analysis-2026-11-16/generate_evidence.py   # 重建全部证据
cd artifacts/m2-analysis-2026-11-16 && shasum -a 256 -c SHA256SUMS      # 校验
.venv/bin/python scripts/analyze_crossfn.py --elf fixtures/crossfn/crossfn_param.elf --json
```

测试：tools/handoff/run-scope-tests.sh m2（28 passed）；日志 .tmp/handoff/m2/。

## 六、需要 Lead/后续决策

1. 上界容量（frame geometry）不足以支撑跨函数修复：Phase-9 E-04 是否排期 DWARF 对象大小解析（M2 下一增量可做）；
2. 同一 sink 多调用路径容量不同 → 需要 M1/RepairSpec 侧决定“按调用路径分别建 spec 或拒绝”，这是接口问题不是分析问题；
3. arm64/i386 数据流、stripped 镜像函数发现、间接调用解析：建议作为 Phase-9 后续显式立项或声明 non_goal。
