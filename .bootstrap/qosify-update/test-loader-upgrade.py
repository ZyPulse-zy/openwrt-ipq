#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise unchanged production loaders across real old/new pinned map ABIs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lab", type=Path, required=True)
parser.add_argument("--bpftool", type=Path, required=True)
args = parser.parse_args()
lab = args.lab.resolve(strict=True)
for ns in ["net", "mnt"]:
    parent = os.environ.get("QOSIFY_PARENT_" + ns.upper() + "NS")
    if os.geteuid() or not parent or parent == os.readlink("/proc/self/ns/" + ns):
        raise SystemExit(
            "Refusing loader test without private root network and mount namespaces"
        )
bpftool = args.bpftool.resolve(strict=True)


def run(*words, check=True):
    result = subprocess.run([str(w) for w in words], capture_output=True, text=True)
    if check and result.returncode:
        print(result.stdout, result.stderr, flush=True)
        result.check_returncode()
    return result


records = []


def map_info(path):
    data = json.loads(run(bpftool, "-j", "map", "show", "pinned", path).stdout)
    return data[0] if isinstance(data, list) else data


run("mount", "--make-rprivate", "/")
with tempfile.TemporaryDirectory(prefix="qosify-upgrade-") as directory:
    pins = Path(directory) / "pins"
    pins.mkdir()
    run("mount", "-t", "bpf", "bpf", pins)
    run("mount", "--bind", pins, "/sys/fs/bpf")
    try:
        previous = []
        for phase, label, action in [
            ("baseline", "baseline", "leave"),
            ("upgrade", "candidate", "leave"),
            ("restart-and-stop", "candidate", "stop"),
        ]:
            result = run(
                lab / (label + "-loader"),
                lab / (label + "-artifacts/qosify-bpf.o"),
                action,
            )
            programs = [json.loads(line) for line in result.stdout.splitlines()]
            types = programs.pop(0)["header_sizes"]
            assert len(programs) == 4 and {p["flags"] for p in programs} == {0, 1, 2, 3}
            assert all(p["actual_kernel_flags"] == p["flags"] for p in programs)
            for item in previous:
                assert (
                    run(
                        bpftool, "prog", "show", "id", item["id"], check=False
                    ).returncode
                    != 0
                ), "Old program retained"
            if action == "stop":
                assert not list(pins.iterdir()), "Production stop left private pins"
                for item in programs:
                    assert (
                        run(
                            bpftool, "prog", "show", "id", item["id"], check=False
                        ).returncode
                        != 0
                    )
                maps = {}
            else:
                maps = {
                    name: map_info(pins / "qosify_data" / name)
                    for name in ["class_map", "ipv4_map", "ipv6_map"]
                }
                assert all(
                    maps[name]["bytes_value"] == size for name, size in types.items()
                ), (types, maps)
                expected = {"qosify_" + p["suffix"] for p in programs} | {"qosify_data"}
                assert {p.name for p in pins.iterdir()} == expected
            records.append(
                dict(
                    phase=phase,
                    programs=programs,
                    maps=maps,
                    compiled_header_sizes=types,
                    old_programs_gone=True,
                )
            )
            previous = programs
    finally:
        run("umount", "/sys/fs/bpf")
        run("umount", pins)
proof = dict(
    passed=True,
    phases=records,
    scope="Complete original/current production loader.c, real SDK-packaged BPF objects, actual kernel flags/maps/pins; only input object path overridden; private root net/mount namespaces; no full daemon/ubus/firmware or production deployment",
)
(lab / "loader-upgrade-result.json").write_text(json.dumps(proof, indent=2) + "\n")
print(
    "All four production program modes and kernel flags verified; map sizes match compiled complete production headers across upgrade; restart/stop leaves no private pins or program references"
)
