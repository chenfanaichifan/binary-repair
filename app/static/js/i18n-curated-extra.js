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

/* /binary (arbitrary binary repair) page: primary Chinese strings -> English.
 * API payloads and exports stay English ASCII; only the page copy is localized. */
Object.assign(window.BR_I18N_OVERRIDES, {
  "任意二进制修复": { en: "Repair any binary" },
  "上传任意 ELF / PE / Mach-O（≤ 20 MiB）先做只读扫描，确认命中的修复矩阵单元与可修补 sink； 再按确定性矩阵发起修复。只有通过运行时验证的候选才能下载；未验证候选需显式允许，且永远不计为成功。": {
    en: "Upload any ELF / PE / Mach-O (≤ 20 MiB) for a read-only scan that reports the matching repair-matrix cell and patchable sinks, then start a repair driven by the deterministic matrix. Only candidates that pass runtime verification can be downloaded; unverified candidates require explicit opt-in and never count as success."
  },
  "矩阵 JSON": { en: "Matrix JSON" },
  "1 · 选择并扫描": { en: "1 · Select and scan" },
  "2 · 扫描结果": { en: "2 · Scan result" },
  "3 · 修复结果": { en: "3 · Repair result" },
  "扫描只读：不写文件、不执行样本。": { en: "Scanning is read-only: no file is written and the sample is not executed." },
  "拖入文件，或点击选择": { en: "Drop a file here, or click to choose" },
  "任意二进制容器 · 单文件 ≤ 20 MiB · 选择后自动扫描": { en: "Any binary container · single file ≤ 20 MiB · scans automatically after selection" },
  "重新扫描": { en: "Scan again" },
  "允许未验证候选（best-effort）": { en: "Allow unverified candidates (best-effort)" },
  "仅静态证据；未通过运行时验证，不计为成功，需人工复核。": { en: "Static evidence only; runtime verification did not pass, so it is not a success and needs manual review." },
  "发起修复": { en: "Start repair" },
  "格式 format": { en: "Format" },
  "架构 arch": { en: "Architecture" },
  "位数 bits": { en: "Bits" },
  "字节序 endian": { en: "Endianness" },
  "矩阵单元 cell": { en: "Matrix cell" },
  "矩阵内可修复 repairable": { en: "Repairable in matrix" },
  "sink 数量 findings": { en: "Sink count (findings)" },
  "sink 明细 findings": { en: "Sink details" },
  "限制 limitations": { en: "Limitations" },
  "结论 disposition": { en: "Disposition" },
  "已验证 verified": { en: "Verified" },
  "证据层级 tier": { en: "Evidence tier" },
  "下载许可 download_allowed": { en: "Download allowed" },
  "下载修复候选": { en: "Download repaired candidate" },
  "下载已验证修复候选": { en: "Download verified repaired candidate" },
  "下载未验证候选": { en: "Download unverified candidate" },
  "已开始下载": { en: "Download started" },
  "只有 delivery.download_allowed 为 true 时才会显示下载按钮；未验证候选不构成修复结论。": {
    en: "The download button appears only when delivery.download_allowed is true; an unverified candidate is not a repair verdict."
  },
  "警告 warnings": { en: "Warnings" },
  "展开 report JSON": { en: "Expand report JSON" },
  "确定性矩阵（覆盖范围）": { en: "Deterministic matrix (coverage)" },
  "英文 ASCII 技术数据 · 与 GET /api/binary/matrix 一致": { en: "English ASCII technical data · identical to GET /api/binary/matrix" },
  "修复单元 cells": { en: "Repair cells" },
  "sink 类别 sink_classes": { en: "Sink classes" },
  "结论取值 dispositions": { en: "Disposition values" },
  "非目标 non_goals": { en: "Non-goals" },
  "边界说明": { en: "Boundary notes" },
  "确定性矩阵。": { en: "Deterministic matrix." },
  "只有矩阵单元命中且分析器发现可修补 sink 时才会产出候选；矩阵外输入（含大端、32 位 Mach-O、fat Mach-O）只做分析，明确返回 analysis_only 或 unsupported。": {
    en: "A candidate is produced only when the matrix cell matches and the analyzer finds a patchable sink. Inputs outside the matrix (including big-endian, 32-bit Mach-O and fat Mach-O) are analysed only and return analysis_only or unsupported."
  },
  "非目标。": { en: "Non-goals." },
  "堆/全局/非导入的内联拷贝、格式化字符串展开、UAF、整数与循环缺陷、arm32/riscv/mips/powerpc 与大端机器码、32 位与 fat Mach-O 改写、超出既有 Mach-O 路径的 Windows/macOS 原生执行，均不在本页承诺范围内。": {
    en: "Heap/global/non-imported inline copies, format-string expansion, UAF, integer and loop defects, arm32/riscv/mips/powerpc and big-endian machine-code repair, 32-bit and fat Mach-O rewriting, and Windows/macOS native execution beyond the existing Mach-O path are outside what this page promises."
  },
  "AI 不参与判定。": { en: "AI does not decide the verdict." },
  "结论由确定性验证门给出；模型可以提议修复，但不能把失败提升为成功，也不能生成结论或证据。页面的 disposition 与 verified 完全取自服务端报告。": {
    en: "The verdict comes from the deterministic verification gate. A model may propose repairs, but it cannot promote a failure to success and cannot emit a verdict or evidence. The page's disposition and verified fields are taken verbatim from the server report."
  },
  "已验证不等于全程序证明。": { en: "Verified is not a whole-program proof." },
  "verified_patch 表示声明范围内的容器重解析、修复动作与运行时用例通过；它不覆盖未声明的路径、输入与并发行为。": {
    en: "verified_patch means the candidate passed container reparse, the recorded repair action and runtime cases within the declared scope; it does not cover undeclared paths, inputs or concurrency behaviour."
  },
  "未验证候选不是成功。": { en: "An unverified candidate is not a success." },
  "static_only_patch 只在显式勾选 best-effort 时返回，只有静态证据、没有运行时证据，必须人工复核后才能使用。": {
    en: "static_only_patch is returned only when best-effort is explicitly enabled; it has static evidence and no runtime evidence, and must be reviewed manually before use."
  },
  "矩阵内": { en: "In matrix" },
  "矩阵外": { en: "Outside matrix" },
  "没有发现可修补的 sink。": { en: "No patchable sink was found." },
  "扫描中…": { en: "Scanning…" },
  "扫描完成": { en: "Scan complete" },
  "修复中…": { en: "Repairing…" },
  "修复完成": { en: "Repair complete" },
  "扫描失败": { en: "Scan failed" },
  "修复失败": { en: "Repair failed" },
  "扫描失败：该输入无法识别或不在支持范围内。": { en: "Scan failed: the input is unrecognised or outside the supported range." },
  "修复请求失败": { en: "Repair request failed" },
  "请先选择或拖入一个二进制文件。": { en: "Choose or drop a binary file first." },
  "文件超过 20 MiB 上限，请换一个更小的样本。": { en: "The file exceeds the 20 MiB limit; choose a smaller sample." },
  "文件为空，请重新选择。": { en: "The file is empty; choose it again." },
  "请求超时，请重试。": { en: "The request timed out; please retry." },
  "网络请求失败，请确认本机服务仍在运行。": { en: "Network request failed; check that the local service is still running." },
  "下载失败：候选数据无法解码。": { en: "Download failed: the candidate data could not be decoded." },
  "已验证": { en: "Verified" },
  "未验证，仅静态证据": { en: "Unverified, static evidence only" },
  "未验证": { en: "Unverified" },
  "仅分析": { en: "Analysis only" },
  "不支持": { en: "Not supported" },
  "已拒绝": { en: "Rejected" },
  "无效输入": { en: "Invalid input" },
  "未知": { en: "Unknown" },
  "是": { en: "Yes" },
  "否": { en: "No" }
});
