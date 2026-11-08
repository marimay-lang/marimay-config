#!/usr/bin/env python3
"""Real POSIX filesystem acceptance; no application logic or mocked host calls."""
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import tempfile
import time

from acceptance import HARNESS, MMAY, ROOT


def main():
    if os.name != "posix" or os.geteuid() == 0:
        raise SystemExit("This acceptance requires an unprivileged POSIX account")
    started = time.monotonic()
    source = (ROOT / "fixtures/v1.json").read_bytes()
    expected = (ROOT / "fixtures/v2.json").read_bytes().removesuffix(b"\n")
    records = []
    # Keep denied data outside the source discovery tree. Resolve macOS /var
    # to its physical spelling so the fixture itself has no ambient symlink.
    with tempfile.TemporaryDirectory(prefix="marimay-config-files-") as temporary:
        work = Path(temporary).resolve()
        allowed = work / "разрешено с пробелами"
        outside = work / "outside"
        allowed.mkdir()
        outside.mkdir()
        original = allowed / "исходник.json"
        original.write_bytes(source)
        outsider = outside / "outside.json"
        outsider.write_bytes(source)
        grants = ["--allow-read", str(allowed), "--allow-write", str(allowed)]
        engines = HARNESS.engines(work, "config", grants)
        harness_metadata = HARNESS.metadata(engines)

        def compare(name, arguments, status, *, data=None, prepare=lambda: None,
                    verify=lambda: None):
            def verify_case(engine, result):
                actual = (result.returncode, result.stdout, result.stderr)
                assert not (result.stderr if status == 0 else result.stdout), (name, engine, actual)
                payload = result.stdout if status == 0 else result.stderr
                try:
                    report = json.loads(payload)
                except json.JSONDecodeError as error:
                    raise AssertionError((name, engine, actual)) from error
                assert report["ok"] == (status == 0) and report["location"] == "$", (name, report)
                verify()
            reference = HARNESS.compare(engines, [*arguments, "--json"], status,
                data=data, label=name, prepare=prepare, verify=verify_case)
            records.append({"name": name, "exit": status,
                "stdout": reference[1].decode(), "stderr": reference[2].decode()})

        def unchanged():
            assert original.read_bytes() == source and outsider.read_bytes() == source
            assert not list(allowed.rglob("*.mmay-tmp-*"))

        compare("unicode-space-path", ["validate", str(original)], 0, verify=unchanged)
        # Every denied path is lexically inside the granted root. Targets may be
        # inside or outside it; the existing D077 contract rejects links in both.
        links = {
            "relative-file": (Path(original.name), False),
            "outside-file": (outsider, False),
            "dangling-file": (Path("missing-target.json"), False),
        }
        for name, (target, directory) in links.items():
            link = allowed / (name + ".json")
            link.symlink_to(target, target_is_directory=directory)
            def intact(link=link, target=target):
                unchanged()
                assert link.is_symlink() and os.readlink(link) == str(target)
                assert not (allowed / "missing-target.json").exists()
            compare(name + "-read", ["validate", str(link)], 1, verify=intact)
            compare(name + "-write", ["migrate", "-", "--output", str(link)],
                1, data=source, verify=intact)
            compare(name + "-in-place", ["migrate", str(link), "--in-place"],
                1, verify=intact)
        real_dir = allowed / "real-directory"
        real_dir.mkdir()
        (real_dir / "input.json").write_bytes(source)
        for name, target, filename in (("inside-parent", real_dir, "input.json"),
                ("outside-parent", outside, "outside.json")):
            link = allowed / name
            link.symlink_to(target, target_is_directory=True)
            def parent_intact(link=link):
                unchanged()
                assert link.is_symlink()
                assert (real_dir / "input.json").read_bytes() == source
            compare(name + "-read", ["validate", str(link / filename)], 1, verify=parent_intact)
            compare(name + "-write", ["migrate", "-", "--output", str(link / filename)],
                1, data=source, verify=parent_intact)
        compare("directory-read", ["validate", str(real_dir)], 1, verify=unchanged)
        compare("directory-write", ["migrate", "-", "--output", str(real_dir)],
            1, data=source, verify=unchanged)
        fifo = allowed / "fifo"
        os.mkfifo(fifo, 0o600)
        compare("fifo-read", ["validate", str(fifo)], 1, verify=unchanged)
        compare("fifo-write", ["migrate", "-", "--output", str(fifo)],
            1, data=source, verify=unchanged)
        assert stat.S_ISFIFO(fifo.lstat().st_mode)

        unreadable = allowed / "unreadable.json"
        unreadable.write_bytes(source)
        unreadable.chmod(0)
        try:
            try:
                unreadable.read_bytes()
            except PermissionError:
                pass
            else:
                raise AssertionError("OS did not enforce read denial")
            compare("os-read-denied", ["validate", str(unreadable)], 1)
        finally:
            unreadable.chmod(0o600)
        assert unreadable.read_bytes() == source
        blocked = allowed / "unsearchable"
        blocked.mkdir()
        hidden = blocked / "input.json"
        hidden.write_bytes(source)
        blocked.chmod(0o600)
        try:
            try:
                hidden.stat()
            except PermissionError:
                pass
            else:
                raise AssertionError("OS did not enforce directory search denial")
            compare("os-search-denied", ["validate", str(hidden)], 1)
        finally:
            blocked.chmod(0o700)
        assert hidden.read_bytes() == source
        readonly = allowed / "unwritable"
        readonly.mkdir()
        retained = readonly / "existing.json"
        retained.write_bytes(b"original")
        readonly.chmod(0o500)
        try:
            try:
                (readonly / "probe").write_bytes(b"probe")
            except PermissionError:
                pass
            else:
                raise AssertionError("OS did not enforce directory write denial")
            def retained_intact():
                assert retained.read_bytes() == b"original"
                assert sorted(p.name for p in readonly.iterdir()) == ["existing.json"]
            for name in ("existing.json", "new.json"):
                compare("os-write-denied-" + name,
                    ["migrate", "-", "--output", str(readonly / name)],
                    1, data=source, verify=retained_intact)
        finally:
            readonly.chmod(0o700)
        output = allowed / "normal-output.json"
        def migrated():
            unchanged()
            assert output.read_bytes() == expected
        compare("atomic-replace-success", ["migrate", "-", "--output", str(output)],
            0, data=source, prepare=lambda: output.write_bytes(b"original"), verify=migrated)
        unchanged()
    result = {"schema": "marimay-config.files-acceptance/1", "platform": platform.platform(),
        "harness": harness_metadata,
        "uid": os.geteuid(), "compiler_sha256": hashlib.sha256(Path(MMAY).read_bytes()).hexdigest(),
        "elapsed_seconds": time.monotonic() - started, "engines": list(engines), "cases": records,
        "scope": "static symlink cases and real POSIX permissions; no concurrent namespace-race claim"}
    report_path = ROOT / "build" / f"files-acceptance-harness-v1-{time.time_ns()}.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"report: {report_path}")
    print(f"filesystem acceptance: {len(records)} exact-parity cases × 3 engines; real OS denials and static symlinks passed")


if __name__ == "__main__":
    main()
