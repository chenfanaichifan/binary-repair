# 为什么自动修复会产生“越修越坏”，以及如何一次性解决

## 这次错误补丁的根因

从用户给出的错误“修复版”可以归纳出五类系统性问题：

1. **作用域错误**：把 `buf` 的堆指针和另一个函数里的 `char buf[24]` 当成同一个对象，
   导致 `free()` 栈数组、`sizeof(pointer)`、跨函数插入 guard。
2. **容量来源错误**：`sizeof(pointer)` 是 8，不是 `malloc(16)` 的 16；自动补丁必须
   知道目标的真实容量，不能一律套 `sizeof(target)`。
3. **无编译门禁**：补丁含未定义变量 `n`/`cap`、对栈数组 `free`，仍然被展示。
4. **无补丁校验**：没有检查补丁是否与原始代码同作用域、是否仍保留危险调用。
5. **注释未更新**：代码已改，`❌` 注释还在，误导读者。

## 现在的硬门禁

`app/services/patch_validation.py` 在补丁返回前执行：

```text
scope-aware static checks
  - free() on stack array
  - sizeof(pointer) used as capacity
  - changed C code compile: clang -fsyntax-only
```

任何一项失败：

```text
patched_code = original
changed = false
patch_rejected = true
summary = 检测到问题，但自动补丁未通过校验，需人工修复
```

因此**宁可不给补丁，也不展示坏补丁**。

## 容量模型

`app/services/code_repair.py` 的 `capacity_for(target, position)`：

- 局部/全局数组、结构体成员：`sizeof(target)`；
- `malloc(N)` 的堆指针：`N`；
- `realloc(p, need)` 的指针：`need`；
- 指针容量未知：**不改写**，只给 finding/advice。

`snprintf`、`sprintf`、`strcat` 均走同一容量函数；未知时不做“假修复”。

## 作用域模型

`function_at(position)` 做同函数作用域定位：

- `free`/`sizeof` 检查只在当前函数内匹配声明；
- 堆长度检查只在 malloc 所在函数内寻找对应 memcpy；
- 防止把 A 函数的容量套到 B 函数。

## 新增规则

- `c.stack-memcpy`：栈数组 + 调用者长度，插入 `if (len > sizeof(buf)) return;`，
  不再 `free` 栈数组；
- `c.unbounded-loop`：逐字节 while 复制改为有界 `snprintf`；
- `c.format-string`：用户变量作为 `snprintf` 格式串改为 `"%s"`；
- `c.array-index`：`table[idx]` 插入上下界检查；
- `c.signed-length`：`int len=(int)strlen(...)` 改为 `size_t`，比较去掉 `(int)`；
- `c.integer-promotion`：明确说明 `unsigned short len + 1` 实际提升为 `int`，
  该示例不产生回绕；不伪造“已修复”；
- 既有 `c.strcpy`/`c.sprintf`/`c.strcat` 使用真实容量。

## 测试

`tests/test_patch_validation.py` 覆盖：

- 拒绝 `free()` 栈数组；
- 拒绝未定义变量导致的编译失败；
- 拒绝 `sizeof(pointer)` 容量；
- 堆 `strcpy` 使用 `malloc` 容量；
- 栈 `memcpy` guard 不含 `free`；
- 修改行注释从 `❌` 变为 `✅ patched:`。

## 仍然的边界

- 编译校验只证明“语法/声明”成立，不证明安全；还需 ASan/UBSan、fuzz、契约验证。
- 项目自定义头文件/宏可能让独立 clang 校验失败；此时会保守拒绝。
- 复杂别名、指针算术、跨函数容量传递仍可能漏检；需要 AST/数据流。
- 不能靠正则覆盖所有 C 语义；规则只覆盖已知结构，未知结构必须人工复核。
