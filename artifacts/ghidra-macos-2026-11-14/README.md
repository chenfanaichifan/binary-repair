# Ghidra 12.2 on Apple Silicon macOS (user-local install)

Date: 2026-11-14. Host: `Darwin arm64` (M2), macOS 13.

## Installed

- Eclipse Temurin **JDK 25.0.5** at `$HOME/Applications/JDKs/temurin-25`
- Ghidra **12.2_PUBLIC_20261016** at `$HOME/Applications/ghidra_12.2_PUBLIC`
- No sudo/root installation. `brew install --cask temurin@25` was attempted but
  failed because no terminal password prompt is available; the user-local
  Adoptium tarball is equivalent and portable.

## Why native build was required

The official Ghidra 12.2 zip includes native components for Windows x64/ARM64
and Linux x86_64 only.  On Apple Silicon the decompiler failed with:

```
ERROR (DecompileProcessFactory) os/mac_arm_64/decompile does not exist
```

The shipped Gradle wrapper was used to build the macOS arm64 natives:

```bash
cd "$GHIDRA_HOME/support/gradle"
JAVA_HOME="$HOME/Applications/JDKs/temurin-25" ./gradlew buildNatives
```

Result: `Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile` exists.

## Headless proof

```bash
source scripts/ghidra_env.sh
bash routeb/ghidra/export.sh \
  fixtures/elf/vuln-strcpy-x86_64.elf vuln_copy artifacts/ghidra-macos-2026-11-14
```

Status: **PASS** — analysis succeeded, `vuln_copy` decompiled (122 chars), metadata
written.  Decompiled output is evidence, not a source recovery claim.

## Reinstall

```bash
bash scripts/install_ghidra_macos.sh
source scripts/ghidra_env.sh
"$GHIDRA_HOME/ghidraRun"
```

The installer downloads JDK 25, Ghidra 12.2 and builds the macOS arm64 natives;
it does not require root.  Paths/versions can be overridden by
`JDK_HOME/GHIDRA_HOME/GHIDRA_VERSION/GHIDRA_ZIP_URL/JDK_URL`.

## Limitation

Headless analysis is verified.  Interactive GUI rendering was not automated in
this headless agent session; `ghidraRun` can be launched by the user with the
environment above.
