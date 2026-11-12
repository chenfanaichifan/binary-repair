from pathlib import Path

import lief

from app.services.macho_repair import repair_macho, scan_macho

MACHO = Path("/Users/huageorge/cb-multios/build64/challenges/3D_Image_Toolkit/3D_Image_Toolkit")
CODE = bytes.fromhex(
    "ff8300d1" "02208052" "e8078052" "010000d4"
    "08088052" "010000d4" "a80b8052" "010000d4"
)


def _sample() -> bytes | None:
    if not MACHO.is_file():
        return None
    data = bytearray(MACHO.read_bytes())
    binary = lief.MachO.parse(list(data)).at(0)
    text = next(s for s in binary.sections if s.name == "__text")
    off = int(text.offset)
    data[off:off + len(CODE)] = CODE
    return bytes(data)


def test_macho_immediate_patch_roundtrips():
    data = _sample()
    if data is None:
        return
    scan = scan_macho(data)
    assert scan["findings"]
    patched, report = repair_macho(data)
    assert patched is not None
    assert report.status == "patched"
    assert report.offsets
    assert patched != data
    assert lief.MachO.parse(list(patched)) is not None
