# M5 build/hash replay

| Field | Value |
|---|---|
| original | `aa42815704d9ffc65b3a49821b3cc6189126a738a7e02d668dec250982408393` |
| candidate | `c4a1592157a2858fcf2dd52623b6ae8c280355ce735a1c224530845569bcaa82` |
| contract canonical | `24bfe568e162be57de013abaeda96060d7edf4cad4b2eca0b003d929d9ec4e37` |
| contract file | `15f6b492608e8c137f2612058bf43b90173284aec86d8c51b25d09903d0ad8df` |
| regen script | `56331eedb4d72c55eec4e0f105fb20207576e6e6860b79ca4cedb175ed54e843` |
| bundle zip | `957d73d4284a4e5ced27de451bacdfe8956751232bd4a1fa5aa6454dccdc108e` |
| SHA256SUMS file | `640b448228ea8e16d15930c5c81a1478a11a82a1feddb122f6262157a87788dd` |

`regen_c4a159.py original.elf replayed.elf` produced a byte-identical candidate;
all 8 SHA256SUMS entries passed. This replay covers the handoff bundle only, not
the formal VM evidence bundle.
