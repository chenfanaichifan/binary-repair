# 214 — Member task prompts (submit only after complete)

Date: 2026-11-09

## Global submission gate

Every member must satisfy all of the following before submitting:

```text
[ ] every task in its prompt is complete
[ ] exact commands and exit codes recorded
[ ] no unrelated files changed
[ ] no public tag/main movement except M4
[ ] no fabricated signature, key, or PASS
[ ] residual blockers stated; partial work submitted as BLOCKED, never as DONE
[ ] commit SHA, changed files, test counts, artifact SHA256 included
```

---

## M4 — sign v1.2.0 receipt

Context:

```text
release/v1.2.0 head 1c6c86d
release/V1.2.0-RELEASE-RECEIPT.md is DRAFT, signature PENDING
public main 9439340 / tag v1.2.0 already released
```

Tasks:

1. Replace the DRAFT receipt with a signed receipt:
   - Release executor: M4
   - Date
   - signature/ref (M4 commit or record)
   - remove `PENDING` and `DRAFT`
2. Commit to `release/v1.2.0`.
3. Push only that branch.
4. Do not move public `v1.2.0`, `v1.1.3`, or any earlier tag.
5. Do not change public main.

Done when:

```text
release/V1.2.0-RELEASE-RECEIPT.md has no PENDING/DRAFT
signed commit is pushed
public main/tag unchanged
git diff is limited to the receipt
```

Submit exactly:

```text
receipt commit SHA
changed file list
public refs before/after
explicit statement: no tag/main movement
```

If M4 cannot sign, submit `BLOCKED`; do not submit a DRAFT as DONE.

---

## M2 — final public verification record

Context:

```text
public main 9439340
tag v1.2.0
source ref origin/v1.2.0-source = 60c4aab
release branch 1c6c86d
```

Tasks:

1. Update `docs/handoffs/209-m2-v1.2.0-final-verification-2026-11-09.md`:
   - source ref and actual source head
   - release branch head and signed receipt commit (after M4)
   - public main/tag/tag object
2. Re-run/report on the public v1.2.0 tree:
   - P0 acceptance 17/17
   - browser e2e 12/12
   - three-state comparison UI
   - upload gate HTTP/file/65 MiB
3. Do not change code unless a verified bug is found; if so, separate branch.
4. Do not move tags or main.

Done when:

```text
record 209 has no placeholder source SHA
all numbers match actual public run
M4 signed receipt commit is referenced
no public write
```

Submit exactly:

```text
branch/commit
record path
P0/e2e logs
public refs observed
```

Do not submit final verification before the M4 receipt commit exists.

---

## M1 — final v1.2.0 handoff

Context:

```text
handoff currently delivery/handoff-v1.2.0-2026-11-09.zip
current draft SHA 4117cd6...
source delivery head 485c9d2...
M4 receipt is still PENDING
```

Tasks:

1. Wait for M4 signed receipt commit.
2. Update handoff with:
   - signed receipt
   - final record 209
   - source ref `v1.2.0-source`
   - public refs
3. Regenerate `SHA256SUMS` and zip.
4. Verify:
   - all listed files hash OK
   - receipt contains no PENDING/DRAFT
   - archive SHA256 recorded
5. Commit/push source delivery only.

Done when:

```text
zip contains signed receipt
SHA256SUMS all OK
archive SHA256 recorded
source delivery pushed
public refs untouched
```

Submit exactly:

```text
archive path + SHA256
source delivery commit
manifest count
receipt commit referenced
```

Do not submit a handoff containing a DRAFT receipt as final.

---

## Lead — closure

Tasks:

1. Confirm v1.1.3 remains frozen.
2. Confirm v1.2.0 public release is closed after M4 signed receipt + M1 handoff + M2 record.
3. Confirm no new tag/main changes.

Done when:

```text
signed receipt exists
M2 record references it
M1 handoff contains it
public refs unchanged from v1.2.0 release
```

Submit exactly:

```text
CLOSED / NOT CLOSED
remaining blockers
frozen tag SHA
```

---

## M3 — no new task

```text
Keep P1/V5 evidence frozen.
Only provide rehash/replay on explicit request.
Do not submit a new PASS.
```

## VMer — no new task

```text
record 88 = NOT AVAILABLE
Do not reopen VM without explicit Lead approval.
```
