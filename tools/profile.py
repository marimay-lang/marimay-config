#!/usr/bin/env python3
"""Sample only the validation process launched by this script (macOS)."""
import argparse
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path)
parser.add_argument("--mode", choices=["validate", "test"], default="validate")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    raise SystemExit("Профиль уже существует; выберите новое имя")
mmay = shutil.which("mmay")
if not mmay or not shutil.which("sample"):
    raise SystemExit("Нужны mmay и macOS sample")
args.output.parent.mkdir(parents=True, exist_ok=True)
if args.mode == "validate" and args.input is None:
    parser.error("--input требуется для validate")
from contextlib import nullcontext
command = ([mmay, "run", ".", "--", "validate", "-", "--json"]
           if args.mode == "validate" else [mmay, "test", ".", "--engine", "both"])
with (args.input.open("rb") if args.input else nullcontext(subprocess.DEVNULL)) as contents:
    child = subprocess.Popen(command,
                             cwd=ROOT, stdin=contents, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    try:
        sampled = subprocess.run(["sample", str(child.pid), "10", "1", "-mayDie",
                                  "-file", str(args.output.resolve())],
                                 capture_output=True, timeout=30)
        output, error = child.communicate(timeout=120)
        print("sample:", sampled.returncode, sampled.stderr.decode(errors="replace"))
        print(args.mode, child.returncode, output.decode(), error.decode())
        assert child.returncode == 0 and not error
        assert (output == '{"ok":true,"message":"Конфиг корректен.","location":"$"}'.encode()
                if args.mode == "validate" else b"7 passed; 0 failed" in output)
        assert args.output.is_file()
    finally:
        if child.poll() is None:
            child.terminate()
            child.communicate(timeout=10)
