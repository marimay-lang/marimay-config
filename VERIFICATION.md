# Local verification 2026-09-06

> Historical record: observations, revisions and acceptance status below refer to
> the dated runs. They do not describe a new verification of the current checkout.

Follow-up 2026-09-07: D094 removes the workaround lambda from command/options.my.
Installed doctor, fmt/check, 7 source tests, and 32 process scenarios
× 3 engines/profiles passed; the process run took 61,12 s under load.
Compiler SHA-256 `eee144223830b3b7d3de21cd268d4f74cd2b181288c16ee8978dccaf0e3f439a`.
Hashes and commands are in the language report `cp42-map-error-context-2026-09-07.json`.

Next follow-up 2026-09-07: D093 allows `expect.equal` in `rejected`.
`fmt --check`, `check --all-targets`, 7 source tests, and 32 process
scenarios × 3 engines/profiles passed; 54,45 s under a different test load.
Compiler SHA-256 `2790d7d58c8df17cc34b79990f313d58234a64212153aeec2ffa820a67fd0d3e`.
Hashes and commands: language report `cp42-test-helpers-2026-09-07.json`.

Current follow-up 2026-09-07: D092 allows an empty successful void match arm.
Five application workarounds were removed; fmt/check, 7 source tests in both engines,
and 32 process scenarios × 3 engines/profiles passed. The latest process run took
53,36 s under parallel load. Compiler SHA-256
`0c80a9ac3ef0dcb3827ea8f545c401dfe1e9023f9621be876e23feb4151194a5`.
Exact new application hashes and results are in the language report
`docs/implementation/evidence/cp42-void-match-2026-09-07.json`.
The reports below apply to their respective historical revisions.

This verifies an uncommitted working version without a remote; it does not close CP42 acceptance.
Host: macOS arm64, AppleClang 21. The ordinary installed `mmay` points to
the Release build of the single language repository, based on `3482467` with
the JSON metadata/shadowing changes described in the language report
`docs/implementation/evidence/cp42-json-intrinsics-2026-09-06.md`.
After verification, this language source was committed and pushed to main as
`f53b2896582e60806f4bb1295c7227054fbb528b`; CI run 190 was still pending.

Verified:

- `mmay fmt . --check` and `mmay check .`.
- `mmay test . --engine both`: 7 tests, 0 failures. Coverage includes migration/idempotence,
  Unicode, types/required/unknown/duplicate fields, error paths, limits,
  independent arrays across repeated decodes, non-mutating encoding, domain rules,
  required files, and CLI modes.
- `python3 tools/acceptance.py`: 27 cases with exact comparisons of exit code,
  stdout, and stderr for VM/native debug/native release; additional checks cover
  atomic writes, preservation of an existing file on error, in-place operation,
  a missing parent directory, denied reads/writes, and a closed pipe.
  The final run passed in 36,96 s.

The first process run exposed a missing explicit flush for short output
to a closed pipe. Flush with error handling was added; the repeated run passes.
This is an important application regression, not a weakened check.

The seven-source-test cycle took 17,97 s alongside parallel compiler checks.
This is not an idle-host baseline or evidence that the UX budget of ≤10 s was met.
Cold/warm startup, throughput, peak memory, and behavior near the maximum
size still need separate measurements. Real OS permissions, symlinks, and the full
platform matrix also remain open; capability denial does not replace them.

SHA-256 of the working contents under verification:

```text
7b0d44ec24e7289fc66770fe2a273eb7f987dbc3773ba4ecc4c0f2475b2b0da6  mmay.mod
06f7b3ebd6823089ccb4ed4ad2c045432dff0e626d454e7e4a30fbcaf5bbba83  main.my
de2dd98f339083c8b1669bf4fdd25cc700ca560cd1bc86926f91bc134e4f8573  main_test.my
e6b3762b1b7ba4dbdb3826c80f89b553323049ce5d26e64da654058e1eece624  config/model.my
c8426ce3d87ce19fad31684a0d6744631b1507088513d95027faeb09c3d355a5  command/options.my
8f8f236d34fb18a18c0440b17813528597917c740d2d2c8f01691552d8c7df2c  tools/acceptance.py
c28892cf72f82aacdf1a6fa602da783e02d493da7cf296bda829535040b3d8b0  fixtures/v1.json
a9d1fe87c1225f4b7b31f6872832da7362018a81a33c39a90de91055cc82cea5  fixtures/v2.json
```

Recheck the application and tests after language improvements.
Known limitations are listed in the [ergonomics log](ERGONOMICS.md).

## D087 recheck

The first report and hash table above refer to the initial acceptance run. A workload
measurement exposed a hidden VM instruction limit: an ordinary run could not process
a valid large configuration, although native accepted it. D087 fixes the language
policy without changing the application's `.my` code. The verified compiler has SHA-256
`7609f2b1694dcc08af772f5c46c0a01420cac0e6f9de3f02739acaa6355564ee`.

The extended `tools/acceptance.py` passed 32 cases × VM/debug native/release
native, plus the earlier atomic, capability, and broken-pipe checks: 88,70 s
under parallel language-test load. Added inputs include 1 048 459 bytes with version
first and last, exactly 1 MiB, one extra byte, and an invalid final token.
SHA-256 of the new harness version:
`69b2a65f3773a20aed0b4ed82a557541c30cab2c68c6b409cdffd12b0a96a1cd`.

After parallel builds/tests finished, separate
[sequential measurements](MEASUREMENTS.md) were run. All three repeated source
`mmay test . --engine both` runs passed 7 tests; the large configuration works in all
profiles, but version last takes 11,30 s in VM and exceeds the 10 s budget.
The application is not yet declared fully accepted and still has no commit/remote.

## Verification of performance fixes

D087 is already in main (`7f68843fa2`). The next working compiler has direct
VM dispatch and a corrected check order in the native analyzer:
SHA-256 `dd569c22e561108b8c9273f71698d93798e100e1eac5e85aacd7f32813668483`.
It passed the 32 exact scenarios × VM/debug native/release native again, plus
atomic/capability/broken-pipe checks, in 89,56 s under load from other tests.
All source tests passed in every paired cold/warm measurement. Generated
C matched byte for byte in all three pairs. Details and remaining misses are in
the [measurements](MEASUREMENTS.md); the cold test cycle still exceeds 10 s.

Historical CI run **190** (original private host omitted) for
`f53b289` finished: 13/13 jobs passed, including Linux Clang/GCC,
ASan+UBSan+LSan, TSan, and four fuzz targets. This is the result for that revision,
not evidence of CI success for later changes.

## Verification of bytecode reuse

The next compiler (base `1b6a89f` + invocation-scoped test preparation,
SHA-256 `0a108ed25f4287e24200c9b2e4ae9fb1eccbba3e423215f0078ba6fa8f673645`)
passed the previous 32 exact cases × 3 engines and atomic/capability/broken-pipe
checks: 102,94 s alongside parallel language checks. All source tests and exact
generated-C identity checks passed in three paired cold/warm measurements.
The application still has no commit/remote and is not declared fully accepted.

This language optimization was committed and pushed to main as `cee30f5`.
Local language checks: Release 68/68, full Debug C-unit 26/26,
selected ASan/UBSan 6/6; the extended final allocation-failure sweep
also passed in three builds. CI results for this revision are not yet confirmed.

## Verification of a shared native test executable

The compiler with one native compilation per test invocation (base `cee30f5`, SHA-256
`b4b5a6c95da1956ef5e696aaacd8d2b9c47a58710669b613efaae16c8cf9e3c2`)
passed all 32 process scenarios × 3 engines, plus atomic-write,
access-denial, and closed-pipe checks: 115,77 s alongside parallel language checks.
All 18 commands in the three paired measurements produced the same report of seven passing
tests. Ordinary generated C matched; there is now one test C file instead of seven.
Business logic and existing budgets were unchanged; the application still has no commit/remote.
Local language checks: all 68 Release CTests; selected Debug and ASan/UBSan
checks, including the full native suite and cleanup on allocation failures.
In the first version of the new language fixture, `expect` was mistakenly placed in an ordinary
helper; the fixture was corrected and rechecked. Details and remaining
issues are in the [measurements](MEASUREMENTS.md).

The language optimization was pushed to `main`: `52e5852616d2deb0694c4bfeeb469ae2e31e4599`.
The remote branch was confirmed; the language working tree was clean. Final verification
of the source distribution passed in 15,62 s. CI for this revision has not yet been checked.

## Real filesystem failures, 2026-09-07

`python3 tools/acceptance_files.py`: **23 exact scenarios × VM/Debug native/Release native**,
macOS arm64, an unprivileged user, 19,06 s. The D094
compiler `eee144223830b3b7d3de21cd268d4f74cd2b181288c16ee8978dccaf0e3f439a` was used.
Checks covered Unicode/spaces in paths, relative/external/broken symlinks,
symlinks in a parent component, reading/writing/in-place operation, a directory and FIFO
in place of a file, real read/traversal/creation failures caused by POSIX mode bits,
preservation of an existing file and absence of temporary leftovers, and successful atomic replacement.
OS failures were first confirmed through independent Python system calls;
target paths were inside an explicitly allowed root. Capability denial
is not presented as OS-permission evidence. Raw output and the compiler hash are retained
in `build/files-acceptance-20260907.json` and the language's D094 report.

The first harness put an inaccessible directory below the source module root: source
discovery correctly returned K0004 before the application ran. File data
was moved into a separate physical temporary directory outside the sources,
so the checks exercise the runtime itself. The historical failure is retained in the language report.
These are static symlink scenarios; they do not claim resistance to
concurrent component renames. Windows and the native Tier 1 matrix
remain incomplete.

The same filesystem harness passed 23 × 3 on Ubuntu 24.04 amd64 under M2 emulation,
Clang 18.1.3, ASan+UBSan+LSan, UID 501:20, without network access: 186.10 s.
The application snapshot and original JSON are retained in the language's D094 report;
this diagnostic environment does not replace native Linux Tier 1 testing.

## Primary panic location and stderr preservation, D095

Compiler `2b05ca481917fcf1bf08401a1937e365eab77e602ac07a499f41150db3fa796a`
shows the defining helper and complete source range. The false engine
mismatch for stderr before panic was fixed. Without further application
changes, doctor/fmt/check, 7 tests in both engines, and 32 process
scenarios × 3 engines passed in 61,31 s under load. Full language Release: 73/73;
focused Debug/ASan+UBSan and Linux ASan+UBSan+LSan passed with the environment
limitations stated in the D095 report.

A paired local measurement on the same application after 3 warmups and 11 rounds:
repeated test cycle 0,538 → 0,553 s; first native test artifact 2,015 → 2,192 s
(one run each). Generated C grew by 637 584 bytes, and the test executable
by 376 096 bytes. This is the measured cost of source metadata, not a test speedup.
The 10 s budget is unchanged; sources, hashes, every sample, and conditions are in the language's D095 report.


## Shared acceptance driver, 2026-09-07

Both adapters use local `tools/mmay_acceptance.py`, version 1,
SHA-256 `e7db6d3bcb596fd8d36a8af14068e83ed928a1c48f67211dfcd2c998a5e546ce`.
It owns build/process/exact parity; application JSON, filesystem, atomic,
denied-access, and broken-pipe checks remain in the adapters. Importing from a neighboring
language checkout is unnecessary. Update the driver by explicitly copying
`tools/cli-acceptance/mmay_acceptance.py` from the language repository.

After migration, 32 process cases and 23 filesystem cases passed, each on
VM/native Debug/native Release. New raw reports:
`build/process-acceptance-harness-v1-1788797221910942000.json` and
`build/files-acceptance-harness-v1-1788797189342532000.json`.
Compiler SHA-256 `cd52f0f066342bf3faf6bba183fb395b09a4cc2a75a1ca228e5e9a2e89b0b6af`.
The runs were concurrent correctness checks; their durations are not a
performance baseline. The startup budget and the application's full resource
and platform acceptance remain open. Run Python without `-O`.
