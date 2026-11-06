import json

BASE = json.load(open("_m4-verify/T30-canonical-build.json"))
SEVEN = json.load(
    open(
        "M1-T30-118-evidence-2026-11-05/t30-rebuild-2026-11-05/07-rebuild.json"
    )
)


def get(path):
    if path.startswith("fixture.support_files."):
        return BASE["fixture"]["support_files"].get(
            path[len("fixture.support_files.") :], "<missing>"
        )
    cur = BASE
    for p in path.split("."):
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return "<missing>"
    return cur


def cmp(field, claimed, actual):
    if actual == "<missing>":
        return False
    if isinstance(actual, dict) and "sha256" in actual:
        actual = actual["sha256"]
    if isinstance(actual, bool):
        return str(claimed).lower().startswith(str(actual).lower())
    if isinstance(actual, (int, float)):
        return claimed == actual
    if isinstance(actual, list):
        return claimed == actual
    a, c = str(actual), str(claimed)
    if c == a or a.startswith(c):
        return True
    if "..." in c:
        p, s = c.split("...")
        return a.startswith(p) and a.endswith(s)
    if field == "trigger.expected_observation":
        return all(x in c for x in ("exit 0", "05040a", "3", "stderr 0"))
    return False


rows = SEVEN["conformance"]
bad = [
    (r["field"], r["build_json"], get(r["field"]))
    for r in rows
    if not cmp(r["field"], r["build_json"], get(r["field"]))
]
print("rows:", len(rows), "matched:", len(rows) - len(bad))
print("mismatches:", bad)
print("verdict differs:", [r["field"] for r in rows if r["verdict"] != "match"])
print("summary:", SEVEN["conformance_summary"])
