#!/usr/bin/env python3
"""Attribute this script's fresh control executable startup on macOS, without changing security."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
assert platform.system() == "Darwin", "macOS diagnostic only"
assert not args.output.exists(), "Choose a new report name"
profile = args.output.with_suffix(".sample.txt").resolve()
assert not profile.exists(), "Choose a new profile name"
args.output.parent.mkdir(parents=True, exist_ok=True)
report = {"schema": "config.startup-trace/1", "host": platform.platform(),
          "conditions": "Own synthetic executables only. First two fresh files run without an observer, third with sample attached before exec. No security changes, OS cache eviction, or application code executed during build.",
          "source_sha256": hashlib.sha256((ROOT / "tools/startup-marker.c").read_bytes()).hexdigest(),
          "samples": []}


def launch(executable, observe=False):
    go_r, go_w = os.pipe()
    out_r, out_w = os.pipe()
    err_r, err_w = os.pipe()
    pid = os.fork()
    if pid == 0:
        try:
            os.close(go_w)
            os.close(out_r)
            os.close(err_r)
            os.dup2(out_w, 1)
            os.dup2(err_w, 2)
            os.close(out_w)
            os.close(err_w)
            if os.read(go_r, 1) != b"x":
                os._exit(125)
            os.close(go_r)
            stamp = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
            os.write(1, (json.dumps({"exec_ns": stamp}) + "\n").encode())
            os.execv(str(executable), [str(executable)])
        except BaseException:
            os._exit(127)
    os.close(go_r)
    os.close(out_w)
    os.close(err_w)
    sampler = None
    waited = False
    try:
        if observe:
            sampler = subprocess.Popen(["sample", str(pid), "2", "1", "-mayDie", "-file", str(profile)],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(0.2)  # Allow attachment before releasing only our child.
        start = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        os.write(go_w, b"x")
        _, status = os.waitpid(pid, 0)
        waited = True
        end = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
        output = os.read(out_r, 16384)
        error = os.read(err_r, 16384)
        assert os.waitstatus_to_exitcode(status) == 0 and not error, (status, output, error)
        before, entered = [json.loads(line) for line in output.splitlines()]
        item = {"observed": observe, "pid": pid, "probe": entered["probe"],
                "exec_to_main_seconds": (entered["entry_ns"] - before["exec_ns"]) / 1e9,
                "main_to_reaped_seconds": (end - entered["entry_ns"]) / 1e9,
                "released_to_reaped_seconds": (end - start) / 1e9}
        if sampler:
            stdout, stderr = sampler.communicate(timeout=20)
            item["sampler"] = {"status": sampler.returncode, "stdout": stdout.decode(), "stderr": stderr.decode()}
        return item
    finally:
        for descriptor in (go_w, out_r, err_r):
            os.close(descriptor)
        if not waited:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            os.waitpid(pid, 0)
        if sampler and sampler.poll() is None:
            sampler.terminate()
            sampler.communicate(timeout=10)


with tempfile.TemporaryDirectory(prefix="startup-trace-", dir=ROOT / "build") as temporary:
    directory = Path(temporary)
    for index in range(3):
        executable = directory / f"marker-{index}"
        built = subprocess.run(["cc", "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
                                f"-DPROBE_ID={index}", str(ROOT / "tools/startup-marker.c"),
                                "-o", str(executable)], capture_output=True, timeout=60)
        assert built.returncode == 0 and not built.stderr, built
        for repetition in range(1 if index == 2 else 3):
            item = launch(executable, observe=index == 2)
            item.update({"round": index, "repetition": repetition,
                         "binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()})
            report["samples"].append(item)
            print(json.dumps(item), flush=True)
    logs = subprocess.run(["/usr/bin/log", "show", "--style", "compact", "--last", "1m",
                           "--predicate", f'eventMessage CONTAINS "{directory.name}"'],
                          capture_output=True, timeout=30)
    report["scoped_host_log"] = {"status": logs.returncode, "stdout": logs.stdout.decode(errors="replace"),
                                  "stderr": logs.stderr.decode(errors="replace")}
if profile.exists():
    report["profile_sha256"] = hashlib.sha256(profile.read_bytes()).hexdigest()
args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
