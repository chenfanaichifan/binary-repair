# CGC cb-multios 获取、构建与用途边界

## 结论

这是一份**静态盘点子集**，不是修复/验收评估集：

- 已构建 5 对、共 10 个 **Mach-O arm64** 二进制；
- 盘点结果为 `formats=["macho"]`、`repair_supported=0`；
- 修复管线只接受 **Linux x86-64 ELF**，因此这批样本**不能进入 Route A/B 或 V0–V5**；
- 未执行、未跑 POV，也不构成任何“修复有效性”证据。

它的正确用途是：公开数据来源证据、适配器/特征提取器的真实样本面、以及
“不支持的格式应显式判 unsupported”的负例。

## 来源

- <https://github.com/trailofbits/cb-multios>
- DARPA CGC challenge binaries、POV、POLL、patched/unpatched 构建
- 工作区 `datasets/cb-multios` 是 shallow + sparse 副本（21 MB，只 checkout
  `3D_Image_Toolkit`、`include`、`tools`）；完整构建在 `~/cb-multios`（1.1 GB）。

## 本机实际结果（2026-11-12）

已构建 5 对：

```text
3D_Image_Toolkit
Board_Game
CGC_Hangman_Game
Palindrome
basic_messaging
```

产物：

```text
~/cb-multios/build64/challenges/<name>/<name>
~/cb-multios/build64/challenges/<name>/<name>_patched
```

盘点：

- [`knowledge/cgc_corpus.json`](../../knowledge/cgc_corpus.json)：
  `counts = {binaries: 10, challenges: 5, paired: 5, formats: ["macho"],
  repair_supported: 0}`；
- [`knowledge/cgc_binary_features.json`](../../knowledge/cgc_binary_features.json)：
  LIEF 静态特征（sections/imports/symbols/strings）。

`detect_binary_format()` 现在直接读文件头写回 `format/arch/repair_supported`，
不再依赖路径里的架构字样；因此 `cgc_corpus.json` 的 `arch` 从 `null` 修正为
`arm64`，并明确标出 `repair_supported=false`。

## 关键移植修复

macOS arm64 不能直接使用仓库的 32 位 `maths.S`。增加
`include/maths_compat.c`（libm 包装）并在 `include/CMakeLists.txt` 中按
`APPLE && arm64` 替换 `maths.S`。`cgc_setjmp/longjmp` 是占位实现（直接
`abort()`），依赖它们的挑战不具备可比语义。

构建（仅 macOS 本机静态盘点用）：

```bash
cd ~/cb-multios
CMAKE_OPTS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" BUILD64=1 \
  NO_PYTHON_I_KNOW_WHAT_I_AM_DOING_I_SWEAR=1 ./build.sh
cd build64
cmake --build . --target 3D_Image_Toolkit 3D_Image_Toolkit_patched -j4
```

## 边界（必须一起引用）

- **格式不匹配**：管线只支持 Linux x86-64 ELF（[README.md:4](../../README.md#L4)、
  `app/static/js/agent.js:428`）；本机产物是 Mach-O arm64；原版 CGC 是 i386 ELF +
  CGC syscall ABI。三者都不是同一种可消费目标。
- **规模**：5/242 个目录，不是全量 CGC；没有 CVE/CWE 标签。
- **编译选项**：挑战 CMake 固定 `-O0`（部分带 `-g`），不是 BinPool 的 opt0–opt3；
  源码就在旁边，弱化了“无源码”设定。
- **patched 的语义**：同一份源码用 `#ifdef PATCHED` 编出修复版，是干净的行为
  oracle；但它是整包重编，不是最小二进制补丁，不能做字节级“与官方补丁一致”的
  比较。
- **未执行**：没有 POV replay 记录；仓库自带的 replay 工具是 Python 2 语法
  （`tools/cb-test.py` 的 `import thread`、`tools/cb-replay-pov.py` 的 print 语句），
  在本机不能直接用。
- **语义漂移**：`maths.S` → libm 包装、`setjmp/longjmp` → `abort()`、
  `_FORTIFY_SOURCE` 改动；即使跑起来也不是原 CGC 语义。
- **不是验收证据**：`artifacts/` 中没有 CGC；`DELIVERY.md` 未引用它。

## 如果要让 CGC 真正参与验证

必须在 **Linux x86-64 guest** 中重编（`BUILD64=1`），再跑至少 3 个 POV，记录
“vulnerable 崩、patched 不崩”；否则不要写“验证”。即便如此，它仍只是 5 对的
小样本，不能替代 BinPool/ARVO 的主评估。
