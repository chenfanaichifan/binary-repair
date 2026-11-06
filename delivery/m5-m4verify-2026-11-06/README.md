# M5 public key for the m4verify account

Public half only. No private key is included or derivable from this package.

- key: `m5_ed25519.pub`
- fingerprint: `SHA256:OHp8LjckI8lQ3kArUPz2CJ/4OxqzWB5URI8idmZzSOc`
- comment: `2761163826@qq.com` (matches M5 commits)
- public-key sha256: `ca565494b41ecc1de3ed15252d547b9de88466722d9fc54a9dc20a0547634e93`

## M3 install

On the guest, as root:

```sh
ssh-keygen -lf /path/to/m5_ed25519.pub
# must print: 256 SHA256:OHp8LjckI8lQ3kArUPz2CJ/4OxqzWB5URI8idmZzSOc 2761163826@qq.com (ED25519)

sudo sh add-m4-key.sh /path/to/m5_ed25519.pub
```

`add-m4-key.sh` installs into `m4verify`'s `authorized_keys`; it verifies the
input is a single public key and refuses private-key-looking material. Then:

```sh
ssh -i /path/to/m5_id_ed25519 m4verify@binrepair-vm
```

M3 should record the observed fingerprint and the resulting `authorized_keys`
line count. This package is a key handoff, not a T8.3 or gate result.
