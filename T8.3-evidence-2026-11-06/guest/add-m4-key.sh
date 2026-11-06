#!/bin/sh
# Install M4's own public key for the m4verify account.
#
#   sudo sh add-m4-key.sh /path/to/m4_id_ed25519.pub
#   ssh-keygen -t ed25519 -f ~/.ssh/m4_id_ed25519 -C "m4@verifier"   # on M4's side
#
# M4 generates the keypair; M3 only ever sees the public half. Nothing in this
# delivery ships a private key for m4verify.
#
# Idempotent: the same key twice does not duplicate a line. Verifies the input is
# a single public key before writing anything, and leaves the file at 600 owned by
# m4verify.
set -eu

USER_NAME=${USER_NAME:-m4verify}
PUB=${1:-}

if [ "$(id -u)" -ne 0 ]; then
    echo "run this with sudo: sudo sh $0 <m4_public_key>" >&2
    exit 2
fi

if [ -z "$PUB" ] || [ ! -f "$PUB" ]; then
    echo "usage: sudo sh $0 /path/to/m4_public_key.pub" >&2
    exit 2
fi

if ! grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp[0-9]+) [A-Za-z0-9+/=]+' "$PUB"; then
    echo "not a public key: $PUB" >&2
    exit 2
fi
if grep -qi 'PRIVATE KEY' "$PUB"; then
    echo "refusing: that file looks like a private key" >&2
    exit 2
fi

HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
if [ -z "$HOME_DIR" ]; then
    echo "no such user: $USER_NAME" >&2
    exit 2
fi

install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "$HOME_DIR/.ssh"
KEY=$(head -1 "$PUB")
touch "$HOME_DIR/.ssh/authorized_keys"
if grep -qxF "$KEY" "$HOME_DIR/.ssh/authorized_keys"; then
    echo "already present: $(echo "$KEY" | cut -c1-32)…"
else
    printf '%s\n' "$KEY" >> "$HOME_DIR/.ssh/authorized_keys"
    echo "added: $(echo "$KEY" | cut -c1-32)…"
fi
chown "$USER_NAME:$USER_NAME" "$HOME_DIR/.ssh/authorized_keys"
chmod 600 "$HOME_DIR/.ssh/authorized_keys"

echo
echo "fingerprint: $(ssh-keygen -lf "$PUB" 2>/dev/null | awk '{print $2}')"
echo "authorized_keys now holds $(wc -l < "$HOME_DIR/.ssh/authorized_keys") key(s)"
