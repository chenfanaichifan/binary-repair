"""Shared pytest configuration and synthetic fixtures.

This file is test infrastructure for the whole team, not just the acceptance
tests. It provides:

* the project root on ``sys.path`` so tests can import ``app.*`` without
  depending on packaging being installed yet (there is no ``pyproject.toml``
  in the repository's first commit);
* tiny synthetic ELF builders used by screening, identity, and broker tests.

Nothing here reads, writes, or executes a real binary. Builders return bytes
only, so every test that uses them is safe to run on a development host.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# --- ELF constants (subset used by the supported profile) -------------------

EI_NIDENT = 16
ELFCLASS32 = 1
ELFCLASS64 = 2
ELFDATA2LSB = 1
ELFDATA2MSB = 2
ET_EXEC = 2
EM_386 = 3  # 32-bit i386
EM_ARM = 40  # 32-bit ARM
EM_X86_64 = 62  # the MVP's supported machine
EM_AARCH64 = 183


def _ident(
    *,
    elf_class: int,
    data: int,
    version: int = 1,
    osabi: int = 0,
) -> bytes:
    """Build the 16-byte ``e_ident`` array."""
    ident = bytearray(b"\x7fELF")
    ident.append(elf_class)
    ident.append(data)
    ident.append(version)
    ident.append(osabi)
    ident.extend(b"\x00" * (EI_NIDENT - len(ident)))
    return bytes(ident)


def build_elf64(
    *,
    machine: int = EM_X86_64,
    data: int = ELFDATA2LSB,
    e_type: int = ET_EXEC,
    ident_version: int = 1,
    osabi: int = 0,
    body: bytes = b"",
) -> bytes:
    """Return a minimal 64-bit ELF header, optionally followed by ``body``.

    The header declares no program headers or sections (counts are zero), so
    the result parses as a header-only ELF. ``body`` is appended verbatim to
    let a test make the file large or give it trailing content.
    """
    header = _ident(elf_class=ELFCLASS64, data=data, version=ident_version, osabi=osabi)
    header += struct.pack(
        "<HHIQQQIHHHHHH",
        e_type,  # e_type
        machine,  # e_machine
        1,  # e_version
        0x401000,  # e_entry
        0,  # e_phoff
        0,  # e_shoff
        0,  # e_flags
        64,  # e_ehsize
        56,  # e_phentsize
        0,  # e_phnum
        64,  # e_shentsize
        0,  # e_shnum
        0,  # e_shstrndx
    )
    return header + body


def build_elf32(
    *,
    machine: int = EM_386,
    data: int = ELFDATA2LSB,
    e_type: int = ET_EXEC,
    body: bytes = b"",
) -> bytes:
    """Return a minimal 32-bit ELF header, optionally followed by ``body``."""
    header = _ident(elf_class=ELFCLASS32, data=data)
    header += struct.pack(
        "<HHIIIIIHHHHHH",
        e_type,
        machine,
        1,
        0x08048000,
        0,
        0,
        0,
        52,
        32,
        0,
        40,
        0,
        0,
    )
    return header + body


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def elf_x86_64() -> bytes:
    """A minimal, structurally valid Linux x86-64 ELF (the supported profile)."""
    return build_elf64(machine=EM_X86_64)


@pytest.fixture
def elf_x86_64_with_body() -> bytes:
    """A valid x86-64 ELF with 4 KiB of trailing bytes."""
    return build_elf64(machine=EM_X86_64, body=b"\x90" * 4096)


@pytest.fixture
def elf_i386() -> bytes:
    """A valid 32-bit i386 ELF: correct magic, wrong class and machine."""
    return build_elf32(machine=EM_386)


@pytest.fixture
def elf_aarch64() -> bytes:
    """A 64-bit ELF for the wrong machine (AArch64)."""
    return build_elf64(machine=EM_AARCH64)


@pytest.fixture
def elf_arm32() -> bytes:
    """A 32-bit ARM ELF: wrong class and wrong machine."""
    return build_elf32(machine=EM_ARM)


@pytest.fixture
def elf_big_endian() -> bytes:
    """A 64-bit x86-64 ELF header marked big-endian."""
    return build_elf64(machine=EM_X86_64, data=ELFDATA2MSB)


@pytest.fixture
def not_an_elf() -> bytes:
    """Bytes with no ELF magic at all."""
    return b"MZ" + b"\x00" * 62


@pytest.fixture
def truncated_elf() -> bytes:
    """A file whose magic is correct but whose header is cut short."""
    return b"\x7fELF" + b"\x02\x01\x01\x00" + b"\x00" * 8


@pytest.fixture
def empty_input() -> bytes:
    """A zero-byte upload."""
    return b""
