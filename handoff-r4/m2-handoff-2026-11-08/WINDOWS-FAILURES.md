# Windows 失败分类取证（code freeze c40b694）

取证执行时 head 为 `6667dca`；自 `c40b694` 起代码与证据未变，
当前 head `7beb6e3` 只多 186、187 两个 docs。

回应 M1 第 3 条：不能直接把失败记为 known-environment。
本文件提供 M1 要求的四项信息，并给出分类判定与最小修复建议。

## 一、结论摘要

```text
head        6667dca（远端 origin/delivery/all-hands-2026-11-07）
freeze      c40b694
collect     719
failures    5（不是 6；b6d110b 上的 test_p1_guest_bundle 已被 c40b694 修好）
skipped     10
errors      0
```

分类：

| # | 失败项 | 分类 | 是否回归 |
|---|---|---|---|
| 1 | `test_p1_two_route_success` | **产品代码缺陷** | 是，应修 |
| 2 | `test_run_case_none_dispatches_to_repaired_runner` | 测试侧 POSIX 依赖 | 否，但缺门控 |
| 3 | `test_run_case_timeout_has_machine_reason` | 测试侧 POSIX 依赖 | 否，但缺门控 |
| 4 | `test_run_case_incomplete_set_is_machine_reason` | 测试侧 POSIX 依赖 | 否，但缺门控 |
| 5 | `test_static_routeb_bundle` | 外部工具缺失（readelf/objdump） | 否，属工具门控 |

只有第 5 条符合 M1 的 known-environment 定义（工具缺失、有 environment.json 自证）。
第 1 条必须按缺陷处理。第 2–4 条是测试自身的平台假设，应加 skip 门控而非记环境。

## 二、M1 要求的信息

### 1. 六个 node id（实际 5 个）

```text
tests/integration/test_p1_two_route_success.py::test_p1_two_route_success
tests/test_mcp_tool_adapters.py::test_run_case_none_dispatches_to_repaired_runner
tests/test_mcp_tool_adapters.py::test_run_case_timeout_has_machine_reason
tests/test_mcp_tool_adapters.py::test_run_case_incomplete_set_is_machine_reason
tests/test_routeb_executor.py::test_static_routeb_bundle
```

第 6 个 `tests/integration/test_p1_guest_bundle.py::test_real_p1_bundle_ingests_measured_gates`
在 `b6d110b` 上失败，在 `6667dca` 上通过，原因是 `c40b694` 的 `delivery/** -text`。

### 2. 每个的 error class 与 traceback

**F1 · 产品缺陷**

```text
error class: tools.route_bundle_ingest.IngestError
node id:     tests/integration/test_p1_two_route_success.py::test_p1_two_route_success

tests\integration\test_p1_two_route_success.py:38: in test_p1_two_route_success
    ingest(
tools\route_bundle_ingest.py:305: in ingest
    _verify_sums(bundle)
tools\route_bundle_ingest.py:179: in _verify_sums
    raise IngestError(f"SHA256SUMS:{lineno}: hash mismatch: {rel}")
E   tools.route_bundle_ingest.IngestError: SHA256SUMS:1: hash mismatch: _v2-interface-scored.json
```

**F2–F4 · 测试侧 POSIX 依赖**

```text
error class: tools.mcp_tool_adapters.ToolError
node id:     tests/test_mcp_tool_adapters.py::test_run_case_none_dispatches_to_repaired_runner
             tests/test_mcp_tool_adapters.py::test_run_case_timeout_has_machine_reason
             tests/test_mcp_tool_adapters.py::test_run_case_incomplete_set_is_machine_reason

tests\test_mcp_tool_adapters.py:39: in test_run_case_none_dispatches_to_repaired_runner
    response = adapters.run_case(
tools\mcp_tool_adapters.py:126: in run_case
    raise ToolError("binary_not_found", str(binary))
E   tools.mcp_tool_adapters.ToolError: \usr\bin\true
    （timeout 用例为 \bin\sleep）
```

测试文件硬编码 POSIX 路径且无平台门控：

```text
tests/test_mcp_tool_adapters.py:22   "argv": ["/usr/bin/true"]
tests/test_mcp_tool_adapters.py:43   "binary_path": "/usr/bin/true"
tests/test_mcp_tool_adapters.py:190  "argv": ["/bin/sleep", "2"]
tests/test_mcp_tool_adapters.py:217  "binary_path": "/bin/sleep"
（全文无 sys.platform / skipif）
```

**F5 · 工具缺失**

```text
error class: AssertionError
node id:     tests/test_routeb_executor.py::test_static_routeb_bundle

tests\test_routeb_executor.py:39: in test_static_routeb_bundle
    assert result["file_count"] >= 8
E   assert 7 >= 8
```

自证文件 `environment.json`：

```json
{
  "platform": "Windows-11-10.0.26200-SP0",
  "tools": {
    "lief": "1.0.0",
    "pyelftools": "0.33",
    "capstone": "5.0.9",
    "clang_path": "missing",
    "ld.lld_path": "missing",
    "readelf_path": "missing",
    "objdump_path": "missing"
  }
}
```

`bundle-record.md` 同时记录 `static audit: pass`，说明缺的只是
`independent-views/` 的 5 个 readelf/objdump 文本，不是审计失败。

### 3. 平台与版本

```text
OS           Microsoft Windows 11 家庭版 中文版
             10.0.26200 build 26200
architecture AMD64
shell        PowerShell 5.1.26100.9711
python       3.13.14（项目 .venv）
pytest       9.1.1
git          2.56.0.windows.2
core.autocrlf true（本机）
```

### 4. 实际命令

```powershell
# 全量
C:\...\binaryrepair-mvp\.venv\Scripts\python.exe -m pytest `
  --basetemp=C:\pt6667 --tb=short -q `
  --junitxml=C:\Users\linyz\DeepWorks\.deepworks\tmp\head6667-junit.xml

# 单条复现
python -m pytest -q tests/integration/test_p1_two_route_success.py
```

工作目录：`git worktree` 检出 `6667dca`。

## 三、F1 的证据链（关键）

这不是 checkout 转换，也不是一次性环境问题。

```text
步骤 1  干净检出 6667dca
        a1.routeb/_v2-interface-scored.json = 1346 bytes, CR=0
        sha = 43ddd9f5…  == SHA256SUMS 记录值

步骤 2  单独跑 test_p1_two_route_success
        result: 1 passed
        跑完后同一文件 = 1400 bytes, CR=54
        git status: M delivery/.../_v2-interface-scored.json

步骤 3  再跑同一条测试
        result: 1 failed
        IngestError: SHA256SUMS:1: hash mismatch: _v2-interface-scored.json
```

根因（产品代码）：

```python
# tools/route_bundle_ingest.py:336-339
if report["pass"]:
    status = "passed"
    scored = bundle / "_v2-interface-scored.json"
    scored.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    names.append(scored.name)
```

两个问题叠加：

1. `Path.write_text` 未指定 `newline="\n"`，Windows 落盘为 CRLF；
2. 写入目标是**输入证据包目录**，写完后 `SHA256SUMS` 立即失效。

Linux 上 `write_text` 落盘是 LF，所以不触发；这也解释了为什么 M1 干净 clone 是 0 失败。
但它是确定性的跨平台缺陷，且在任一平台都会破坏「证据包不可变」这条原则
（第二条在 Linux 上同样存在，只是哈希恰好没变）。

### 最小修复（建议 M1 采用 A）

A. 不写回证据包（推荐）

```python
scored_dir = data_dir / "scored"          # 或 run 维度目录
scored_dir.mkdir(parents=True, exist_ok=True)
scored = scored_dir / f"{attempt_id}-_v2-interface-scored.json"
```

B. 若必须原地写回，则同时固定换行并重算清单

```python
scored.write_text(
    json.dumps(report, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
# 并同步重建 SHA256SUMS，否则自校验必然失败
```

注意 B 会让证据包哈希随 ingest 变化，与 c40b694 的 byte-exact 目标冲突，故推荐 A。

## 四、F2–F4 的建议

测试用 POSIX 路径是测试自身假设，不是产品缺陷。两种处理：

```python
# 方案 1：门控（最快）
pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX fixture binaries")

# 方案 2：改用当前解释器做被测二进制
"binary_path": sys.executable, "argv": [sys.executable, "-c", "pass"]
```

方案 2 能保留 Windows 覆盖，但需要改 fixture 语义，建议 M1 决定。

## 五、F5 的建议

断言应跟随工具可用性，而不是硬编码 8：

```python
views = out / "independent-views"
view_count = len(list(views.glob("*.txt"))) if views.exists() else 0
assert result["file_count"] == 7 + view_count
```

同时可断言：`readelf`/`objdump` 缺失时 `view_count == 0` 且 `static_audit is True`。
这样 Windows 上不再失败，也不再靠 `>=` 掩盖真实数量。

## 六、10 个 skip 的构成（Windows）

```text
6  tests/test_v3_no_input_e2e.py         skipif(os.name == "nt") · POSIX executable script
1  tests/integration/test_worker.py      skipif(os.name == "nt") · POSIX executable wrapper
2  tests/test_fixture_v3_manifest.py     非 Linux · ELF execution requires Linux
1  tests/integration/test_route_bundle_ingest.py  symlink creation unavailable on this host
---
10
```

其中 9 个在 Linux 上会恢复执行；`test_repaired_candidate_matches_v3_if_provided`
还需要 `BINARYREPAIR_CANDIDATE_ELF` 才会跑，因此 Linux 侧仍会有 skip。
M1 的「2 Linux-only skipped」与之相容，但具体是哪 2 个建议用 `pytest -rs` 落一条记录。

## 七、请 M1 决定的三件事

```text
1. F1 是否按缺陷修复（推荐方案 A：不写回证据包）；若修，M2 可协助出补丁与测试
2. F2–F4 用 skip 门控还是改 fixture（影响 Windows 覆盖范围）
3. F5 断言是否改为 7 + view_count
```

在 1 修好前，Windows 侧不能声明 0 failed；
但也不能把它写成 known-environment，因为它是可复现的产品行为差异。
