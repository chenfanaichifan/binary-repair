import os
import tempfile
from pathlib import Path

data_dir = Path(tempfile.mkdtemp()) / "var"
os.environ["BINARYREPAIR_DATA_DIR"] = str(data_dir)

from app.controller_api import _ai_usage_for_job  # noqa: E402
from app.services import jobs, model_calls  # noqa: E402


def make_job(name: str) -> str:
    record = jobs.create_job(
        original_bytes=b"\x7fELF" + name.encode(),
        filename=f"{name}.elf",
        defect_description="partial usage probe",
        data_dir=data_dir,
    )
    return record.id


def call(job_id: str, usage):
    model_calls.record_call(
        data_dir=data_dir,
        model_requested="m",
        status="ok",
        usage=usage,
        job_id=job_id,
    )


j1 = make_job("j1")
call(j1, {"prompt_tokens": 12, "completion_tokens": 3})
call(j1, None)
print("j1 real + NULL sibling:", model_calls.aggregate_job_usage(data_dir=data_dir, job_id=j1))
print("j1 controller:", _ai_usage_for_job(j1))

j2 = make_job("j2")
call(j2, None)
print("j2 all NULL:", model_calls.aggregate_job_usage(data_dir=data_dir, job_id=j2))
print("j2 controller:", _ai_usage_for_job(j2))

j3 = make_job("j3")
call(j3, {"prompt_tokens": 5, "completion_tokens": 7})
call(j3, {"prompt_tokens": 1, "completion_tokens": 2})
print("j3 all real:", model_calls.aggregate_job_usage(data_dir=data_dir, job_id=j3))

j4 = make_job("j4")
call(j4, {"prompt_tokens": 5, "completion_tokens": None})
print("j4 one-sided NULL only:", model_calls.aggregate_job_usage(data_dir=data_dir, job_id=j4))

j5 = make_job("j5")
call(j5, {"prompt_tokens": 5, "completion_tokens": None})
call(j5, {"prompt_tokens": 1, "completion_tokens": 2})
print("j5 one-sided NULL + real:", model_calls.aggregate_job_usage(data_dir=data_dir, job_id=j5))
