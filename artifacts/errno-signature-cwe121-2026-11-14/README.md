# Optional errno signature: CWE121 (2026-11-14)

`poc_runner` now supports an opt-in `errno_probe: "strace"` manifest field.  For
native ELF execution it runs the PoC under `strace -f` and extracts syscall
errno names; regression cases compare the **set/unset signature**, not exact
errno values.

CWE121 fixed candidate:

- poc status: `pass`
- stdout signature: `matched`
- errno probe: `strace`
- errno signature: `matched`

Observed syscall errno sets are identical between original and fixed for the
four regression inputs (`EBADF`, `EINVAL`, `ENOENT`).  This is a **syscall
errno proxy**, not a full TLS/libc errno capture; the gate remains optional.

Fixed candidate SHA-256: `463a9758f9eb45a8d80d5af340ffd0861997b0ccaa5c5b6be41406616589636f`.
