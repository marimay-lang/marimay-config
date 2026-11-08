#!/usr/bin/env python3
"""Generate deterministic stress fixtures without touching user configuration."""
import argparse
from pathlib import Path
from measure import dataset

parser = argparse.ArgumentParser()
parser.add_argument("directory", type=Path)
args = parser.parse_args()
args.directory.mkdir(parents=True, exist_ok=False)
for name, contents in (
    ("near-limit-first.json", dataset(43680)),
    ("near-limit-last.json", dataset(43680, True)),
    ("medium.json", dataset(1000)),
):
    destination = args.directory / name
    destination.write_bytes(contents)
    print(destination, len(contents))
