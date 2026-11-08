# Gate 6 concrete crash evidence（2026-10-20）

**状态：** concrete counterexample **accepted partial**；symbolic detection 仍是
**pending V4**。本页不声称 gate 6 完成。

## 1. 身份

| 项 | 值 |
|---|---|
| Binary | `original.elf`，26,792 B |
| SHA-256 | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| Guest | Ubuntu 24.04.5 LTS，kernel 6.8.0-147-generic，x86_64 |
| ASLR | `randomize_va_space=2` |
| Raw evidence | `07-gate6-crash-evidence.txt`，SHA-256 `4bab2214e5a17272bb32c20972e3d9ccc422c93e9853cbf89346dbbdf5eb16d9` |
| Summary | `gate6-crash-summary.md`，SHA-256 `cffa8b95ff51774bf55e36fa6e151279c29021215974b14a098241cc21e1801c` |

## 2. 复现

```bash
ARG=$(python3 -c "import sys; sys.stdout.write('A'*100)")
./original.elf "$ARG"
echo $?        # 139 (SIGSEGV)，5/5 次一致
```

## 3. 覆盖证明（strcpy 返回后断点）

`strcpy` 在 `0x401309` 返回；此时：

| 观察 | 值 |
|---|---|
| `dest` | `0x7fffffffe920` |
| `rbp` | `0x7fffffffe960` |
| `rbp - dest` | **64 bytes** |
| `[rbp]`（saved rbp） | `0x4141414141414141` |
| `[rbp+8]`（return address） | `0x4141414141414141` |

50 字节的 buffer 距离 saved rbp 有 64 字节；100 字节输入（含 NUL 101）越过
buffer，正好覆盖 saved rbp 和 return address。

## 4. 故障

```text
SIGSEGV at 0x401317 (ret)
rip  0x401317  <..._badSink+103>   ; ret
rsp  0x7fffffffe968                ; return slot
rbp  0x4141414141414141            ; already popped by leave
```

`leave` 在 `0x401316` 已把攻击者字节装入 `rbp`；`ret` 在 `0x401317` 试图返回
`0x4141414141414141`，进程死亡。

## 5. 证明与不证明

证明：

- `0x4012b0` sink 存在 binary-level OOB write；
- 写入到达 saved rbp / return address；
- 100 字节输入 5/5 确定性崩溃（exit 139）；
- 输入在 frozen oracle 下是 invalid（100 > 49）。

不证明：

- 修复候选安全（V3 是另一件事）；
- OOB 路径的符号可达性（V4，工具链缺失）；
- 其他输入/二进制/总体的结论。

## 6. 与 V3 的关系

- Gate 6 是**检测**：证明原程序确实有漏洞；
- V3 是**修复后的具体行为**：valid 保持、invalid 走精确错误路径；
- 原程序的 manifest 4/6 是 V0 行为证据，不是 gate 6。

V3 的 manifest/contract 断言在 `tests/test_fixture_v3_manifest.py`；gate 6 的
concrete 部分已由成员4 接受，symbolic 部分等 V4 环境。
