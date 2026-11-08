"""Versioned process-only acceptance mechanics for independent Marimay CLIs.

Vendor this file unchanged beside an application's acceptance adapters.
Business rules, fixtures, output assertions and filesystem checks stay there.
"""

import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess


VERSION = "1"


class Application:
    def __init__(self, root, compiler=None, *, timeout=120):
        if not __debug__:
            raise RuntimeError("acceptance requires enabled Python assertions")
        self.root = Path(root).resolve()
        selected = compiler if compiler is not None else os.environ.get("MMAY", "mmay")
        resolved = shutil.which(str(selected))
        if resolved is None:
            raise FileNotFoundError(f"Marimay compiler not found: {selected}")
        self.compiler = str(Path(resolved).resolve())
        self.timeout = timeout

    def run(self, arguments, *, input=None):
        return subprocess.run(arguments, cwd=self.root, input=input,
                              capture_output=True, timeout=self.timeout)

    def successful(self, arguments):
        result = self.run(arguments)
        if result.returncode != 0 or result.stderr:
            raise AssertionError((arguments, result.returncode,
                                  result.stdout, result.stderr))
        return result.stdout

    def engines(self, directory, name, grants=()):
        if not name or Path(name).name != name or name in (".", ".."):
            raise ValueError("artifact name must be one filename component")
        work = Path(directory).resolve()
        suffix = ".exe" if os.name == "nt" else ""
        result = {"vm": [self.compiler, "run", ".", *grants, "--"]}
        for profile in ("debug", "release"):
            binary = work / (name + "-" + profile + suffix)
            flags = ["--release"] if profile == "release" else []
            self.successful([self.compiler, "build", ".", *grants, *flags,
                             "--output", str(binary)])
            result[profile] = [str(binary)]
        return result

    def compare(self, engines, arguments, status, *, data=None, label=None,
                prepare=None, verify=None):
        """Compare exact bytes/exits and run app-owned checks for every engine.

        prepare() restores a mutable fixture before EACH execution. verify gets
        (engine_name, CompletedProcess) and checks expected output/file effects;
        engine equivalence alone cannot establish application correctness.
        """
        if not engines:
            raise ValueError("acceptance needs at least one engine")
        reference = None
        for engine, prefix in engines.items():
            if prepare is not None:
                prepare()
            result = self.run([*prefix, *arguments], input=data)
            actual = (result.returncode, result.stdout, result.stderr)
            if result.returncode != status:
                raise AssertionError((label, engine, "expected exit", status, actual))
            if reference is not None and actual != reference:
                raise AssertionError((label, engine, "engine divergence", reference, actual))
            if verify is not None:
                verify(engine, result)
            reference = actual
        return reference

    def metadata(self, engines):
        """No ambient environment or application data is collected."""
        return {
            "harness_version": VERSION,
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "platform": platform.platform(),
            "compiler": self.compiler,
            "compiler_sha256": hashlib.sha256(Path(self.compiler).read_bytes()).hexdigest(),
            "engines": {
                name: {"command": list(prefix), "executable_sha256":
                       hashlib.sha256(Path(prefix[0]).read_bytes()).hexdigest()}
                for name, prefix in engines.items()
            },
        }
