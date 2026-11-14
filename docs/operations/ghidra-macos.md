# Ghidra on Apple Silicon macOS (M2) — user-local install

Verified 2026-11-14: **JDK 25.0.5 + Ghidra 12.2_PUBLIC**, no sudo, native
macOS arm64 decompiler built from the shipped Gradle project.

## One-command install

```bash
bash scripts/install_ghidra_macos.sh
source scripts/ghidra_env.sh
```

The official Ghidra zip ships native components only for Windows and Linux x86;
on macOS it fails with `os/mac_arm_64/decompile does not exist`.  The installer
runs `support/gradle/gradlew buildNatives`, which produced the missing
`Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile`.

The installer avoids `brew install --cask temurin@25`, which needs an interactive
sudo password that a headless agent cannot supply.  It extracts the Adoptium
aarch64 tarball under `~/Applications/JDKs/temurin-25` instead.

## Verify

```bash
source scripts/ghidra_env.sh
"$JAVA_HOME/bin/java" -version
bash routeb/ghidra/export.sh \
  fixtures/elf/vuln-strcpy-x86_64.elf vuln_copy /tmp/ghidra-out
"$GHIDRA_HOME/ghidraRun"
```

Expected: `WROTE .../vuln_copy.c`, metadata with `entry=0102bab4`,
`SIZE 31 bytes`; the GUI `ghidraRun` starts a Java `ghidra.GhidraRun` process.
Evidence: `artifacts/ghidra-macos-2026-11-14/`.

## Environment

```bash
export JAVA_HOME="$HOME/Applications/JDKs/temurin-25"
export GHIDRA_HOME="$HOME/Applications/ghidra_12.2_PUBLIC"
export PATH="$JAVA_HOME/bin:$PATH"
export BINARYREPAIR_GHIDRA_HOME="$GHIDRA_HOME"   # GUI connector
```

Ghidra 12.2 requires JDK 25 on this host; mismatched Java is the most common
startup failure.  `routeb/ghidra/export.sh` now defaults to these user-local
paths and checks both Java and Ghidra before launching.

## Scope

This is toolchain readiness and decompilation evidence.  It does not by itself
implement paradigm A; the next step is C patch generation + binary-aware
recompilation behind the existing PoC gate.
