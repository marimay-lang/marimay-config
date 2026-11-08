#!/usr/bin/env python3
"""Profile one empty-cache test invocation; touch only disposable fixture state."""
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
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
report_path = args.output.with_suffix(".json")
if args.output.exists() or report_path.exists():
    raise SystemExit("Профиль или отчёт уже существует; выберите новое имя")
mmay = shutil.which("mmay")
if not mmay or not shutil.which("sample"):
    raise SystemExit("Нужны mmay и macOS sample")
args.output.parent.mkdir(parents=True, exist_ok=True)
report = {"schema": "config.cold-test-profile/1", "host": platform.platform(),
          "compiler": {"path": mmay, "sha256": hashlib.sha256(Path(mmay).read_bytes()).hexdigest()},
          "sources": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}}
with tempfile.TemporaryDirectory(prefix="test-profile-", dir=ROOT / "build") as temporary:
    module = Path(temporary)
    for name in FILES:
        destination = module / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    assert not (module / ".mmay").exists()
    command = [mmay, "test", ".", "--engine", "both"]
    report["command"] = command
    start = time.perf_counter_ns()
    child = subprocess.Popen(command, cwd=module, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        sampled = subprocess.run(["sample", str(child.pid), "30", "1", "-mayDie",
                                  "-file", str(args.output.resolve())],
                                 capture_output=True, timeout=40)
        output, error = child.communicate(timeout=180)
        report.update(seconds_including_sampler=(time.perf_counter_ns() - start) / 1e9,
                      status=child.returncode, stdout=output.decode(errors="replace"),
                      stderr=error.decode(errors="replace"), sample_status=sampled.returncode)
        report["generated_c"] = {str(path.relative_to(module)): {"bytes": path.stat().st_size,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                                 for path in module.rglob("program.c")}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        assert child.returncode == 0 and not error and b"7 passed; 0 failed" in output
        assert sampled.returncode == 0 and args.output.is_file()
        assert len(report["generated_c"]) == 7
    finally:
        if child.poll() is None:
            child.terminate()
            child.communicate(timeout=10)
