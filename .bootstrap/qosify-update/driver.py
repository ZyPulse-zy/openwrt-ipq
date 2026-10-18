#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build both real SDK recipes, then test their packaged objects and loaders."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from lab_io import extract_archive
from restore_git import restore_git

HERE = Path(__file__).resolve().parent
PINS = json.loads((HERE / "pins.json").read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def run(log, words, *, cwd=None, env=None, allowed=(0,)):
    with log.open("w") as output:
        result = subprocess.run(
            list(map(str, words)),
            cwd=cwd,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    if result.returncode not in allowed:
        print(log.read_text()[-12000:], flush=True)
        raise RuntimeError(f"Command failed ({result.returncode}): {log.name}")
    return result.returncode


def acquire(spec, path):
    run(
        path.with_suffix(".download.log"),
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "4",
            "--retry-all-errors",
            "--connect-timeout",
            "20",
            "--max-time",
            "600",
            spec["url"],
            "-o",
            path,
        ],
    )
    assert digest(path) == spec["sha256"], f"Archive digest mismatch: {path.name}"


def one(paths):
    paths = list(paths)
    assert len(paths) == 1, [str(p) for p in paths]
    return paths[0]


def build_packages(work, source, evidence):
    sdk = work / "sdk"
    archive = work / "sdk.tar.zst"
    acquire(PINS["sdk"], archive)
    omitted = extract_archive(archive, sdk, PINS["sdk"]["absolute_host_links"])
    save(
        evidence / "sdk-extraction.json",
        {"sha256": digest(archive), "omitted": omitted},
    )
    assert omitted == PINS["sdk"]["absolute_host_links"]
    actual = subprocess.check_output(
        ["git", "-C", source, "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual == PINS["nss_candidate"]
    relative = "package/network/config/qosify/Makefile"
    recipe = source / relative
    candidate = recipe.read_bytes()
    baseline = subprocess.check_output(
        ["git", "-C", source, "show", PINS["nss_base"] + ":" + relative]
    )
    assert b"MIRROR_HASH:=skip" not in candidate
    (sdk / "feeds.conf").write_text(f"src-link base {source}/package\n")
    kernel = one(sdk.glob("build_dir/target-*/linux-*/linux-*/Module.symvers")).parent
    abi = {name: digest(kernel / name) for name in [".config", "Module.symvers"]}
    save(evidence / "kernel-abi-before.json", abi)
    env = dict(os.environ, BISON_PKGDATADIR="/usr/share/bison", M4="/usr/bin/m4")
    try:
        recipe.write_bytes(baseline)
        run(
            evidence / "feeds-update.log",
            ["./scripts/feeds", "update", "base"],
            cwd=sdk,
            env=env,
        )
        run(
            evidence / "feeds-install.log",
            ["./scripts/feeds", "install", "qosify"],
            cwd=sdk,
            env=env,
        )
        assert (
            sdk / "package/feeds/base/qosify/Makefile"
        ).is_file(), "Feed prerequisite/index failure"
        (sdk / ".config").write_text(
            "CONFIG_PACKAGE_qosify=m\n# CONFIG_ALL_KMODS is not set\n# CONFIG_ALL_NONSHARED is not set\n"
        )
        run(evidence / "defconfig.log", ["make", "defconfig"], cwd=sdk, env=env)
        selected = re.findall(
            r"^(CONFIG_PACKAGE_kmod-[^=]+)=[ym]$", (sdk / ".config").read_text(), re.M
        )
        required = {"kmod-ifb", "kmod-sched-bpf", "kmod-sched-cake", "kmod-sched-core"}
        overrides = [
            name + ("=m" if name.removeprefix("CONFIG_PACKAGE_") in required else "=")
            for name in selected
        ]
        assert required <= {name.removeprefix("CONFIG_PACKAGE_") for name in selected}
        command = ["make", "package/qosify/compile", "V=s", "-j4", *overrides]
        save(evidence / "build-command.json", command)
        for label, data, commit in [
            ("baseline", baseline, PINS["qosify"]["baseline"]),
            ("candidate", candidate, PINS["qosify"]["candidate"]),
        ]:
            recipe.write_bytes(data)
            run(evidence / (label + "-sdk.log"), command, cwd=sdk, env=env)
            out = work / (label + "-artifacts")
            out.mkdir()
            apk = one(
                sdk.glob("bin/targets/*/*/packages/qosify-*" + commit[:8] + "*.apk")
            )
            shutil.copy2(apk, out / apk.name)
            extracted = out / "extracted"
            extracted.mkdir()
            run(
                evidence / (label + "-apk-extract.log"),
                [
                    sdk / "staging_dir/host/bin/apk",
                    "extract",
                    "--allow-untrusted",
                    "--no-chown",
                    "--destination",
                    extracted,
                    apk,
                ],
            )
            obj = extracted / "lib/bpf/qosify-bpf.o"
            assert obj.is_file()
            shutil.copy2(obj, out / "qosify-bpf.o")
            archive = one(sdk.glob("dl/qosify-*" + commit[:8] + ".tar.*"))
            expected_hash = re.search(rb"^PKG_MIRROR_HASH:=(\S+)$", data, re.M)[
                1
            ].decode()
            assert digest(archive) == expected_hash
            tree = work / (label + "-source")
            extract_archive(archive, tree)
            proof = restore_git(
                tree, (HERE / (label + ".commit")).read_bytes(), commit, branch="master"
            )
            proof.update(
                archive_sha256=digest(archive),
                apk_sha256=digest(apk),
                object_sha256=digest(obj),
            )
            save(evidence / (label + "-source.json"), proof)
            shutil.copy2(apk, evidence / apk.name)
            shutil.copy2(obj, evidence / (label + "-packaged.o"))
            assert abi == {
                name: digest(kernel / name) for name in abi
            }, "SDK kernel ABI changed"
    finally:
        recipe.write_bytes(candidate)
    run(evidence / "source-clean.log", ["git", "-C", source, "diff", "--exit-code"])
    save(
        evidence / "sdk-build-result.json",
        {
            "passed": True,
            "source": actual,
            "kernel_abi_inputs_unchanged": True,
            "required_kernel_packages": sorted(required),
        },
    )
    return sdk


def native_tools(work, sdk, evidence):
    archive = work / "kernel.tar.xz"
    acquire(PINS["kernel"], archive)
    kernel = work / "native-kernel"
    extract_archive(archive, kernel)
    output = work / "bpftool-build"
    output.mkdir()
    llvm = (sdk / "staging_dir/host/llvm-bpf").resolve(strict=True) / "bin"
    run(
        evidence / "bpftool-build.log",
        [
            "make",
            "-C",
            kernel / "tools/bpf/bpftool",
            f"OUTPUT={output}/",
            "CC=gcc",
            "HOSTCC=gcc",
            f"CLANG={llvm}/clang",
            f"LLVM_STRIP={llvm}/llvm-strip",
            "-j4",
        ],
    )
    for label in ["baseline", "candidate"]:
        source = work / (label + "-source")
        command = [
            "gcc",
            "-g",
            "-O2",
            "-I" + str(source),
            "-I" + str(sdk / "staging_dir/host/include"),
            "-I" + str(kernel / "tools/lib"),
            "-I" + str(kernel / "tools/include/uapi"),
            '-DQOSIFY_LOADER_SOURCE="' + str(source / "loader.c") + '"',
        ]
        if label == "candidate":
            command.append("-DTEST_LOADER_STOP")
        command += [
            HERE / "loader-harness.c",
            output / "libbpf/libbpf.a",
            "-lelf",
            "-lz",
            "-o",
            work / (label + "-loader"),
        ]
        run(evidence / (label + "-loader-build.log"), command)
    return output / "bpftool"


def isolated(script, words, log, bpftool, allowed=(0,)):
    env = ["PATH=" + str(bpftool.parent) + ":" + os.environ["PATH"]]
    env += [
        "QOSIFY_PARENT_" + ns.upper() + "NS=" + os.readlink("/proc/self/ns/" + ns)
        for ns in ["net", "mnt"]
    ]
    return run(
        log,
        [
            "sudo",
            "env",
            *env,
            "unshare",
            "--net",
            "--mount",
            sys.executable,
            HERE / script,
            *words,
        ],
        allowed=allowed,
    )


def kernel_tests(work, bpftool, evidence):
    for label in ["baseline", "candidate"]:
        for mode in ["matrix", "tun"]:
            report = evidence / (label + "-" + mode + ".json")
            isolated(
                "test-" + mode + ".py",
                [
                    "--object",
                    work / (label + "-artifacts/qosify-bpf.o"),
                    "--report",
                    report,
                    "--expect-failure",
                ],
                evidence / (label + "-" + mode + ".log"),
                bpftool,
                allowed=(0, 1),
            )
    comparison = {}
    for mode, cases, before, after in [("matrix", 976, 108, 104), ("tun", 96, 16, 16)]:
        old = json.loads((evidence / ("baseline-" + mode + ".json")).read_text())
        new = json.loads((evidence / ("candidate-" + mode + ".json")).read_text())
        assert old["cases"] == new["cases"] == cases
        assert len(old["mismatches"]) == before and len(new["mismatches"]) == after
        improved = []
        for a, b in zip(old["results"], new["results"], strict=True):
            assert {k: v for k, v in a.items() if k != "dscp"} == {
                k: v for k, v in b.items() if k != "dscp"
            }, "Case inputs differ"
            assert not (
                a["dscp"] == a["expected_dscp"] and b["dscp"] != b["expected_dscp"]
            ), "New regression"
            if a["dscp"] != b["dscp"]:
                assert a["initial_dscp"] == 20 and a["dscp"] == 46 and b["dscp"] == 20
                improved.append({"before": a, "after": b})
        assert len(improved) == before - after
        comparison[mode] = {
            "cases": cases,
            "baseline_mismatches": before,
            "candidate_mismatches": after,
            "improved": improved,
            "new_regressions": 0,
        }
    save(evidence / "packet-comparison.json", comparison)
    isolated(
        "test-loader-upgrade.py",
        ["--lab", work, "--bpftool", bpftool],
        evidence / "loader-upgrade.log",
        bpftool,
    )
    shutil.copy2(
        work / "loader-upgrade-result.json", evidence / "loader-upgrade-result.json"
    )


def qemu_test(work, sdk, evidence):
    out = work / "candidate-artifacts"
    root = out / "qemu-root"
    (root / "lib").mkdir(parents=True)
    (root / "usr/lib").mkdir(parents=True)
    target = one(sdk.glob("staging_dir/target-*_musl"))
    for path in (target / "usr/lib").glob("*.so*"):
        if path.is_file():
            shutil.copyfile(path, root / "usr/lib" / path.name)
    toolchain = sdk / "staging_dir" / PINS["sdk"]["toolchain"] / "lib"
    for name in ["libc.so", "libgcc_s.so.1"]:
        shutil.copyfile(toolchain / name, root / "lib" / name)
    (root / "lib/ld-musl-aarch64.so.1").symlink_to("libc.so")
    status = run(
        evidence / "candidate-qemu-cli.log",
        ["qemu-aarch64", "-L", root, out / "extracted/usr/sbin/qosify", "-h"],
        allowed=(1,),
    )
    assert "Usage:" in (evidence / "candidate-qemu-cli.log").read_text()
    save(
        evidence / "qemu-cli.json",
        {
            "passed": True,
            "exit": status,
            "scope": "Actual APK AArch64/musl CLI usage only; no target daemon or target BPF runtime",
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    work = args.workspace.resolve()
    work.mkdir(parents=True, exist_ok=False)
    evidence = work / "evidence"
    evidence.mkdir()
    sdk = build_packages(work, args.source.resolve(strict=True), evidence)
    bpftool = native_tools(work, sdk, evidence)
    kernel_tests(work, bpftool, evidence)
    qemu_test(work, sdk, evidence)
    save(
        evidence / "verification.json",
        {
            "passed": True,
            "candidate": PINS["nss_candidate"],
            "known_short_packet_failures_retained": {"matrix": 104, "tun": 16},
            "target_deployment": False,
            "firmware_or_hardware_tested": False,
        },
    )
    save(
        evidence / "file-sha256.json",
        {p.name: digest(p) for p in sorted(evidence.iterdir()) if p.is_file()},
    )
    print(
        "Both actual SDK packages, source roots, packaged BPF comparison, production loader upgrade and target CLI verified"
    )


if __name__ == "__main__":
    main()
