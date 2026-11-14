"""Symbol-gap classification and syscall stub templates for Route A.

The model may name a symbol that the target binary does not import.  This
module never rewrites unknown semantics silently: it classifies each call as
already available, satisfiable by a reviewed syscall template, defined by the
patch itself, or unresolved (fail closed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

C_KEYWORDS = {
    "if", "for", "while", "switch", "return", "sizeof", "case", "do", "else",
    "typeof", "alignof", "defined", "_static_assert", "static_assert",
    "volatile", "asm", "__asm__", "__asm", "register", "const", "unsigned",
    "signed", "long", "short", "char", "int", "void", "size_t",
}
_CALL_RE = re.compile(r"(?<![\w.>])([A-Za-z_]\w*)\s*\(")
# Matches a function definition, including a leading return type/static/etc.
_DEF_RE = re.compile(
    r"(?:^|\n)\s*(?:static\s+)?(?:[A-Za-z_]\w*\s+|\*+\s*)*([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)

# Reviewed x86-64 Linux syscall glue.  These templates introduce no external
# symbols and are intentionally limited to low-risk process/fd operations.
_SYSCALL_TEMPLATES: dict[str, str] = {
    "br_write": r'''static long br_write(int fd, const void *buf, unsigned long n)
{
    register long rax __asm__("rax") = 1;
    register long rdi __asm__("rdi") = fd;
    register long rsi __asm__("rsi") = (long)buf;
    register long rdx __asm__("rdx") = (long)n;
    __asm__ volatile("syscall" : "+r"(rax) : "r"(rdi), "r"(rsi), "r"(rdx)
                     : "rcx", "r11", "memory");
    return rax;
}''',
    "br_exit": r'''static void br_exit(int code)
{
    register long rax __asm__("rax") = 60;
    register long rdi __asm__("rdi") = code;
    __asm__ volatile("syscall" :: "r"(rax), "r"(rdi) : "rcx", "r11", "memory");
    for (;;) { }
}''',
}
_TEMPLATE_ALIASES = {"write": "br_write", "exit": "br_exit"}

# Pure, deterministic user-space templates.  These are low-risk replacements
# for common libc functions that have no target import; side-effecting libc
# (fputs/malloc/...) is deliberately absent and remains fail-closed.
_PURE_TEMPLATES: dict[str, str] = {
    "strlen": r'''static unsigned long strlen(const char *s)
{
    const char *p = s;
    while (*p != 0) { p++; }
    return (unsigned long)(p - s);
}''',
    "memcpy": r'''static void *memcpy(void *dst, const void *src, unsigned long n)
{
    unsigned char *d = (unsigned char *)dst;
    const unsigned char *s = (const unsigned char *)src;
    for (unsigned long i = 0; i < n; i++) { d[i] = s[i]; }
    return dst;
}''',
    "memset": r'''static void *memset(void *dst, int value, unsigned long n)
{
    unsigned char *d = (unsigned char *)dst;
    for (unsigned long i = 0; i < n; i++) { d[i] = (unsigned char)value; }
    return dst;
}''',
}
_FPUTS_TEMPLATE = r'''static int br_fputs(const char *s)
{
    unsigned long n = 0;
    while (s[n] != 0) { n++; }
    register long rax __asm__("rax") = 1;
    register long rdi __asm__("rdi") = 2;
    register long rsi __asm__("rsi") = (long)s;
    register long rdx __asm__("rdx") = (long)n;
    __asm__ volatile("syscall" : "+r"(rax) : "r"(rdi), "r"(rsi), "r"(rdx)
                     : "rcx", "r11", "memory");
    return 0;
}'''
_TEMPLATE_SOURCES = {**_SYSCALL_TEMPLATES, **_PURE_TEMPLATES, "br_fputs": _FPUTS_TEMPLATE}
_FPUTS_STDERR_RE = re.compile(r"\bfputs\s*\(\s*([^,()]+?)\s*,\s*stderr\s*\)")


@dataclass
class Resolution:
    available: list[str] = field(default_factory=list)
    defined_in_source: list[str] = field(default_factory=list)
    stubs: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    rewritten_source: str | None = None

    @property
    def ok(self) -> bool:
        return not self.unresolved

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "available": sorted(self.available),
            "defined_in_source": sorted(self.defined_in_source),
            "stubs": sorted(self.stubs),
            "unresolved": sorted(self.unresolved),
        }


def called_names(source: str) -> set[str]:
    return {m.group(1) for m in _CALL_RE.finditer(source)} - C_KEYWORDS


def defined_names(source: str) -> set[str]:
    return {m.group(1) for m in _DEF_RE.finditer(source)} - C_KEYWORDS


def rewrite_fputs_stderr(source: str) -> tuple[str, int]:
    """Rewrite only ``fputs(<simple>, stderr)`` to the reviewed br_fputs stub."""
    return _FPUTS_STDERR_RE.subn(r"br_fputs(\1)", source)


def resolve(source: str, available: set[str] | frozenset[str],
            target_name: str | None = None,
            allow_fputs_stderr: bool = False) -> Resolution:
    """Classify calls; add syscall stubs only when a reviewed template exists.

    Caller must inspect ``unresolved`` and fail closed if non-empty.
    """
    available = set(available)
    rewritten_count = 0
    if allow_fputs_stderr:
        source, rewritten_count = rewrite_fputs_stderr(source)
    defined = defined_names(source)
    if target_name:
        defined.add(target_name)
    names = called_names(source) - defined
    resolution = Resolution()
    resolution.defined_in_source = sorted(defined - ({target_name} if target_name else set()))
    for name in sorted(names):
        if name in available:
            resolution.available.append(name)
        elif name in _TEMPLATE_ALIASES:
            resolution.stubs.append(_TEMPLATE_ALIASES[name])
        elif name in _PURE_TEMPLATES:
            resolution.stubs.append(name)
        elif name == "br_fputs":
            resolution.stubs.append("br_fputs")
        else:
            resolution.unresolved.append(name)
    if rewritten_count:
        if "br_fputs" not in resolution.stubs:
            resolution.stubs.append("br_fputs")
        resolution.rewritten_source = source
    return resolution


def apply_stubs(source: str, resolution: Resolution) -> str:
    """Prepend needed reviewed templates; unresolved calls remain for caller."""
    needed = sorted(set(resolution.stubs))
    if not needed:
        return resolution.rewritten_source or source
    blocks = "\n\n".join(_TEMPLATE_SOURCES[name] for name in needed)
    return blocks + "\n\n" + (resolution.rewritten_source or source)
