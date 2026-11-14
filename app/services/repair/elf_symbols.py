"""Target-ELF symbol inventory for Route A symbol reconstruction.

Only measured symbols/PLT entries are returned.  Duplicate names are exposed as
ambiguous instead of being silently mapped to an arbitrary address.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.services.containers import detect_container


@dataclass
class SymbolInventory:
    by_name: dict[str, int] = field(default_factory=dict)
    ambiguous: dict[str, list[int]] = field(default_factory=dict)

    @property
    def names(self) -> set[str]:
        return set(self.by_name)


def _record(out: dict[str, list[int]], name: str, va: int) -> None:
    if not name or not va:
        return
    out.setdefault(str(name), []).append(int(va))


def available_symbols(data: bytes) -> SymbolInventory:
    """Return unique target symbols and PLT/import entries by name.

    ``ContainerInfo.symbols`` covers local/global function symbols;
    ``ContainerInfo.imports`` covers x86-64/i386 PLT/JUMP_SLOT entries (including
    ``.plt.sec``).  A name with more than one measured address is ambiguous and
    is not put in ``by_name``.
    """
    container = detect_container(data)
    raw: dict[str, list[int]] = {}
    for va, name in (getattr(container, "symbols", {}) or {}).items():
        _record(raw, str(name), int(va))
    for va, name in (getattr(container, "imports", {}) or {}).items():
        _record(raw, str(name), int(va))
    inventory = SymbolInventory()
    for name, addresses in raw.items():
        unique = sorted(set(addresses))
        if len(unique) == 1:
            inventory.by_name[name] = unique[0]
            continue
        # PLT stubs are executable; GOT/COPY entries are data.  Prefer the
        # measured executable address instead of treating the duplicate as
        # ambiguous.
        executable: list[int] = []
        for va in unique:
            section = container.section_at(va)
            if section is not None and getattr(section, "executable", False):
                executable.append(va)
        if len(executable) == 1:
            inventory.by_name[name] = executable[0]
        else:
            inventory.ambiguous[name] = unique
    return inventory
