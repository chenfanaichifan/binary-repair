# Where "M4 cannot reach the guest" actually stops

The review's first action item is "restore guest access or use a fresh isolated
guest". Before doing either, it is worth knowing which layer is broken, because
three different things wear the same symptom — *ssh: connect to host … : Connection
timed out* — and only one of them is M3's to fix.

This directory answers that with the guest's own log rather than with an
explanation.

## The measurement

The VM was powered off; it was started for this check at 09:48 on 2026-11-07 and
`sshd` came up on `0.0.0.0:22` and `[::]:22` as before. Then, over the guest's
entire sshd journal:

```
$ sudo journalctl -u ssh --no-pager | grep -oE "from [0-9.]+ port" | awk '{print $2}' | sort | uniq -c
    460 192.168.30.1
```

**Every accepted connection in the log comes from `192.168.30.1`** — this host's
VMnet8 address. Not one arrives from anywhere else, at any time, for any account.

And the two keys that are actually installed have never been used:

```
256 SHA256:JF1hZZdGsxmEUt0REdbg4X76LCbaA/1q+0IYObh3zgI  m5-v4-access-2026-11-06
256 SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q  m4-guest-replay-2026-11-06
```

Zero accepted logins between them. The only fingerprints that ever authenticated to
`m4verify` are `5JOwkAS…` (35 times) and `ffnNlGvM…` (once), and both are M3's own
test keys — the first was the key generated for the 11-06 handoff and removed before
delivery, the second was the throwaway used to exercise `add-m4-key.sh` end to end.
Neither is in `authorized_keys` now, so neither can authenticate again.

## What that rules out

| Hypothesis | Status |
|---|---|
| the key is wrong or unreadable | ruled out — the file parses, both fingerprints are correct, `sshd -T` shows `pubkeyauthentication yes` |
| the account is locked out | ruled out — 36 successful logins to the same account from `192.168.30.1` |
| sshd is misconfigured or not listening | ruled out — listening on both stacks, no `AllowUsers`/`DenyUsers` |
| a firewall inside the guest | ruled out — `ufw` inactive, `iptables` INPUT ACCEPT, no `nft` rules |
| **the client cannot route to the guest** | **this one** |

`192.168.30.128` is a VMnet8 NAT address. It exists inside this host. Nothing
outside has a route to it, so a client elsewhere fails at TCP before `sshd` ever
opens a preauth session — which is exactly what the log shows: no such session, ever.

A guest log cannot prove a negative about packets that never arrived. What it can
prove is that `sshd` never opened a preauth session for an outside address, and that
is the same claim one layer up.

## So the fix is not in the guest

The two commands that would open the path are in
`../m4-key-install-2026-11-06/03-network-path.txt`: a `netsh` port proxy and a
firewall rule, both requiring an administrator prompt on this host. The agent runs
unelevated and `netsh` answers *The requested operation requires elevation*, so this
stays open on the host side.

One alternative needs no elevation and should be a decision, not a quiet change:
switching the VM's adapter from NAT to bridged would put the guest directly on the
LAN, where M4 could reach it without any forwarding. The cost is real — the guest
would lose `192.168.30.128`, and every window record from 118 onward, including this
one, describes that address. Re-cutting the environment to make a connection easier
would invalidate the records faster than it would unblock anything.

## Housekeeping done while here

Two private keys on this host could once authenticate to `m4verify`. Both were
already removed from `authorized_keys` before delivery, so neither works; they were
moved out of `.tmp/m4key/` into `.tmp/retired-keys/` so that the tempting-looking
file is not sitting where a later window would reach for it. Deleted keys cannot be
audited; retired ones can.
