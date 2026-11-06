from app.domain.acceptance import Obligation, decide_attempt_outcome
from app.domain.outcomes import CheckResult

kinds = ["identity", "structure", "interface", "behaviour", "symbolic", "reproducibility"]


def run(label, results, **kw):
    obs = [Obligation(kind=k, required=True, result=r) for k, r in zip(kinds, results)]
    v = decide_attempt_outcome(obligations=obs, **kw)
    print(
        f"{label}: outcome={v.outcome.value} "
        f"reason={getattr(v.reason, 'value', v.reason)} "
        f"failing={v.failing_obligation}"
    )


run("all not_run", [CheckResult.NOT_RUN] * 6)
run(
    "V4 not_run only",
    [CheckResult.PASSED] * 4 + [CheckResult.NOT_RUN] + [CheckResult.PASSED],
    candidate_sha256="a" * 64,
    expected_sha256="a" * 64,
    reviewed_scope_sha256="b" * 64,
)
run(
    "all passed",
    [CheckResult.PASSED] * 6,
    candidate_sha256="a" * 64,
    expected_sha256="a" * 64,
    reviewed_scope_sha256="b" * 64,
)
