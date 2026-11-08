#!/usr/bin/env python3
"""Local paired VM diagnosis; this desktop is not a dedicated D056 release runner."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--baseline", type=Path, required=True)
parser.add_argument("--candidate", type=Path, required=True)
parser.add_argument("--input", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Отчёт уже существует; выберите новое имя")
participants = {"baseline": args.baseline.resolve(), "candidate": args.candidate.resolve()}
data = args.input.read_bytes()
report = {"schema": "config.paired-vm/1", "host": platform.platform(),
          "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip(),
          "initial_load": os.getloadavg(),
          "conditions": "Sequential fresh processes; 3 warmup rounds, 11 measured rounds; alternating participant order. No deliberate OS cache eviction or background application termination. Exploratory desktop evidence, not a dedicated D056 runner.",
          "input_bytes": len(data), "input_sha256": hashlib.sha256(data).hexdigest(),
          "binaries": {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                       for name, path in participants.items()},
          "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "samples": []}
expected = '{"ok":true,"message":"Конфиг корректен.","location":"$"}'.encode()
for index in range(14):
    for name in list(participants)[::1 if index % 2 == 0 else -1]:
        command = [str(participants[name]), "run", ".", "--", "validate", "-", "--json"]
        start = time.perf_counter_ns()
        result = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=60)
        elapsed = (time.perf_counter_ns() - start) / 1e9
        item = {"participant": name, "round": index, "warmup": index < 3,
                "seconds": elapsed, "command": command, "status": result.returncode,
                "stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace")}
        report["samples"].append(item)
        print(name, index, round(elapsed, 6), flush=True)
        assert (result.returncode, result.stdout, result.stderr) == (0, expected, b""), item
report["summary"] = {}
for name in participants:
    values = [item["seconds"] for item in report["samples"] if item["participant"] == name and not item["warmup"]]
    median = statistics.median(values)
    report["summary"][name] = {"median_seconds": median,
                                "mad_seconds": statistics.median(abs(value - median) for value in values),
                                "min_seconds": min(values), "max_seconds": max(values)}
report["final_load"] = os.getloadavg()
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(report["summary"]), flush=True)
