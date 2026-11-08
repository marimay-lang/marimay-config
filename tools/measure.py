#!/usr/bin/env python3
"""Sequential, reproducible CLI workload measurements; no application logic."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = ROOT.parent.parent / "marimay"


def run(arguments, *, data=None, timeout=60):
    start = time.perf_counter()
    try:
        result = subprocess.run(arguments, cwd=ROOT, input=data, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"seconds": time.perf_counter() - start, "timeout": timeout}
    return {
        "seconds": time.perf_counter() - start,
        "status": result.returncode,
        "stdout": result.stdout.decode("utf-8", errors="replace"),
        "stderr": result.stderr.decode("utf-8", errors="replace"),
    }


def dataset(count, version_last=False):
    value = {
        "version": 2,
        "project": {"name": "Проект 🌿", "root": "."},
        "scan": {"extensions": [".my", ".json"], "maxFileBytes": 1024,
                 "requiredFiles": [f"sources/file-{i:05d}.my" for i in range(count)]},
    }
    if version_last:
        value["version"] = value.pop("version")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def record(report, name, arguments, data, samples):
    results = [run(arguments, data=data) for _ in range(samples)]
    for item in results:
        item["ok"] = item.get("status") == 0 and not item.get("stderr")
        if item["ok"] and data is not None:
            item["ok"] = item["stdout"] == '{"ok":true,"message":"Конфиг корректен.","location":"$"}'
        elif item["ok"]:
            item["ok"] = "7 passed; 0 failed" in item["stdout"]
    successful = [item["seconds"] for item in results if item["ok"]]
    report["measurements"][name] = {
        "command": arguments,
        "input_bytes": len(data) if data is not None else None,
        "input_sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
        "samples": results,
        "median_seconds": statistics.median(successful) if successful else None,
        "all_passed": all(item["ok"] for item in results),
    }
    print(name, json.dumps({"seconds": [round(item["seconds"], 4) for item in results],
                           "all_passed": all(item["ok"] for item in results)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Выходной отчёт уже существует; выберите новое имя.")
    mmay = shutil.which(os.environ.get("MMAY", "mmay"))
    if mmay is None:
        raise SystemExit("mmay не найден")
    language_revision = subprocess.check_output(["git", "-C", str(LANGUAGE), "rev-parse", "HEAD"], text=True).strip()
    language_dirty = subprocess.check_output(["git", "-C", str(LANGUAGE), "status", "--porcelain"], text=True)
    sources = [ROOT / "mmay.mod", *sorted(ROOT.rglob("*.my"))]
    source_hashes = {str(file.relative_to(ROOT)): hashlib.sha256(file.read_bytes()).hexdigest()
                     for file in sources if "build" not in file.relative_to(ROOT).parts}
    report = {
        "schema": "marimay-config.measurements/1",
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": platform.platform(),
        "cpu": subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
               if platform.system() == "Darwin" else platform.machine(),
        "language_revision": language_revision, "language_dirty": bool(language_dirty),
        "compiler": mmay, "compiler_sha256": hashlib.sha256(Path(mmay).read_bytes()).hexdigest(),
        "compiler_doctor": run([mmay, "doctor"]),
        "application_source_sha256": source_hashes,
        "conditions": "Sequential fresh processes. No deliberate OS cache eviction. First measured run is not a disk-cold claim. Normal desktop background applications remain running; no fully idle-host claim.",
        "budgets": {"run_first_seconds": 1, "run_repeat_seconds": 0.3,
                    "native_small_seconds": 0.1, "test_both_seconds": 10,
                    "vm_near_limit_seconds": 10, "native_near_limit_seconds": 1,
                    "peak_rss_bytes": 268435456},
        "measurements": {},
    }
    vm = [mmay, "run", ".", "--", "validate", "-", "--json"]
    small = dataset(0)
    record(report, "run_first", vm, small, 1)
    record(report, "run_repeat", vm, small, 7)
    build = ROOT / "build"
    build.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="measure-", dir=build) as directory:
        binary = Path(directory) / "marimay-config"
        report["native_build"] = run([mmay, "build", ".", "--release", "--output", str(binary)])
        assert report["native_build"].get("status") == 0, report["native_build"]
        native = [str(binary), "validate", "-", "--json"]
        record(report, "native_small", native, small, 7)
        for name, contents in (("medium", dataset(1000)),
                               ("near_limit_first", dataset(43680)),
                               ("near_limit_last", dataset(43680, True))):
            assert len(contents) <= 1048576
            record(report, "vm_" + name, vm, contents, 1)
            record(report, "native_" + name, native, contents, 1)
        record(report, "test_both", [mmay, "test", ".", "--engine", "both"], None, 3)
        contents = dataset(43680)
        for name, command in (("vm", vm), ("native", native)):
            flags = ["-l"] if platform.system() == "Darwin" else ["-v"]
            result = run(["/usr/bin/time", *flags, *command], data=contents)
            result["output_matches"] = result.get("stdout") == '{"ok":true,"message":"Конфиг корректен.","location":"$"}'
            pattern = r"(\d+)\s+maximum resident set size" if platform.system() == "Darwin" else r"Maximum resident set size \(kbytes\): (\d+)"
            match = re.search(pattern, result.get("stderr", ""))
            result["peak_rss_bytes"] = int(match.group(1)) * (1 if platform.system() == "Darwin" else 1024) if match else None
            report["measurements"][name + "_near_limit_rss"] = result
            print(name + "_near_limit_rss", result["peak_rss_bytes"], flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print("report:", args.output)


if __name__ == "__main__":
    main()
