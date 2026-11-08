#!/usr/bin/env python3
"""Process-only acceptance harness; application behavior lives in Marimay."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from measure import dataset
from mmay_acceptance import Application


ROOT = Path(__file__).resolve().parents[1]
HARNESS = Application(ROOT)
MMAY = HARNESS.compiler
invoke = HARNESS.run
successful = HARNESS.successful


def main():
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    source = (ROOT / "fixtures/v1.json").read_bytes()
    expected = (ROOT / "fixtures/v2.json").read_bytes().removesuffix(b"\n")
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="acceptance-", dir=build) as directory:
        work = Path(directory)
        grants = ["--allow-read", str(ROOT), "--allow-write", str(work)]
        engines = HARNESS.engines(work, "config", grants)
        harness_metadata = HARNESS.metadata(engines)
        output = work / "output.json"
        cases = [
            (["--help"], None, 0),
            ([], None, 2),
            (["wrong", "-"], b"", 2),
            (["validate", "-", "--output", str(output)], source, 2),
            (["migrate", "-", "--in-place"], source, 2),
            (["migrate", "-", "--json"], source, 2),
            (["validate", "-", "--max-bytes", "0"], source, 2),
            (["validate", "-", "--max-bytes", "NaN"], source, 2),
            (["validate", "-", "--json"], source, 0),
            (["validate", "fixtures/v2.json"], None, 0),
            (["validate", "-", "--max-bytes", str(len(source))], source, 0),
            (["validate", "-", "--max-bytes", str(len(source) - 1)], source, 1),
            (["validate", str(work / "missing.json")], None, 1),
            (["migrate", "-"], source, 0),
            (["migrate", "-"], expected, 0),
        ]
        malformed = [
            b"", b"{}", b"null", b"\xff", b'{"version":3}',
            b'{"version":1,"version":1}', source + b"{}",
            b'{"version":2,"project":{"name":false}}',
            b'{"version":1,"extra":null}',
            source.replace(b'".json"', b'".my"'),
            source.replace(b'"maxFileBytes":1024', b'"maxFileBytes":0'),
        ]
        cases += [(["validate", "-", "--json"], data, 1) for data in malformed]
        large = json.loads(expected)
        large["scan"]["requiredFiles"] = [f"dir/file-{i}.my" for i in range(1000)]
        large_bytes = json.dumps(large, ensure_ascii=False).encode()
        cases.append((["validate", "-", "--json"], large_bytes, 0))
        near_limit = dataset(43680)
        assert len(near_limit) == 1048459
        at_limit = near_limit + b" " * (1048576 - len(near_limit))
        cases += [
            (["validate", "-", "--json"], near_limit, 0),
            (["validate", "-", "--json"], dataset(43680, True), 0),
            (["validate", "-", "--json"], at_limit, 0),
            (["validate", "-", "--json"], at_limit + b" ", 1),
            (["validate", "-", "--json"], near_limit[:-1] + b"!", 1),
        ]
        for number, (arguments, data, status) in enumerate(cases):
            def verify_case(engine, result):
                actual = (result.returncode, result.stdout, result.stderr)
                assert not (result.stderr if status == 0 else result.stdout), (number, engine, actual)
                if "--json" in arguments and status != 2:
                    report = json.loads(result.stdout if status == 0 else result.stderr)
                    assert report["ok"] == (status == 0)
                    assert isinstance(report["location"], str)
                if arguments == ["migrate", "-"]:
                    assert result.stdout == expected
            HARNESS.compare(engines, arguments, status, data=data,
                            label=number, verify=verify_case)
        for engine, prefix in engines.items():
            output.write_bytes(b"original")
            result = invoke([*prefix, "migrate", "-", "--output", str(output), "--json"], input=source)
            assert result.returncode == 0 and not result.stderr, (engine, result)
            assert json.loads(result.stdout)["ok"] and output.read_bytes() == expected
            for bad_input, extra in ((b"{}", []), (source, ["--max-bytes", str(len(source))])):
                output.write_bytes(b"original")
                result = invoke([*prefix, "migrate", "-", "--output", str(output), *extra], input=bad_input)
                assert result.returncode == 1 and output.read_bytes() == b"original", (engine, result)
            output.write_bytes(source)
            result = invoke([*prefix, "migrate", str(output), "--in-place"])
            assert result.returncode == 0 and output.read_bytes() == expected, (engine, result)
            output.write_bytes(b"{}")
            result = invoke([*prefix, "migrate", str(output), "--in-place"])
            assert result.returncode == 1 and output.read_bytes() == b"{}", (engine, result)
            result = invoke([*prefix, "migrate", "-", "--output", str(work / "absent/out.json")], input=source)
            assert result.returncode == 1 and not (work / "absent").exists(), (engine, result)
            read_fd, write_fd = os.pipe()
            os.close(read_fd)
            try:
                child = subprocess.Popen([*prefix, "migrate", "-"], cwd=ROOT,
                    stdin=subprocess.PIPE, stdout=write_fd, stderr=subprocess.PIPE)
            finally:
                os.close(write_fd)
            _, error = child.communicate(source, timeout=120)
            assert child.returncode == 1 and error, (engine, child.returncode, error)
        denied = work / "config-denied"
        successful([MMAY, "build", ".", "--release", "--output", str(denied)])
        for prefix in ([MMAY, "run", ".", "--"], [str(denied)]):
            result = invoke([*prefix, "validate", "fixtures/v1.json"])
            assert result.returncode == 1 and not result.stdout and result.stderr
            output.write_bytes(b"original")
            result = invoke([*prefix, "migrate", "-", "--output", str(output)], input=source)
            assert result.returncode == 1 and output.read_bytes() == b"original"
        assert (ROOT / "fixtures/v1.json").read_bytes() == source
        report_path = build / f"process-acceptance-harness-v1-{time.time_ns()}.json"
        report_path.write_text(json.dumps({"schema": "marimay-config.process-acceptance/1",
            "harness": harness_metadata, "exact_parity_cases": len(cases),
            "additional_checks": ["atomic", "denied", "broken-pipe"],
            "elapsed_seconds": time.monotonic() - start}, ensure_ascii=False, indent=2) + "\n")
        print(f"report: {report_path}")
        print(f"acceptance: {len(cases)} exact-parity cases × 3 engines; atomic/denied/broken-pipe checks passed")
        print(f"elapsed: {time.monotonic() - start:.2f}s (correctness run, not a latency baseline)")


if __name__ == "__main__":
    main()
