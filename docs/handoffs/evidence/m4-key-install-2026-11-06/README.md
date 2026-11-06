# M4's guest key — installed, and two keys on one account

M4 delivered its public key as text, and this directory records installing it.

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBFmDHmwn/0KeulZ32w97zmV2jP+p7kGMdWew2rZnbdq  m4-guest-replay-2026-11-06
file sha256  ab8fbd7dc23bf900dc1597da8025a689feed55f77275c87869e55fa4dca5a703
fingerprint  SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q
```

| file | what it shows |
|---|---|
| `m4_guest_key.pub` | the key exactly as installed — 108 bytes, one line, LF, trailing newline |
| `01-install-and-acceptance.txt` | digest and fingerprint on both sides, the two lines in `authorized_keys`, idempotence, `600 m4verify:m4verify`, sshd's effective config |

## What is now true

```
~m4verify/.ssh/authorized_keys   600 m4verify:m4verify     2 lines
  SHA256:JF1hZZdGsxmEUt0REdbg4X76LCbaA/1q+0IYObh3zgI  m5-v4-access-2026-11-06
  SHA256:bRq28b6JG3LXILy3iayXdW/HdSre8mCofnd6B+8L84Q  m4-guest-replay-2026-11-06
```

M5's line is untouched — same fingerprint, same position, first. M4's was appended
beside it. `add-m4-key.sh` is idempotent: a second run reports `already present`
and the count stays at 2 rather than growing a duplicate.

The account keeps its shape: uid 1004, own group, no sudo, password locked (`L`).
sshd offers `pubkeyauthentication yes` and `passwordauthentication no` on
`0.0.0.0:22` and `[::]:22`, so this key is now the way in.

## What this does not establish

That M4 can log in. That requires M4's private half, which was never sent to this
host and is in no repository, package or transcript here. The install proves the
server will accept that key; the login proves the client holds it. Only M4 can
produce the second half.

Nor does it establish anything about V4. A key is access, not a replay. `V4` stays
`not_run` until M4 runs the harness and writes its own `verified_by`, and M3 does
not write that field.

## Correction to the two previous windows

Earlier records said M4's key "is not on this host" after searching the working
tree, `/tmp` and the disk. That was true of the working tree and, per the request,
wrong about the repository: the key is said to live on a separate branch,
`delivery/t83-2026-11-06` (root commit `f46c626c`, key commit `df99853b`), which no
checkout on this machine contains — so `find` could not have found it, and
`git fetch origin delivery/t83-2026-11-06` was the command that was missing from
those two windows.

This window did not get to verify that either, and the record should say so rather
than inherit the claim. The fetch was attempted five more times while writing this
and failed every time with the same transport fault as the rest of the afternoon
(`Empty reply from server`, `CONNECT tunnel failed, response 502` on
`github.com:443`). `git cat-file -t` on both of those commit ids returns nothing on
this host, because without the branch there is nothing to read.

So the key was installed from the text supplied with the request, and the check
performed was the one available: the file's digest equals the digest supplied
alongside it, `ab8fbd7d…a703`, and its fingerprint equals `bRq28b6J…84Q`. That is
consistency between two things the request provided, not an independent reading of
a branch. When the transport recovers, `git show origin/delivery/t83-2026-11-06:m4_guest_key.pub`
should produce these same 108 bytes — if it does not, this directory is wrong and
the branch is right, and the installed key would have to be replaced.

