# 二进制 → 汇编 → 修复 → 重新生成二进制

## 结论

本仓库现在有一条**真实可运行**的二进制修复流水线：

```text
ELF x86-64
  -> capstone 反汇编目标函数
  -> 识别 call strcpy@plt
  -> 生成汇编级 trampoline（长度检查/拒绝路径）
  -> 写入现有代码洞（code cave）
  -> 重新生成 ELF
  -> 重新打开并反汇编
  -> 三轮静态验证
  -> 输出 ELF + before.asm + after.asm + report.json
```

命令：

```bash
.venv/bin/python -m routea.assembly_repair \
  --elf artifacts/binary-repair/cave-original.elf \
  --target 0x4012b0 \
  --cave 0x4018e9 \
  --cave-size 0x71 \
  --contract artifacts/binary-repair/contract.json \
  --out artifacts/binary-repair/cave-patched.elf \
  --report artifacts/binary-repair/report.json \
  --asm-dir artifacts/binary-repair/asm
```

实际结果：

```text
passed: true
call_site: 0x401304
original_sha256: aa428157...
patched_sha256: 2e595298...
audit.pass: true
no_wx: true
```

产物：

- [`artifacts/binary-repair/cave-patched.elf`](../../artifacts/binary-repair/cave-patched.elf)
- [`artifacts/binary-repair/report.json`](../../artifacts/binary-repair/report.json)
- [`artifacts/binary-repair/asm/before.asm`](../../artifacts/binary-repair/asm/before.asm)
- [`artifacts/binary-repair/asm/after.asm`](../../artifacts/binary-repair/asm/after.asm)

## 为什么不是“整文件反汇编再原样汇编回去”

**整文件 disassemble → text → reassemble 不是等价变换**，会破坏：

- relocations / GOT / PLT；
- 代码与数据混排；
- PIE/ASLR 相对寻址；
- `.eh_frame`、异常/栈展开元数据；
- 对齐、段权限、入口和调试信息；
- 指令边界之外的字节。

因此本实现采用 **call-site trampoline + code cave**：

```asm
; 原函数
call strcpy@plt
; 修复后
call cave
```

cave 中：

```asm
; rdi=dst, rsi=src
; 扫描 NUL，比较 max_valid
; 合法 -> jmp strcpy@plt
; 非法 -> write(2, msg, len); exit_group(1)
```

这是二进制级修改，不需要源码，也不需要把整个程序重新汇编。

## 三轮验证

`report.json` 的 `rounds`：

1. 原函数成功反汇编，call site 可解码；
2. 重新打开 patched ELF，目标函数仍可反汇编，hash 已变化；
3. ELF 入口/段布局/审计/W^X 全部通过。

`audit` 还检查：

```text
redirect_bytes
cave_code
message_bytes
harness_unchanged
no_new_segments
relocations_unchanged
no_wx
rx_extended
```

## 适用范围

当前实现是 **x86-64 ELF + 已契约化的 `strcpy` 调用点**。

不是通用的“任意二进制自动修复器”。要扩展到：

- `memcpy` / `sprintf` / 循环复制；
- 多调用点；
- PIE/共享库；
- ARM64/Mach-O；
- 反汇编后的完整函数重写；

需要：

- 重定位/符号/段布局引擎；
- 指令语义与数据流分析；
- 更多 cave/段扩展策略；
- 隔离 guest 中的行为回归。

## 行为验证边界

静态验证只能证明：

```text
字节/段/反汇编/审计一致
```

不能证明运行时行为正确。  
真实执行必须在一次性 Linux guest/容器中完成，并运行：

- valid cases；
- invalid cases；
- 原始崩溃/POV；
- ASan/UBSan（如可重建）；
- 回归测试。

当前 macOS host 不能直接执行 x86-64 Linux ELF，因此没有伪造运行结果。

## 与 AI 多 Agent 的关系

AI 多 Agent 用于**源码/汇编建议与复审**；  
二进制最终写回必须经过确定性门禁：

```text
AI 提议
-> 反汇编/汇编/布局检查
-> ELF 审计
-> 静态验证
-> 隔离 guest 行为验证
```

AI 不能直接把任意字节写进二进制并声称修复成功。
