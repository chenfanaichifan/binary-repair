#!/usr/bin/env python3
"""Replay one CGC POV against a challenge binary.

Topology (matching CGC / cb-replay):
  pov stdin  <- challenge stdout
  pov stdout -> challenge stdin
  pov fd 3   <-> replay harness (negotiation + final submit)

Only 3D_Image_Toolkit's POV uses type-2 negotiation; the others speak directly
on fd 0/1.  The harness waits briefly for a 4-byte type and otherwise starts the
challenge immediately.

Usage: pov_replay.py <qemu> <challenge> <pov> [timeout_seconds]
Exit: 0 both exited; 3 timeout; 4 challenge died by signal; 5 pov died by signal.
"""
import os
import select
import signal
import socket
import struct
import subprocess
import sys
import time

PAGE_ADDR = 0x4347C000
PAGE_LENGTH = 0x1000
PAGE_BYTES = 4


def read_exact(fd, n, timeout):
    data = b""
    end = time.time() + timeout
    while len(data) < n:
        remaining = end - time.time()
        if remaining <= 0:
            return None
        r, _, _ = select.select([fd], [], [], remaining)
        if not r:
            return None
        chunk = os.read(fd, n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def wait_timeout(proc, timeout):
    try:
        proc.wait(timeout=timeout)
        return True
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return False


def main():
    if len(sys.argv) < 4:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    qemu, challenge, pov = sys.argv[1:4]
    timeout = float(sys.argv[4]) if len(sys.argv) > 4 else 15.0

    cb_in_r, cb_in_w = os.pipe()    # POV stdout -> challenge stdin
    cb_out_r, cb_out_w = os.pipe()  # challenge stdout -> POV stdin
    sock_parent, sock_child = socket.socketpair()

    def pov_preexec():
        os.dup2(sock_child.fileno(), 3)

    pov_proc = subprocess.Popen(
        [qemu, pov],
        stdin=cb_out_r,
        stdout=cb_in_w,
        close_fds=False,
        preexec_fn=pov_preexec,
    )
    os.close(cb_out_r)
    os.close(cb_in_w)
    sock_child.close()

    negotiated = None
    head = read_exact(sock_parent.fileno(), 4, min(2.0, timeout))
    if head:
        pov_type = struct.unpack("<I", head)[0]
        if pov_type == 1:
            rest = read_exact(sock_parent.fileno(), 12, 2.0)
            if rest:
                ipmask, regmask, regnum = struct.unpack("<III", rest)
                ip = 0x41414141 & ipmask
                reg = 0x42424242 & regmask
                sock_parent.sendall(struct.pack("<II", ip, reg))
                negotiated = "type1"
        elif pov_type == 2:
            sock_parent.sendall(struct.pack("<III", PAGE_ADDR, PAGE_LENGTH, PAGE_BYTES))
            negotiated = "type2"
        else:
            negotiated = f"type{pov_type}"

    cb_proc = subprocess.Popen([qemu, challenge], stdin=cb_in_r, stdout=cb_out_w)
    os.close(cb_in_r)
    os.close(cb_out_w)

    ok_cb = wait_timeout(cb_proc, timeout)
    ok_pov = wait_timeout(pov_proc, timeout)
    timed_out = not (ok_cb and ok_pov)

    cb_sig = -cb_proc.returncode if cb_proc.returncode is not None and cb_proc.returncode < 0 else 0
    pov_sig = -pov_proc.returncode if pov_proc.returncode is not None and pov_proc.returncode < 0 else 0
    cb_exit = cb_proc.returncode if cb_proc.returncode is not None and cb_proc.returncode >= 0 else -1
    pov_exit = pov_proc.returncode if pov_proc.returncode is not None and pov_proc.returncode >= 0 else -1

    submitted = None
    if negotiated == "type2":
        tail = read_exact(sock_parent.fileno(), 4, 0.2)
        if tail:
            submitted = tail.hex()

    print(
        f"negotiated={negotiated} cb_exit={cb_exit} cb_signal={cb_sig} "
        f"pov_exit={pov_exit} pov_signal={pov_sig} timed_out={int(timed_out)} "
        f"submitted={submitted}"
    )
    if timed_out:
        return 3
    if cb_sig:
        return 4
    if pov_sig:
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
