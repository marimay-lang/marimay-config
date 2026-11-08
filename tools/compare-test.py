#!/usr/bin/env python3
"""Compare empty native-cache and repeated test loops in disposable fixture modules."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
FILES = ["mmay.mod", "main.my", "main_test.my", "config/model.my", "command/options.my"]
parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, required=True)
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--candidate-native-units", type=int, choices=(1, 7), default=7,
                    help="Expected generated test programs; 1 explicitly tests the shared executable")
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Отчёт уже существует; выберите новое имя")
participants = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
report = {"schema": "config.paired-test/2", "host": platform.platform(),
          "conditions": "Three pairs of disposable fixture modules, each with no .mmay directory before its first test. Subsequent two runs reuse that module's native cache. Sequential processes; no OS cache eviction. Not a dedicated D056 runner.",
          "sources": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES},
          "binaries": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                       for name, path in participants.items()}, "samples": [],
          "expected_native_units": {"baseline": 7, "candidate": args.candidate_native_units},
          "generated_test_c": [], "identical_ordinary_c": []}
args.output.parent.mkdir(parents=True, exist_ok=True)


def save_report():
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


expected = None
for pair in range(3):
    with tempfile.TemporaryDirectory(prefix="test-cache-probe-", dir=ROOT / "build") as temporary:
        module = Path(temporary) / "module"
        for source in FILES:
            destination = module / source
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source, destination)
        generated = {}
        ordinary = None
        for name in list(participants)[::1 if pair % 2 == 0 else -1]:
            assert not (module / ".mmay").exists()
            for index in range(3):
                command = [str(participants[name]), "test", ".", "--engine", "both"]
                start = time.perf_counter_ns()
                result = subprocess.run(command, cwd=module, capture_output=True, timeout=180)
                elapsed = (time.perf_counter_ns() - start) / 1e9
                item = {"pair": pair, "participant": name, "native_cache_cold": index == 0,
                        "seconds": elapsed, "status": result.returncode,
                        "stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace")}
                report["samples"].append(item)
                save_report()
                assert result.returncode == 0 and not result.stderr and b"7 passed; 0 failed" in result.stdout, item
                if expected is None:
                    expected = result.stdout
                assert result.stdout == expected, item
                print(name, pair, index, round(elapsed, 6), flush=True)
            sources = {str(path.relative_to(module)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in module.rglob("program.c")}
            assert len(sources) == report["expected_native_units"][name], sources
            generated[name] = sources
            # A shared test executable intentionally has a different main. The
            # ordinary build must still emit identical C in the identical path.
            emitted = Path(temporary) / (name + "-ordinary.c")
            result = subprocess.run([str(participants[name]), "build", ".", "--emit", "c",
                                     "--output", str(emitted)], cwd=module, capture_output=True, timeout=180)
            assert result.returncode == 0 and not result.stderr, result
            digest = hashlib.sha256(emitted.read_bytes()).hexdigest()
            if ordinary is None:
                ordinary = digest
            assert digest == ordinary, "Ordinary generated C changed between compilers"
            # Keep source paths identical but give the next participant an empty
            # tool cache. Only this script's temporary generated state is moved.
            (module / ".mmay").rename(Path(temporary) / (name + "-cache"))
        if args.candidate_native_units == 7:
            assert generated["baseline"] == generated["candidate"], "Generated test C changed"
        report["generated_test_c"].append(generated)
        report["identical_ordinary_c"].append(ordinary)
        save_report()
