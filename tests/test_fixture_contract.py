from __future__ import annotations

import json
from pathlib import Path

from app.domain.contracts import SecurityContract, contract_sha256

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "fixtures/public/CWE121_src_char_declare_cpy_51b/contract.json"


def test_first_persisted_contract_has_six_authorized_edits() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract = SecurityContract.from_dict(data)
    assert contract_sha256(data) == "1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c"
    assert len(contract.authorized_edits) == 6
    assert contract.allowed_calls == ("printLine", "strcpy")
    assert contract.dest_capacity_bytes == 50
    assert contract.max_valid_input_bytes == 49
    assert contract.invalid_exit_code == 1
    assert contract.invalid_stderr == "ERROR: input exceeds destination capacity\n"
    joined = " ".join(contract.authorized_edits).lower()
    assert "0x401304" in joined
    assert "256" in joined
    assert "64" in joined
    assert "fd 2" in joined
    assert "0x401fff" in joined
    assert "no new segment" in joined
    assert contract.sha256() == "1a0ad101097461b207e3ea07e264d8d6eb03bc57d1f54c7b9e41c2955015c10c"
