# CGC cb-multios 获取与构建

## 来源

- <https://github.com/trailofbits/cb-multios>
- DARPA CGC challenge binaries、POV、POLL、patched/unpatched 构建

## 本机实际结果

已构建 5 对 Mach-O arm64：

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

- [`knowledge/cgc_corpus.json`](../../knowledge/cgc_corpus.json)
- [`knowledge/cgc_binary_features.json`](../../knowledge/cgc_binary_features.json)

## 关键修复

macOS arm64 不能直接使用仓库的 32 位 `maths.S`。增加
`include/maths_compat.c`（libm 包装）并在 `include/CMakeLists.txt` 中按
`APPLE && arm64` 替换 `maths.S`。

构建：

```bash
cd ~/cb-multios
CMAKE_OPTS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" BUILD64=1 \
  NO_PYTHON_I_KNOW_WHAT_I_AM_DOING_I_SWEAR=1 ./build.sh
cd build64
cmake --build . --target 3D_Image_Toolkit 3D_Image_Toolkit_patched -j4
```

## 边界

- 这是 CGC 子集，不是全部 100+ 挑战。
- `maths_compat.c` 的 `cgc_setjmp/longjmp` 是占位；依赖它们的挑战不做执行验证。
- 只做静态盘点/特征；未在 host 执行 challenge 二进制。
- 未下载 BinPool 40 GB / CveBinarySheet 12.5 GB。
