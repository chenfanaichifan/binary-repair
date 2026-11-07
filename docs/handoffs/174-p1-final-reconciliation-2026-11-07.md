# 174 — P1 final reconciliation

Date: 2026-11-07

## Authoritative P1 run

```text
job 1f426d798bd04df9890bf7c8ea658cb3
run 90f16624fcc2497dbd23236a66540584
Route A: V0/V1/V2/V3/V4/V5 passed
Route B: V0/V1/V2/V3/V4/V5 passed
P2 exit 0
verdict success_within_scope
```

Route B used the current `delivery/p1-real-window-2026-11-07/bundle/a1.routeb`
with V2/V4/V5 evidence. Route A used the current M4 V4 marker bound to
`2a96b1083f23a0885ef6152dee39c48648d496a7a026e37ccfb31382c412970e`.

## Superseded run

M1's `784f6cc0185b49edb45e2381d2fddc2a` used a Route B bundle without
V2/V4/V5 evidence. Its Route A passed, Route B was inconclusive, so it is not
the final P1 result.

## Worker fix

M1 commit `1dccf08` was cherry-picked: the worker now evaluates persisted
obligations, not the claimed bundle result. This prevents success with a
persisted not_run gate. Test: `test_worker_evaluates_persisted_gates_not_the_claimed_bundle`.

## Status

```text
T8.3: COMPLETE
P1: success_within_scope
P2: exit 0
```

No tag, merge or live-success claim outside the recorded scope.
