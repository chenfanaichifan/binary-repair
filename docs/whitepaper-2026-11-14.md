# AI 驱动的二进制漏洞修复：当前方法论与边界

## 架构

Ghidra/反编译 → 模型语义补丁 → symbol_resolver（纯函数/系统调用/PLT）→
Patcherex2 或 assembly 注入 → native PoC/regression/副作用 gate。

## 已证据化的能力

- 单函数 loop A（copy_name）：Ghidra C → DeepSeek → Patcherex2 → roundtrip 6/6 + fixed 6/6；
- CWE121 非 loop 单函数 A：model guard + reviewed syscall helper + Patcherex2，
  PoC 2/2 + regression 4/4；
- Path A 选择性 call 白名单：12 案 loop 6/6，非 loop 0/6；
- 4 模型矩阵：DeepSeek 两模型 6/12；SiliconFlow CN 免费 Qwen 8B/7B 均 0/12；
- 验证：exit/crash、stdout 签名、可选 strace syscall-errno 代理；
- 符号解析：纯函数模板、write/exit syscall 模板、fputs(stderr) 降级、
  ELF 自动 PLT/符号、malloc/free 有 PLT 才放行。

## 关键负结果

1. 仅增加 callee context 没有提升 `hard-multicall`（0 vs 0）；
2. 该案例真实的 `no_candidate` 原因是 assembly validator 拒绝 `ud2`，不是
   Patcherex2 符号/空间失败；修复后已能注入，native gate 变成语义 fail；
3. 小参数免费模型即便有相同上下文/符号解析器，仍全量 0/12；
4. 精确 TLS errno 不是 syscall errno；后者只能是代理；新增 LD_PRELOAD
   进程退出 errno 探针（native dynamic ELF）仍不是函数返回点。
5. 非 loop 泛化：在 RepairSpec + ABI-strict + cave relocation 修复后，
   hard-multicall / hard-sprintf / hard-nonconst 三例 **AI verified PASS**
   （deepseek-flash）；同一管线 deepseek-v4-pro 为 0/3，证明能力仍依赖模型；
   UAF 参考修复单独 PASS，不计入 AI。

## 不可判定 / 未覆盖

完整堆布局、多线程竞态、系统资源泄漏没有通用判定；本项目的验收永远是
“在给定 PoC/regression 范围内的差异证据”，不是全程序等价证明。

## 复现

`./setup.sh` → 配置环境变量 → `./run_matrix.sh deepseek:deepseek-flash`；
Ghidra 相关实验见 `docs/operations/ghidra-macos.md`。
