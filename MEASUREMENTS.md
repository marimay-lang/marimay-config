# Measurements 2026-09-06

> Historical record: observations, revisions and acceptance status below refer to
> the dated runs. They do not describe a new verification of the current checkout.

Host: macOS arm64, Apple M2; Release compiler. Processes ran
sequentially after our builds and tests finished. The user's background applications
continued running. The OS cache was not cleared; "first measured run" does not mean
a disk-cold launch, and the measured test cycles used an already warm
native cache. The application and input bytes were unchanged between comparisons.

Baseline: clean `f53b289`, compiler SHA-256
`45d410f7e611da8ee3e9f26c1168fd20a477086ac3093c9e261c8ca2dfe28e8a`.
Repeat: `f53b289` with the verified D087 change, compiler SHA-256
`7609f2b1694dcc08af772f5c46c0a01420cac0e6f9de3f02739acaa6355564ee`.

| Scenario | Baseline | With D087 | Predetermined budget |
|---|---:|---:|---:|
| First small VM run | 0,291 s | 0,289 s | ≤1 s |
| Repeated VM run, median of 7 | 0,294 s | 0,292 s | ≤0,3 s |
| First launch of a new native executable | 0,600 s | 0,594 s | ≤0,1 s — missed |
| Small configuration, native, median of 7 | 0,0048 s | 0,0044 s | ≤0,1 s |
| VM: 1 048 459 bytes, version first | I0002/70 | 6,744 s | ≤10 s |
| VM: same configuration, version last | I0002/70 | 11,299 s | ≤10 s — missed |
| Native: version first / last | 0,413 / 0,564 s | 0,415 / 0,565 s | ≤1 s |
| Warm cycle of 7 tests, median of 3 | 5,903 s | 5,566 s | ≤10 s |
| RSS of successful large VM / native run | VM did not finish / 87,4 MiB | 145,7 / 87,5 MiB | ≤256 MiB |

All repeated checks produced the expected complete JSON response. The baseline VM
terminated with an error: its time and RSS cannot count as a successful fast run.
The first baseline test cycle took 14,598 s, exceeding the budget;
later warm cycles do not erase that observation. Repeated small VM
runs with D087: 0,2897–0,3008 s; a median does not guarantee an upper bound.

The large configuration contains 43 680 unique `requiredFiles`; string lengths and
element counts are permitted by the schema. Large-input times include startup/source checking
and input processing: approximately 0,148 / 0,088 MiB/s for VM and 2,41 / 1,77 MiB/s for
native, depending on the position of version. The cost of a second pass and copying
still needs profiling. The cause of the first native-invocation delay has not yet
been established. Do not reduce the data volume or raise budgets to conceal misses.

Reproduction (use a new report name for each run):

```sh
python3 tools/measure.py --output build/measurements-new.json
python3 tools/make-fixtures.py build/new-resource-fixtures
```

Full local reports contain commands, raw times, stdout/stderr,
input hashes, and `.my` file hashes. SHA-256:

```text
7f7a04069cd74a9d83684d9e03f5964da52f6931fde90cfca07e666d001c914f  build/measurements-baseline-20260906.json
569221e9cfef92c00f0779e40c95fcf2b89f1d57d36a4a154cffac15aceb4b85  build/measurements-d087-20260906.json
```

This is a local baseline, not completed performance/platform acceptance.
RSS is whole-process memory, not a managed-heap counter. OS-permission,
symlink, other resource-boundary checks, and the other eight new utilities are still pending.

## Fixing two hot spots

D087 was pushed to main as `7f68843fa2`. Profiling then identified two sources
of unnecessary work: the VM dispatcher checked every operation family before simple
instructions, while native expression-equality analysis searched for register definitions
before checking whether they could be candidates at all. Both were fixed in
the language; the application's business logic and inputs were unchanged.

Paired old/new dispatcher comparison: 3 warmup and 11 measured
rounds, alternating participant order. On the large configuration with version last,
the median was **11,391 → 9,516 s** (16,5% lower). New-variant range:
9,241–10,588 s; the result above 10 s was retained rather than discarded.
This is local diagnosis on a working computer, not a dedicated D056 runner.

After the second fix, paired tests in three isolated temporary modules produced:

| Cycle of 7 VM+native tests | Before | After |
|---|---:|---:|
| Empty native cache, median of 3 | 14,823 s | 10,951 s |
| Repeated run, median of 6 | 5,628 s | 1,837 s |

Within each pair, the source path is identical; the first participant's native cache is moved
into a neighboring temporary directory before the second. All seven generated C files
matched byte for byte in every pair. The initial harness version compared different
module paths, obtained different identifiers, and stopped; that harness assumption
was corrected. A separate `build --emit c` from the main directory also
produced an identical SHA-256 before/after:
`df48506c776307f99d3ff2909d97a4b2798ce1eb4c35c003b1ea902d2ef52b1e`.

First-launch control: five new minimal C programs took
0,374–0,573 s, then 0,004–0,009 s. A new native configuration-validator executable took
0,375–0,400 s, then 0,005–0,011 s. The delay also reproduces without the Marimay
runtime; this test did not identify a specific macOS service or mechanism. Security
settings were unchanged, and user programs were not executed during build.

**Performance acceptance remains open:** the cold cycle still exceeds 10 s,
the median small repeated run in an additional measurement was 0,305 s, above 0,3 s,
and the first launch of a new native executable exceeds 0,1 s. Repeated conversion of the whole
program for every test and separate native compilation for every test remain
the next areas of work. Do not move to the next utility before resolving the issues;
do not raise budgets or reduce data volumes just to make the table pass.

Raw reports:

```text
5cd8ea0a3663a68da942f4d2688d25b7713f0e228ea0380e422d5a5244cad77a  build/paired-dispatch-last-20260906.json
e0b4d23870c881feed470d957001627562f17e1bc080023d9e759b494fab50cf  build/paired-test-relations-fixed-path-20260906.json
231154571be099ddb4c7586829a1753cc842b81f19c888990cc37802ae2420f5  build/native-startup-control-20260906.json
341129c8e06ba683176c4ebb11477fb04569be01e3cefb931a5511274fdc6632  build/measurements-dispatch-relations-20260906.json
```

## Reusing prepared bytecode

The two preceding optimizations are in language main (`1b6a89f`). The next
optimization removes repeated lowering/encoding/decoding of the whole program for each
test. Preparation happens once per command, with verification before every
test; memory, arguments, streams, and panic state remain separate for each test.

Three paired measurements with the same `tools/compare-test.py`, without parallel builds/tests:

| 7 VM+native tests | `1b6a89f` | Prepared bytecode |
|---|---:|---:|
| Empty native cache, median of 3 | 10,867 s | 10,180 s |
| Repeated run, median of 6 | 1,813 s | 1,243 s |

Every command finished with exactly the same report of seven passing tests; the seven
C files in each pair matched byte for byte. Cold times for the new variant:
10,554 / 10,073 / 10,180 s — **all still above 10 s**. Acceptance is not complete:
the next area to fix is repeated native preparation/build/execution.
Do not move on to the manifest utility; this change also does not resolve the earlier misses
for small runs or the first launch of a new native executable.

Compiler SHA-256: `0a108ed25f4287e24200c9b2e4ae9fb1eccbba3e423215f0078ba6fa8f673645`.
SHA-256 of report `build/paired-test-preparation-20260906.json`:
`bb80ac28dc332ee56896ca4208c33df6fea472566ec4213c922879ef5bacda9c`.
The application's business logic and workloads were unchanged. For the next cold profile,
`tools/profile-cold-test.py` was added: it uses only its own temporary module
without `.mmay` and removes only the state it created after measurement.

A fresh profile after the other checks finished: 4 633 of 7 901 samples
(58,6%) were waiting for the C compiler; 2 347 (29,7%) were waiting for native processes.
Seven C files of 4 045 463 bytes each were generated. This points to repeated compilation
of one program with different entry points; eliminating it is the next step,
not yet implemented by the current bytecode change. All seven tests in the profile passed.

## One native build for all tests

The cause of repeated compilation was removed in the language: one executable selects
the requested test, while every test still runs in a fresh process. On base
`cee30f5`, three new pairs were measured with identical paths and sources within
each pair, an empty native cache before the first run, and two repeats.
Our builds/tests finished before measurement; background applications continued running.

| 7 VM+native tests | `cee30f5` | Shared native executable |
|---|---:|---:|
| Empty native cache, median of 3 | 10,505 s | 1,910 s |
| Cold-run range | 10,381–11,691 s | 1,896–2,013 s |
| Repeated run, median of 6 | 1,254 s | 0,585 s |
| Generated test C files | 7 | 1 |

All three cold runs now meet the existing 10 s budget. The cold cycle
is 5,5 times faster; the warm cycle decreased by 53,3%. Every run matched
the full seven-test report, exit code, and stderr. Test C intentionally changed:
seven separate entry points were replaced by one dispatcher. Schema 2 of the harness explicitly
checks 7 → 1 with `--candidate-native-units 1`; ordinary `build --emit c`
still matches byte for byte before/after within each pair.

Repeating all workloads: small VM — first 0,315 s, repeat median 0,290 s,
but two repeats of 0,322/0,311 s exceed 0,3 s. Large JSON — VM 5,714 s with
version first and 9,744 s with version last; a single run does not establish headroom below 10 s.
A new native executable still requires **0,628 s** on first launch, then
0,0036–0,0100 s. This issue remains unresolved and is not attributed to an identified
macOS service: the mechanism is still unknown. Large-input RSS: 132,7 MiB VM and
87,4 MiB native, against a 256 MiB limit. This is process RSS, not a managed-heap counter.
Do not proceed to manifest before completing the remaining checks/fixes.

Compiler SHA-256:
`b4b5a6c95da1956ef5e696aaacd8d2b9c47a58710669b613efaae16c8cf9e3c2`.
Raw reports:

```text
053ceeb16f369515ec32a64aa94255b9424d24f2aac4b9ae8293bd3340e410f3  build/paired-native-test-build-20260906.json
f66122ae72f6f6313a6cf29969484476db0c3f31b28d7a936d234775cad62fa9  build/measurements-native-test-build-20260906.json
```


## Repeating application workloads on the final candidate

Unchanged `marimay-config` inputs: small VM — first 0,283 s,
seven repeats 0,275–0,289 s; 1 048 459-byte JSON — VM 3,569 s with version
first and 5,051 s with version last, native 0,250/0,331 s. Seven tests
in both engines — 0,5857/0,5713/0,5733 s. Peak RSS: 155 746 304 bytes
VM and 94 683 136 bytes native, against a 256 MiB budget. Every result was checked.

The first launch of a fresh native executable takes **0,524 s against a 0,1 s budget**;
subsequent launches take 0,0038–0,0059 s. This defect remains open. Large inputs
were measured once each: this is local diagnosis of the combined
D089–D095 candidate, not stable Tier 1 acceptance or proof that D095 caused
the JSON speedup. Raw report: `build/measurements-d095-20260907.json`, SHA-256
`6b55ece0106954cb32060c8178695b0f3ff2c434f380bf7d01bb606c93182499`. Application and CLI-alpha acceptance remain open.

Compiler SHA-256:
`2b05ca481917fcf1bf08401a1937e365eab77e602ac07a499f41150db3fa796a`.
