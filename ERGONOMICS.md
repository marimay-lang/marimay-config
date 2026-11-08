# Ergonomics log

> Historical record: observations, revisions and acceptance status below refer to
> the dated runs. They do not describe a new verification of the current checkout.

Observations from 2026-09-06, initial implementation, using a compiler based on `3482467`
with local JSON metadata changes. These are open findings, not a claim that
the language is ready. CP42 owns their review; startup/test measurements relate to CP41.

## E01 — Handling `Result<void, Error>` with match

Status on 2026-09-07: fixed by D092 and rechecked on macOS arm64.
Five artificial bool/discard constructs were replaced with void-match; error
handling was preserved. The 7 source tests passed in both engines, along with
32 process scenarios on VM/Debug native/Release native. The original observation below is historical.

In the version-reading loop, the natural expression `match json.skipValue(decoder) { Ok(_) => {},
Err(error) => { return Err(json.atField(error, name)); }, };` produces `T0016`:
reachable block match arm does not end with a value.
Workaround in `config/model.my`: `const _ = match ... { Ok(_) => true, ... };`.
The consistency of statement/void contexts needs clarification, and this expression
needs improvement without changing error-return semantics. Impact: medium, recurring noise.

## E02 — expect cannot be used in an ordinary test helper

Status on 2026-09-07: D093 allows ordinary helpers in `_test.my`.
`rejected` uses `expect.equal`; all-targets check passed, along with the 7 source
tests in both engines and 32 process scenarios × 3 engines/profiles.
The restriction on definitions in production `.my` files remains. The historical
reproducer follows; the missing location display is recorded separately in E09.

A helper `fn rejected(...)` with `expect.equal(...)` in `_test.my` produces `R0007`:
expect helpers are available only inside @test and @fuzz functions.
Workaround: ordinary `if` and `panic`, which provide less useful reporting than built-in expectations.
An explicit contract for reusable test assertions is needed. Impact: medium.

## E03 — Overloaded mapper and context before ?

Status on 2026-09-07: fixed locally by D094. The application uses
`cli.parse(parser(), arguments).mapError(cli.message)?`; installed
doctor/fmt/check passed, along with 7 source tests and 32 process scenarios × 3 engines.
Error context is limited to the direct operand of `?`; T and U are independent,
and ordinary shadowing is preserved. The historical reproducer follows.

`cli.parse(...).mapError(cli.message)?` produces `T0002`: mapper must be a unary
visible function. `mapError((error) => cli.message(error))?` is also rejected:
omitted result type requires an expected Result type. The working expression is
`mapError((error): string => cli.message(error))?`. Owner: checker/mapError;
check the contract for selecting an overload by its expected signature and
the error context from the surrounding Result before `?`. Impact: medium.

## E04 — Version discovery requires a separate pass

Strict typed decoding is convenient after selecting a version, but selecting Version1 or
Configuration requires a `readVersion` cursor followed by a new decode from the start.
The schema accepts fields in any order; the prefix before version may be large.
The workaround is explicit and bounded. Measure its cost and compare explicit codec APIs;
do not add an unbounded DOM solely for this case. Impact: investigate.

## E05 — Localization and structured diagnostics

JSON provides a path and byte span, but there is no universal position accessor;
complete Russian localization requires a large match over all Error variants.
The application currently uses json.message with a Russian prefix; cli/fs/io errors
are also partly in English. Agree on a small diagnostic-data API and convenient
localization without copying the enum into every utility. Impact: medium.

## E06 — Set mutations and manual indices

Duplicate checks read well, but insertion requires `const _ = set.add(value)`;
a separate loop counter supplies the index in a message. This relates to
planned mutation/collection contracts and Option-loop in CP42. API changes
must not silently discard a useful insertion result or an expected error.

## E07 — Successful write without flush does not guarantee pipe delivery

A process test with an already closed pipe reader initially returned code 0 rather than
the expected 1 for a small JSON response. This matches the explicit flush contract in D075:
a buffered stdout error appears at flush. The application was fixed:
stdout/stderr are explicitly flushed at the result boundary, and errors affect
the exit code. This regression is included in process acceptance. Document the pattern
for the other CLIs, especially grep/logstats; this is an application fix, not new
I/O semantics or a reason for the runner to hide a write error.

Every finding requires a decision or explicit disposition and a recheck of
the affected application before closing the portfolio. Acceptance results and measurements
will be recorded separately with exact revisions.

## E08 — A hidden VM limit rejects a valid configuration

Status: D087 fixes the local check; language CI is pending. There is no application
workaround: the same input is accepted by VM, debug native, and release native.
Baseline on `f53b289`: 43 680 unique requiredFiles, 1 048 459 bytes,
with permitted string lengths and element counts. Native successfully validates both
version-field orders; VM terminates with I0002/70. LLDB shows
`MMAY_BYTECODE_RUN_STEP_LIMIT`, exactly 10 000 000 instructions in one frame,
at depth 4. This is neither a JSON limit violation nor a schema error.

Owner: CLI/VM policy; severity: acceptance blocker. D087
separates ordinary local execution from a finite embedded-VM budget.
Do not treat a fast failing exit as a successful measurement, reduce
the configuration, or bypass the verifier. The original dataset and results are retained in
`build/measurements-baseline-20260906.json`; the generator is `tools/measure.py`.
Regressions were added to `tools/acceptance.py`: both field orders, exactly 1 MiB,
one byte over the limit, and an invalid final token. All 32 process
scenarios passed on three engines/profiles, including the earlier atomic and I/O tests.

New measurements must use the same bytes and check the complete
successful result. Separate open questions remain: the first native
launch (0,60 s), the first test cycle (14,60 s), and other resource boundaries.

## E09 — Panic position is lost in the brief test report

Status on 2026-09-07: D095 locally displays the defining helper and complete
line/column range, including generics and different files. VM/native/both
compare identical lines containing the location. The loss of stderr before
panic was also fixed: the former B0007/5 on identical execution now becomes an ordinary
matching test failure/1. Full Release 73/73 and focused Debug/ASan+UBSan passed;
Linux ASan+UBSan+LSan passed under M2 emulation. The repeated seven-test cycle
was measured: 0,538 → 0,553 s; test executable size 1 404 672 → 1 780 768 bytes. Full
stack/suppressed-panic printing is outside this fix. Historical observation:

Found during D093 acceptance: a helper with `expect.equal(1, 2)` retains exact
symbol/span/call frames in MIR/VM/native, but `mmay test --engine both` prints
only `panic[G4004]: expect.equal failed: values differ at root`, without the helper's
file and line. The built-in human report and CLI observation comparison require
separate work; owners are `cli_test_program.c` and native executable
failure reporting. Exact matching locations across files,
generic helpers, Unicode/spaces in paths, and a negative regression are required. D093
removes the helper restriction but does not close this finding.
