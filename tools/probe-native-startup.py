#!/usr/bin/env python3
"""Compare fresh/repeated process startup; no security settings or cache eviction."""
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
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Отчёт уже существует; выберите новое имя")
mmay = shutil.which("mmay")
cc = shutil.which("cc")
assert mmay and cc
report = {"schema": "config.native-startup/1", "host": platform.platform(),
          "compiler_sha256": hashlib.sha256(Path(mmay).read_bytes()).hexdigest(),
          "cc_version": subprocess.check_output([cc, "--version"], text=True),
          "conditions": "Sequential fresh processes, no OS cache eviction or security changes.",
          "samples": []}


def run(command, data, expected):
    start = time.perf_counter_ns()
    result = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=120)
    elapsed = (time.perf_counter_ns() - start) / 1e9
    assert (result.returncode, result.stdout, result.stderr) == (0, expected, b""), result
    return elapsed


ROOT.joinpath("build").mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="native-startup-", dir=ROOT / "build") as temporary:
    directory = Path(temporary)
    for index in range(5):
        # Compiling a trivial C program provides a control without Marimay's runtime.
        plain = directory / f"plain-{index}"
        source = b'#include <stdio.h>\nint main(void) { return puts("ok") < 0; }\n'
        compile_result = subprocess.run([cc, "-std=c17", "-O2", "-x", "c", "-", "-o", str(plain)],
                                        input=source, capture_output=True, timeout=120)
        assert compile_result.returncode == 0, compile_result
        native = directory / f"config-{index}"
        build = subprocess.run([mmay, "build", ".", "--release", "--output", str(native)],
                               cwd=ROOT, capture_output=True, timeout=120)
        assert build.returncode == 0 and not build.stderr, build
        data = ROOT.joinpath("fixtures/v2.json").read_bytes()
        expected = '{"ok":true,"message":"Конфиг корректен.","location":"$"}'.encode()
        # Alternate participant order without mixing first and repeated samples.
        participants = [("plain_c", [str(plain)], None, b"ok\n"),
                        ("config", [str(native), "validate", "-", "--json"], data, expected)]
        for name, command, contents, output in participants[::1 if index % 2 == 0 else -1]:
            times = [run(command, contents, output) for _ in range(3)]
            item = {"participant": name, "round": index, "seconds": times,
                    "binary_bytes": Path(command[0]).stat().st_size,
                    "binary_sha256": hashlib.sha256(Path(command[0]).read_bytes()).hexdigest()}
            report["samples"].append(item)
            print(json.dumps(item), flush=True)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
