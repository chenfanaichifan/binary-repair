Object.assign(window.BR_I18N_OVERRIDES || (window.BR_I18N_OVERRIDES = {}), {
 "循环边界使用 <= 导致差一越界写": {
  "en": "Loop bound uses <= and writes one byte out of bounds"
 },
 "改为 len >= sizeof(buffer) 时拒绝/截断；用 memcpy(buffer, input, len + 1) 或 snprintf，并保留 \\0。": {
  "en": "Reject or truncate when len >= sizeof(buffer); use memcpy(buffer, input, len + 1) or snprintf and keep the NUL terminator."
 },
 "循环多写一个字节，可能覆盖栈上的返回地址/相邻变量，造成崩溃或代码执行。": {
  "en": "The extra byte can overwrite a saved return address or adjacent stack data, causing a crash or code execution."
 },
 "len 恰好等于缓冲区大小时，i <= len 的最后一次迭代写到 buffer[len]，越界 1 字节；随后若再用 %s 读取，还会缺少 \\0 终止。": {
  "en": "When len equals the buffer size, the final i <= len iteration writes buffer[len]; the subsequent %s also lacks a NUL terminator."
 },
 "差一错误不是“只多一个字节”的小问题；在栈上它足以改变控制流。": {
  "en": "An off-by-one is not just one extra byte; on the stack it is enough to change control flow."
 },
 "自定义安全拷贝未为 \\0 预留空间": {
  "en": "Custom safe-copy does not reserve space for the NUL terminator"
 },
 "把循环条件改为 i + 1 < dest_size（或 i < dest_size - 1），保证 dest[i] = '\\0' 落在容量内。": {
  "en": "Change the loop to i + 1 < dest_size (or i < dest_size - 1) so dest[i] = '\\0' stays within capacity."
 },
 "自定义“安全拷贝”在目标满时把 \\0 写到 dest[dest_size]，越界 1 字节。": {
  "en": "The custom safe-copy writes NUL at dest[dest_size] when the destination is full, one byte out of bounds."
 },
 "循环允许 i 到达 dest_size，随后 dest[i] = '\\0' 写到边界之外；dest_size 没有为终止符预留位置。": {
  "en": "The loop lets i reach dest_size; dest[i] = '\\0' then writes past the boundary because dest_size did not reserve room for the terminator."
 },
 "“自己写的安全函数”仍需证明每个写操作都满足 0 <= index < capacity。": {
  "en": "A self-written safe function still needs a proof that every write satisfies 0 <= index < capacity."
 },
 "报文长度字段未校验即用于堆拷贝": {
  "en": "Packet length field is used for a heap copy without validation"
 },
 "报文长度字段可超过堆块容量，memcpy 直接覆盖堆元数据/相邻对象，可能导致任意写。": {
  "en": "The packet length can exceed the heap allocation; memcpy overwrites heap metadata or adjacent objects and may enable arbitrary writes."
 },
 "分配使用固定 MAX_PAYLOAD，但拷贝长度完全信任 header->payload_len；两个容量事实没有建立关系。": {
  "en": "The allocation uses a fixed MAX_PAYLOAD, but the copy length trusts header->payload_len; the two capacity facts are never related."
 },
 "长度字段是攻击面，不是可信元数据；拷贝前必须验证 len <= capacity。": {
  "en": "A length field is attack surface, not trusted metadata; validate len <= capacity before copying."
 },
 "有符号长度直接传入 memcpy（负数变巨大 size_t）": {
  "en": "Signed length passed directly to memcpy (negative becomes a huge size_t)"
 },
 "负数长度通过 int 检查后转换为巨大的 size_t，memcpy 会破坏栈并崩溃/可被利用。": {
  "en": "A negative length passes the int check and converts to a huge size_t; memcpy then corrupts the stack and may be exploitable."
 },
 "if (len < 1024) 对负数成立；memcpy 的第三个参数是 size_t，len=-1 变为 SIZE_MAX。": {
  "en": "if (len < 1024) is true for negative values; memcpy's third argument is size_t, so len=-1 becomes SIZE_MAX."
 },
 "有符号/无符号转换必须在调用前显式检查 len >= 0 并限定上界。": {
  "en": "Check len >= 0 and enforce an upper bound before any signed-to-unsigned conversion."
 }
});

Object.assign(window.BR_I18N_OVERRIDES, {
  "差一循环已改为显式容量检查 + 带终止符的 memcpy；若 input 不是 NUL 结尾，需改为 len 限制并手动补 \\0。": {
    en: "The loop now has an explicit capacity check and a NUL-terminating memcpy; if input is not NUL-terminated, limit by len and add the terminator manually."
  },
  "自定义拷贝循环改为 i + 1 < dest_size；dest_size == 0 时不会写终止符，调用方仍需拒绝零容量。": {
    en: "The custom copy loop now uses i + 1 < dest_size; dest_size == 0 writes no terminator, so the caller must reject zero capacity."
  },
  "已加入 dest_size == 0 的提前返回；调用方仍应拒绝零容量。": {
    en: "Added an early return for dest_size == 0; the caller should still reject zero capacity."
  }
});
