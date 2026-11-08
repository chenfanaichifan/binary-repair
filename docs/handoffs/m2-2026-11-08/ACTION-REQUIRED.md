# 129 · 行动清单（2026-11-08）

## 0. 一句话

代码侧已收敛到 0 failed。剩下 3 件需要人推动的事，其中 1 件是硬阻断：
M4 至今没有拿到 r4 包本体，所以 Review 12 无法出正式结论。

## 1. 原硬阻断：已降级为 fetch（2026-11-08 下午更新）

不再依赖 10.6 MB 的 zip。远端已有两个分支：

```bash
git fetch origin m2-h m2-fix-188-windows-gates
git checkout m2-h
sha256sum -c docs/handoffs/m2-2026-11-08/MANIFEST.sha256
# 19 OK
```

```text
m2-fix-188-windows-gates   db814a8   F1–F5 修复
m2-h                       c1e3b85   修复 + 交接材料
```

只有拿不到网络时才用离线包：

```text
m2-handoff-2026-11-08-r4.zip
  164434e60cc09a71caa32b7a345803179a8032357570b7874006d940325a591f
  10,684,792 bytes  解压 18/18

188-windows-test-fixes-2026-11-08.zip
  5824a08092bcb8b09122ca2cede79444b143fb8d1a056f05b86b594b48028ec2
  20,748 bytes      解压 5/5
```

期望 M4 回的三个数：

```text
19/19              m2-h 分支内 MANIFEST 自校验
132 passed         run-m2-tests.sh 的 M2 用例集
18/18 或 5/5       若改用离线 zip
```

Review 12 的 PASS 仍建立在 M2-3（用例集）和 M2-4（页面）被独立复核之上。
判定表见 130 号第 3 节，M4 只需核对事实并写一行结论。

## 2. 需要 M4 补一行明确结论

187 里只有 `M2-4 page confirmation PASS`，没有 `Review 12: PASS`。

要做的：让 M4 在 187 末尾补一行总判定，二选一：

```text
Review 12: PASS   —— UI 如实表达 scope/bounded 缺失，不冒充通过
Review 12: FAIL   —— 列出不通过项
```

口径提醒：这一行只评价「缺失是否被如实表达」，
不代表分析通过，也不能写成「分析验证通过」。

## 3. 需要 Linux 侧跑一次（我这边没有 Linux）

717 passed 引用的是 M1 的干净 clone 记录，我无法本地复现。

要做的（任一 Linux 机器）：

```bash
git checkout 9c95b55c7656784471b6761007a64153d41639e0
git am 0001-evidence-and-elf-gates.patch
python -m pytest -q
```

期望：

```text
719 collected / 717 passed / 2 skipped / 0 failed
```

如果出现 `independent-views` 数为 1–4，说明 F5 的 0/5 约束按预期拦住了
不完整的工具链（不会静默通过）。把 node id 发我，我按 188 的口径判断
是补 view 还是调门控。

## 4. 需要你决策（都不阻断）

### 4.1 e2e 的既有 conftest 导入

```text
tests/e2e/capture_agent_screens.py:23   from conftest import start_gui, stop_gui
tests/e2e/capture_all_pages.py:30       from conftest import start_gui, stop_gui
```

这是你规则里的「情况 B」，但属既有写法，不参与 pytest fixture。
收敛成可导入模块，还是保留现状？我按你的话做。

### 4.2 analysis / comparison 的 typed schema 归属

179 契约只有 `status=not_provided`，没有字段级 schema，
所以 UI 只能显示「不可用」，不能填任何猜测字段。这块归 M5 还是本项目？

### 4.3 要不要出 r5

我的建议是不出。用「r4 + 0001 patch」组合交付：

```text
r4  = 已验收的 M2 主体（10.6MB，18/18）
0001 = F1–F5 修复（7,770 bytes，git am 可直接用）
```

理由：M4 还没收到 r4，再发一个 10MB 包只会增加转发成本和版本混淆。

## 5. 我这边的限制（说明，不需要你处理）

```text
git push        已解决：缺 ~/.ssh/config，用 id_ed25519_binaryrepair 已推送
Linux           无环境，717/2/0 只能引用 M1 记录
WSL / bash      不可用，shell 脚本只能人工审阅
node            不可用，JS 只能靠 pytest 源码级断言
```

## 6. 当前可核验状态

```text
base             9c95b55c7656784471b6761007a64153d41639e0
freeze           c40b694b85ad51a25a9f8136434104d48bdbf5bc
commit           db814a83f783e68da17fd4b3bd3d40d89e951289
tree             21eb9f7baea2a3d4e86ebc566c3c499f03752c88
                 git apply 与 git am 两条路径产出同一棵树

Windows          719 collected / 706 passed / 0 failed / 13 skipped
delivery         git status -- delivery 为空
补丁             apply --check 通过，am --3way 通过
```

## 7. 包内文件

```text
ACTION-REQUIRED.md                本文件
0001-evidence-and-elf-gates.patch git am 用，含提交信息
188-windows-test-fixes.patch      git apply 用，纯 diff
128-f1-f5-implementation-2026-11-08.md
win-full-junit.xml                修复后 Windows 全量
ENV.txt
REPRO.md
DELIVERABLES.sha256               两个 zip 的 sha 指针
MANIFEST.sha256                   LF 自校验
```
