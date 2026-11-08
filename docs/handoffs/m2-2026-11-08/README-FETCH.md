# M2 handoff 2026-11-08 - how to obtain

The handoff used to be a 10.6 MB zip containing a thin git bundle.
That bundle is no longer required: the code is on a public branch.

## Fetch

    git fetch origin m2-fix-188-windows-gates
    git fetch origin m2-h
    git log --oneline -3 FETCH_HEAD

m2-fix-188-windows-gates carries the F1-F5 test fix (commit db814a8).
m2-h carries this handoff directory on top of it.

## Verify on this branch

    git checkout m2-h
    python -m pytest -q

Expected on Linux:   719 collected / 717 passed / 2 skipped / 0 failed
Expected on Windows: 719 collected / 706 passed / 13 skipped / 0 failed

Tracked evidence must stay byte-identical:

    git status --short -- delivery     # must be empty

## If offline

The thin bundle (m2-on-791.thin.bundle, 10.6 MB) still ships inside
m2-handoff-2026-11-08-r4.zip. Use it only when the branch cannot be fetched.

## Note on MANIFEST

MANIFEST.sha256 in this directory covers the files committed here, not the
zip layout. Line endings are LF because .gitattributes keeps docs as text.