# 五类 C 缓冲区溢出：检测、修复与边界

这份说明对应 `samples` 中五类常见 C 溢出。核心结论只有一句：

> 缓冲区溢出不是“字符串函数用错了”，而是**容量、索引、长度三者的不变量在某条路径上被破坏**。
> 静态扫描只能看见语法；要证明“修复成立”，至少要证明这些不变量在运行时仍成立。

## 1. 循环差一：`i <= len` 写 `buffer[len]`

### 原理

```c
char buffer[32];
size_t len = strlen(input);
for (size_t i = 0; i <= len; i++) {
    buffer[i] = input[i];   // 当 len == 32，i == 32 越界
}
```

- 合法下标集合是 `0 .. capacity-1`，即 `i < 32`。
- `i <= len` 在 `len == 32` 时执行第 33 次写入。
- 即使 `len < 32`，循环复制了 `len` 个字符，却没有写入 `\0`；后续 `%s` 会继续读到相邻栈数据。
- 二进制层面，这个额外字节可能正好覆盖 saved RBP/返回地址的低字节；是否可利用取决于布局、编译器和栈保护。

### 安全写法

```c
if (len >= sizeof(buffer)) {
    return;                    // 或明确截断
}
memcpy(buffer, input, len + 1); // input 有 NUL，len + 1 <= sizeof
```

或者：

```c
snprintf(buffer, sizeof(buffer), "%s", input);
```

`snprintf` 保证终止符，但会截断；如果截断不可接受，必须先拒绝超长输入。

### 为什么普通扫描难发现

需要同时知道：`buffer` 的容量、`len` 的来源（`strlen`）、循环上界、写入表达式。只看 `for`/`<=` 会产生大量误报。
本工作台的 `c.off-by-one-loop` 规则只匹配这组结构（固定数组 + `<=` + 同下标写入），并给出容量检查 + 带终止符的 `memcpy`，不假装能理解任意循环。

## 2. 自定义“安全拷贝”：没有为 `\0` 留位

### 原理

```c
for (i = 0; i < dest_size && src[i] != '\0'; i++) {
    dest[i] = src[i];
}
dest[i] = '\0';   // i == dest_size 时越界
```

- `dest_size` 通常表示“整个目标数组大小”，不是“最多可复制的字符数”。
- 循环允许 `i == dest_size - 1` 写入最后一个字符，之后 `i++` 变为 `dest_size`，再写 `\0` 就越界。
- 若 `dest_size == 0`，循环不执行，`dest[0] = '\0'` 仍然越界。

### 安全写法

```c
if (dest_size == 0) return;
for (i = 0; i + 1 < dest_size && src[i] != '\0'; i++) {
    dest[i] = src[i];
}
dest[i] = '\0';
```

更推荐直接使用经过审计的 `snprintf` / `strlcpy`（注意 `strlcpy` 的返回值语义），或者一个带 `(dest, dest_size, src)` 契约并经过模糊测试的函数。

### 本工作台

`c.safe-copy-off-by-one` 检测 `i < dest_size` 循环与 `dest[i] = '\0'` 的组合，改为 `i + 1 < dest_size`，并在 `void` 拷贝函数中插入 `dest_size == 0` 提前返回。非 `void` 函数、复杂 `goto`/多出口不会自动插入 guard，只给建议。

## 3. 报文长度字段：堆分配与 `memcpy` 没有建立关系

### 原理

```c
uint8_t *buffer = malloc(MAX_PAYLOAD);
memcpy(buffer, payload, header->payload_len);
```

- 分配容量是 `MAX_PAYLOAD`，拷贝长度来自**对端可控**的 `payload_len`。
- 如果 `payload_len > MAX_PAYLOAD`，`memcpy` 直接覆盖堆块后的元数据/对象。
- 还存在整数溢出：`sizeof(PacketHeader) + payload_len` 可能回绕，导致分配过小但拷贝很大。
- 只检查 `buffer != NULL` 完全不够。

### 安全写法

```c
if (header->payload_len > MAX_PAYLOAD) {
    free(buffer);
    return; // 或返回错误码，不要继续解析
}
memcpy(buffer, payload, header->payload_len);
```

如果长度可变，应：

```c
if (payload_len > SIZE_MAX - sizeof(*header)) return ERROR;
size_t total = sizeof(*header) + payload_len;
uint8_t *buffer = malloc(total);
if (!buffer) return ERROR;
memcpy(buffer + sizeof(*header), payload, payload_len);
```

### 本工作台

`c.length-field-heap` 匹配 `malloc(cap)` + `memcpy(buffer, ..., field->len)`，在拷贝前插入 `if (len > cap) { free; return; }`。
它不做全程序整数溢出证明；`cap` 是宏/常量时可靠，若是运行时变量需人工确认。

## 4. `sprintf` 拼接：格式展开长度不受控

### 原理

```c
char log_buffer[128];
sprintf(log_buffer, "[LOG] User says: %s", user_msg);
```

- `sprintf` 不知道目标容量；输出长度 = 固定前缀 + `user_msg` 长度。
- 输入超过 128 字节即写穿栈。
- `%n`、宽格式、精度等还会改变写入量；不要用不可信格式串。

### 安全写法

```c
int n = snprintf(log_buffer, sizeof(log_buffer), "[LOG] User says: %s", user_msg);
if (n < 0 || (size_t)n >= sizeof(log_buffer)) {
    // 截断或拒绝；不要把截断当成功
}
```

对堆指针，`sizeof(ptr)` 是 8，不是容量；必须单独保存容量。

### 本工作台

`c.sprintf` 将 `sprintf(dst, fmt, ...)` 改为 `snprintf(dst, sizeof(dst), fmt, ...)`；这只对数组目标成立，堆指针/宏容量会被标记为需人工复核。

## 5. 有符号长度 → `size_t`：负数变巨大

### 原理

```c
void f(int len, const char *data) {
    char local_buf[1024];
    if (len < 1024) {
        memcpy(local_buf, data, len); // len == -1 -> SIZE_MAX
    }
}
```

- `if (len < 1024)` 对 `-1` 成立。
- `memcpy` 第三个参数是 `size_t`；`-1` 转换为 `SIZE_MAX`，发生巨量拷贝。
- 这类问题在反汇编里常表现为：比较指令用的是有符号条件，后续长度寄存器按无符号使用。

### 安全写法

```c
if (len < 0) return ERROR;
if ((size_t)len >= sizeof(local_buf)) return ERROR;
memcpy(local_buf, data, (size_t)len);
local_buf[(size_t)len] = '\0';
```

注意上界应为 `>= sizeof`（给终止符留位），不是 `> sizeof`。

### 本工作台

`c.signed-length` 检测 `int len` + `memcpy(..., len)` + 固定数组，改写为：

```c
if (len >= 0 && (size_t)len < sizeof(local_buf)) {
    memcpy(local_buf, data, (size_t)len);
}
```

仍需调用方限制业务上界；类型转换正确不等于语义正确。

## 为什么“只做静态规则”不够

| 层次 | 能回答 | 不能回答 |
|---|---|---|
| 正则/规则 | 已知危险 API、明显 `<=`、固定数组 | 路径可达、别名、复杂长度计算 |
| AST/数据流 | 哪些值流入长度/索引、是否经过检查 | 所有运行时输入、并发/外部调用 |
| 符号执行 | 哪条路径能令索引越界 | 路径爆炸、环境建模 |
| 动态/ASan | 真实输入是否触发 | 输入空间覆盖 |
| 模糊测试 | 是否能找到反例 | 证明不存在反例 |
| 差分/翻译验证 | 补丁是否保持目标行为/等价 | 全程序生产批准 |

因此正确路线是“规则先筛、数据流确认、符号/动态复现、差分验证”，而不是让一个模型直接宣布“已修复”。

## 本工作台的边界

- 新增五条规则只覆盖**这些结构化形态**；不是通用 C 静态分析器。
- 规则产出的 `patched_code` 是待复核建议，未经过编译/运行时验证。
- 代码块、任务 ID、SHA、verdict 值不做机器翻译；安全结论不翻译。
- 真实修复还应配合 ASan/UBSan、单元用例、fuzz、编译告警（`-Wall -Wextra -Wconversion`）与人工评审。

## 参考

- CWE-193 Off-by-one Error
- CWE-787 Out-of-bounds Write
- CWE-190 Integer Overflow or Wraparound
- CWE-195 Signed to Unsigned Conversion Error
- CWE-120 Buffer Copy without Checking Size
- CERT C: STR31-C, ARR30-C, INT31-C
- NIST SP 800-218 SSDF
