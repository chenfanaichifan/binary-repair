"""Describe what each obligation kind actually establishes.

The GUI renders results; it does not decide them. This module only labels the
scope of a persisted obligation so a reader can tell apart:

- metadata checks (hashes and contract identity, no execution),
- static checks (structure, loading, ABI),
- binary-level behaviour (executed inputs),
- model-level symbolic reasoning (a hand-written model, not the emitted code),
- replay evidence,
- round-trip evidence, which preserves the *original* behaviour and therefore
  cannot count as repair evidence.

``repair_credit`` is the honest bit: only obligations that actually bear on the
repaired candidate may be shown as repair evidence.
"""

from __future__ import annotations

from typing import Any

EVIDENCE_DOMAINS: dict[str, dict[str, Any]] = {
    "identity": {
        "label_zh": "冻结输入",
        "label_en": "Identity and preconditions",
        "level": "metadata",
        "level_zh": "元数据",
        "scope_zh": "只核对任务输入与契约版本哈希，不执行代码。",
        "scope_en": "Frozen job inputs and contract identity; no execution.",
        "repair_credit": False,
    },
    "structure": {
        "label_zh": "静态结构",
        "label_en": "Structure and placement",
        "level": "static",
        "level_zh": "静态",
        "scope_zh": "静态检查指令边界与改动区间，不执行代码。",
        "scope_en": "Static placement of instructions and changed intervals.",
        "repair_credit": False,
    },
    "interface": {
        "label_zh": "接口兼容",
        "label_en": "Interface and compatibility",
        "level": "static",
        "level_zh": "静态",
        "scope_zh": "检查调用约定、载入与 ABI 兼容，不证明行为正确。",
        "scope_en": "Signature, loader and ABI compatibility; not behaviour.",
        "repair_credit": False,
    },
    "behaviour": {
        "label_zh": "行为测试",
        "label_en": "Concrete behaviour",
        "level": "binary",
        "level_zh": "二进制级",
        "scope_zh": "实际执行冻结的有效/无效输入；只覆盖这些输入与本机环境。",
        "scope_en": "Executed frozen valid/invalid inputs; scope limited to that set.",
        "repair_credit": True,
    },
    "symbolic": {
        "label_zh": "符号验证",
        "label_en": "Bounded symbolic security",
        "level": "model",
        "level_zh": "模型级",
        "scope_zh": "对手写 Z3 模型的证明；不证明发射出的机器指令正确实现了该逻辑。",
        "scope_en": "Proof over a hand-written model, not over the emitted instructions.",
        "repair_credit": False,
    },
    "reproducibility": {
        "label_zh": "可复现重放",
        "label_en": "Reproducibility",
        "level": "replay",
        "level_zh": "重放",
        "scope_zh": "用冻结哈希与输入重放，证明可重复，不单独证明修复正确。",
        "scope_en": "Replay with frozen hashes and inputs; reproducibility only.",
        "repair_credit": False,
    },
    # Not produced by the V0-V5 gate list yet; reserved so the round-trip and
    # repaired-behaviour evidence can never be merged into one row.
    "round_trip": {
        "label_zh": "往返行为",
        "label_en": "Round-trip behaviour",
        "level": "binary",
        "level_zh": "二进制级",
        "scope_zh": "未修复的恢复代码保持了原始行为；原始行为可能正是漏洞本身，因此不构成修复证据。",
        "scope_en": "Unrepaired recovered code keeps the original behaviour; not repair evidence.",
        "repair_credit": False,
    },
    "repaired_behaviour": {
        "label_zh": "修复后行为",
        "label_en": "Repaired behaviour",
        "level": "binary",
        "level_zh": "二进制级",
        "scope_zh": "最终候选保留有效行为并满足安全契约；这是唯一可计入修复的行为证据。",
        "scope_en": "Final candidate keeps valid behaviour and meets the safe contract.",
        "repair_credit": True,
    },
}

_UNKNOWN: dict[str, Any] = {
    "label_zh": "未分类证据",
    "label_en": "Unclassified evidence",
    "level": "unknown",
    "level_zh": "未知",
    "scope_zh": "后端未标注证据类型，无法判断它证明了什么。",
    "scope_en": "The backend did not label this obligation's evidence scope.",
    "repair_credit": False,
}

# Some producers send the human label instead of the short V0-V5 kind
# ("Bounded symbolic security" vs "symbolic"). Normalise those before falling
# back to "unknown", and keep the repaired/round-trip split ahead of the generic
# behaviour match so repair evidence is never confused with preservation.
_ALIASES: dict[str, str] = {
    "identity and preconditions": "identity",
    "structure and placement": "structure",
    "interface and compatibility": "interface",
    "concrete behavior": "behaviour",
    "concrete behaviour": "behaviour",
    "bounded symbolic security": "symbolic",
    "reproducibility": "reproducibility",
    "round trip behavior": "round_trip",
    "round trip behaviour": "round_trip",
    "round-trip behavior": "round_trip",
    "round-trip behaviour": "round_trip",
    "repaired behavior": "repaired_behaviour",
    "repaired behaviour": "repaired_behaviour",
}

_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("repaired", "repaired_behaviour"),
    ("round", "round_trip"),
    ("symbolic", "symbolic"),
    ("behaviour", "behaviour"),
    ("behavior", "behaviour"),
    ("reproduc", "reproducibility"),
    ("interface", "interface"),
    ("structure", "structure"),
    ("identity", "identity"),
)


def _resolve(kind: str) -> str | None:
    """Resolve a short kind or a human label to a canonical domain key."""

    key = kind.strip().lower()
    if key in EVIDENCE_DOMAINS:
        return key
    if key in _ALIASES:
        return _ALIASES[key]
    for needle, canonical in _KEYWORDS:
        if needle in key:
            return canonical
    return None


def evidence_domain(kind: str | None) -> dict[str, Any]:
    """Return the display metadata for an obligation ``kind``."""

    if not kind:
        return dict(_UNKNOWN, kind="")
    canonical = _resolve(str(kind))
    if canonical is None:
        return dict(_UNKNOWN, kind=str(kind))
    return dict(EVIDENCE_DOMAINS[canonical], kind=str(kind))


__all__ = ["EVIDENCE_DOMAINS", "evidence_domain"]
