#!/usr/bin/env python3
"""Compare read/copy/UTF-8/decoder/skip/typed stages, using the same input."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Отчёт уже существует")
contents = args.input.read_bytes()
mmay = shutil.which("mmay")
if not mmay:
    raise SystemExit("mmay не найден")
report = {"input_sha256": hashlib.sha256(contents).hexdigest(),
          "compiler_sha256": hashlib.sha256(Path(mmay).read_bytes()).hexdigest(),
          "input_bytes": len(contents), "stages": {}}
with tempfile.TemporaryDirectory(prefix="stages-", dir=ROOT / "build") as temporary:
    artifact = str(Path(temporary) / "probe")
    built = subprocess.run([mmay, "build", "tools/perf-probe", "--release", "--output", artifact],
                           cwd=ROOT, capture_output=True, timeout=120)
    assert built.returncode == 0, built.stderr
    for engine, prefix in (("vm", [mmay, "run", "tools/perf-probe", "--"]),
                           ("native", [artifact])):
        for stage in ("read", "copy", "utf8", "decoder", "skip", "typed"):
            samples = []
            for _ in range(3):
                start = time.perf_counter()
                result = subprocess.run([*prefix, stage], cwd=ROOT, input=contents,
                                        capture_output=True, timeout=120)
                samples.append(time.perf_counter() - start)
                expected = 43680 if stage == "typed" else len(contents)
                assert result.returncode == 0 and not result.stderr
                assert result.stdout == f"{expected}\n".encode(), (engine, stage, result)
            measured = {"seconds": samples, "median_seconds": statistics.median(samples)}
            report["stages"][engine + "/" + stage] = measured
            print(engine, stage, measured, flush=True)
args.output.write_text(json.dumps(report, indent=2) + "\n")
