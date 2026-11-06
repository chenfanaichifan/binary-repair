#!/bin/sh
# Print the end-to-end check: does /opt/angr-venv reproduce the committed
# V4 evidence byte for byte?
#
#   sh run_e2e.sh            > 03-rerun.txt
#
# Reads:  ~/v4/v4_harness.py, ~/cwe416-sync/{candidate.elf,kit/.../original.elf,
#         kit/.../contract.json}, ~/v4-env/committed-harness-output.json
# Writes: ~/v4-env/rerun.json, ~/v4-env/rerun.log
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
V4ENV=${V4ENV:-$HOME/v4-env}
HARNESS=${HARNESS:-$HOME/v4/v4_harness.py}
CANDIDATE=${CANDIDATE:-$HOME/cwe416-sync/candidate.elf}
FIXTURE=${FIXTURE:-$HOME/cwe416-sync/kit/fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput}
PY=${PY:-/opt/angr-venv/bin/python}

echo "# end-to-end check: does this environment reproduce the committed V4 evidence?"
echo "# guest $(hostname), $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "\$ sha256sum $HARNESS"
sha256sum "$HARNESS"
echo
echo "\$ /opt/angr-venv/bin/python $HARNESS \\"
echo "      --candidate $CANDIDATE \\"
echo "      --original \$FIXTURE/original.elf \\"
echo "      --contract \$FIXTURE/contract.json \\"
echo "      --out $V4ENV/rerun.json"
start=$(date +%s%N)
"$PY" "$HARNESS" \
    --candidate "$CANDIDATE" \
    --original "$FIXTURE/original.elf" \
    --contract "$FIXTURE/contract.json" \
    --out "$V4ENV/rerun.json" > "$V4ENV/rerun.log" 2>&1
end=$(date +%s%N)
echo "  exit 0 in $(( (end - start) / 1000000 )) ms"
echo
echo "\$ sha256sum rerun.json committed-harness-output.json"
# shellcheck disable=SC2086
(cd "$V4ENV" && sha256sum rerun.json committed-harness-output.json)
echo
echo "\$ cmp rerun.json committed-harness-output.json && echo byte-identical"
if cmp -s "$V4ENV/rerun.json" "$V4ENV/committed-harness-output.json"; then
    echo "byte-identical"
else
    echo "DIFFERS"
fi
echo
echo "\$ python3 $HERE/summarize_output.py rerun.json"
"$PY" "$HERE/summarize_output.py" "$V4ENV/rerun.json"
