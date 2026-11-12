# CGC cb-multios 获取、构建与用途边界

## 结论

CGC 子集不是主评估集，但现在有两层产物：

| 产物 | 格式 | 状态 | 用途 |
|---|---|---|---|
| macOS 本机构建 | Mach-O arm64 | 静态盘点，`repair_supported=0` | 适配器/负例 |
| Linux 交叉编译 | **ELF x86-64**（静态 musl） | 已跑 7 个 POV，2 个干净 crash 差分 | 可执行的小样本差分 |

修复管线只接受 Linux x86-64 ELF，所以只有第二层能被 Route A/B 消费；
它仍然**不是** V0–V5 验收，也不是原版 CGC 的 32 位 syscall ABI。

## 来源

- <https://github.com/trailofbits/cb-multios>
- DARPA CGC challenge binaries、POV、POLL、patched/unpatched 构建
- 工作区 `datasets/cb-multios` 是 shallow + sparse 副本（21 MB，只 checkout
  `3D_Image_Toolkit`、`include`、`tools`）；完整克隆在 `~/cb-multios`（1.1 GB）。

## 产物一：macOS 本机构建（仅静态）

5 对 Mach-O arm64：

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
  `formats=["macho"]`、`repair_supported=0`；
- [`knowledge/cgc_binary_features.json`](../../knowledge/cgc_binary_features.json)：
  LIEF 静态特征。

`detect_binary_format()` 直接读文件头写回 `format/arch/repair_supported`，
不再依赖路径里的架构字样；Mach-O 的 `arch` 从 `null` 修正为 `arm64`。

## 产物二：Linux x86-64 交叉编译（可执行）

源码与补丁在 `datasets/cgc-linux-src`，构建在 `datasets/cgc-linux-build`：

```bash
cmake -S datasets/cgc-linux-src -B datasets/cgc-linux-build \
  -DCMAKE_TOOLCHAIN_FILE="$PWD/datasets/cgc-linux-src/toolchain/zig-x86_64-linux.cmake" \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DBUILD_STATIC_LIBS=ON
cmake --build datasets/cgc-linux-build -j4
```

产物：10 个 ELF（5 对）+ 7 个 POV；清单见
[`knowledge/cgc_linux_x86_64.json`](../../knowledge/cgc_linux_x86_64.json)
（`formats=["elf"]`、`repair_supported=10`、每个文件的 SHA-256）。

移植补丁：

- `maths.S`（32 位 x86 汇编）→ `maths_compat.c`（libm 包装）；
- `libcgc.c` 的 `mmap()` 指针参数显式强转；
- 关闭 UBSan、允许旧式隐式声明（POV 代码）；
- 去掉 zig/lld 不支持的 `--allow-multiple-definition`、`-z execstack`、
  `-z norelro`。

## POV 重放（探索性）

在 Ubuntu 24.04 arm64（Lima `vz`）+ `qemu-x86_64-static 8.2.2` 下重放：

| Challenge | POV | vulnerable | patched | 判定 |
|---|---|---|---|---|
| Palindrome | pov_1 | SIGSEGV | exit 0 | **干净 crash 差分** |
| basic_messaging | pov_1 | SIGSEGV | exit 0 | **干净 crash 差分** |
| Board_Game | pov_1 | exit 0 | exit 1 | 仅行为差异 |
| 3D_Image_Toolkit | pov_1 | 超时 | SIGSEGV | 未复现（type-2 leak） |
| CGC_Hangman_Game | pov_1/2/3 | SIGSEGV + POV exit 1 | 同左 | 未复现（match 失败） |

详细记录：[`docs/acceptance/cgc-pov-2026-11-12.md`](../acceptance/cgc-pov-2026-11-12.md)。

## 边界（必须一起引用）

- **不是原版 CGC**：交叉编译为 x86-64 musl，`-O0`，有源码/调试信息；
  不是 32 位 CGC syscall ABI。
- **不是加固 guest**：qemu-user 模拟，不是 uid 1003/seccomp/netns 的
  executor，不能把这里的 SIGSEGV 当平台级验收。
- **规模**：5/242 个目录；没有 CVE/CWE 标签；不是 benchmark。
- **POV 语义**：CGC POV 不全是 crash PoV；`Board_Game` 的 exit 0/1
  不能写成“漏洞已触发”。
- **差分强度**：2 个 POV 只证明两份构建在该输入上不同，不证明修复后的
  二进制与官方修复版语义等价。
- **不是验收证据**：`artifacts/` 中没有 CGC 的 V0–V5 记录；本页与
  `cgc-pov-2026-11-12.md` 都是探索性材料。

## 如果要用于主评估

CGC 只能作为小样本回归/负例；主评估请用 BinPool 切片（x86-64 ELF、
vuln/patch×opt0–3、CVE/CWE 标签）或 ARVO（可复现漏洞 + Docker vul/fix）。

## 主评估数据状态（2026-11-12）

- **BinPool**：Zenodo 记录 15178740 只有一个
  `binpool_dataset.tar.gz`（40,306,943,879 字节），没有 per-CVE 分片；
  本轮不下载 40 GB。
- **ARVO**：镜像在 Docker Hub；本机 `registry-1.docker.io` 连接超时
  （12s），且宿主机没有 Docker，未拉取。
- **CveBinarySheet**：Kaggle 无凭据、OneDrive 链接 404，仍只有元数据。

所以本轮可执行的只有 CGC 小样本（2 个干净 crash 差分），主评估的
3 个真实 CVE 仍需在能访问 BinPool/ARVO 的环境里做。
