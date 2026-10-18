#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile a source-interface serialization model with actual recipe flags.

The producer is a host header model, never NSS firmware output. The consumer
executes the actual complete ath11k peer statistics callback against fixtures.
"""
import argparse
import hashlib
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from nss_driver_export import driver_types

TARGET = 'drivers/net/wireless/ath/ath11k/nss.c'
VERSIONS = ('11_4', '12_1', '12_2', '12_5')


def recipe_flags(recipe, cwd, stage, version, enabled=True):
    # The recipe asks git for informational build metadata at TOPDIR. Supply
    # an isolated fixture repository so those queries do not read host state.
    if not (stage / '.git').exists():
        subprocess.run(['git', 'init', '-q', str(stage)], check=True)
        subprocess.run(['git', '-C', str(stage), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', 'commit',
                        '--allow-empty', '-qm', 'test metadata'], check=True)
    include = stage / 'include'
    include.mkdir(exist_ok=True)
    for name in ('rules.mk', 'include/kernel.mk', 'include/package.mk'):
        (stage / name).write_text('')
    harness = stage / 'flags.mk'
    harness.write_text(".PHONY: flagdump\nflagdump:\n\t@printf '%s\\n' "
                       "'$(C_DEFINES)' '$(EXTRA_CFLAGS)' '$(PKG_CONFIG_DEPENDS)'\n")
    config = {v: ('y' if v == version else '') for v in VERSIONS}
    cmd = ['make', '-srR', '-f', str(recipe), '-f', str(harness), 'flagdump',
           f'TOPDIR={stage}', f'INCLUDE_DIR={include}',
           'IPQ_BRANCH=test', 'IPQ_DATE=test', 'IPQ_COMMIT=test',
           'CONFIG_ATH11K_NSS_SUPPORT=' + ('y' if enabled else '')]
    cmd += [f'CONFIG_NSS_FIRMWARE_VERSION_{v}={value}' for v, value in config.items()]
    output = subprocess.check_output(cmd, cwd=cwd, text=True).splitlines()
    assert len(output) == 3, output
    return output


def callback(root, stage):
    source = stage / TARGET
    source.parent.mkdir(parents=True)
    for patch in sorted((root / 'patches/nss/ath11k').glob('*.patch')):
        sections = re.split(r'(?=^--- (?:[ab]/|/dev/null))', patch.read_text(), flags=re.M)
        relevant = [s for s in sections if re.search(
            r'^\+\+\+ b/' + re.escape(TARGET) + r'(?:\s|$)', s, re.M)]
        if relevant:
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(stage)],
                           input=''.join(relevant), text=True, capture_output=True,
                           check=True, timeout=10)
    text = source.read_text()
    start = text.index('static void ath11k_nss_get_peer_stats(')
    brace = text.index('{', start)
    level, end = 1, brace + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver-header', type=Path, required=True)
    parser.add_argument('--driver-package', type=Path, required=True,
                        help='pinned nss-packages/qca-nss-drv directory')
    parser.add_argument('--mac-recipe', type=Path, help='optional exact baseline Makefile')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--runner', default='')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    recipe = (args.mac_recipe or root / 'Makefile').resolve()
    driver = args.driver_package.resolve()
    provider_recipe = (driver / 'Makefile').read_bytes()
    provider_blob = hashlib.sha1(b'blob ' + str(len(provider_recipe)).encode()
                                + b'\0' + provider_recipe).hexdigest()
    if provider_blob != '29a87fdedcc2badadb0c7956a36acafa3c599773':
        raise ValueError('Driver recipe differs from pinned nss-packages 0d970dbf0185')
    types = driver_types(args.driver_header, driver / 'patches')
    with tempfile.TemporaryDirectory(prefix='nss-layout-test-') as folder:
        stage = Path(folder)
        (stage / 'driver-types.h').write_text(types)
        function = callback(root, stage)
        print('Actual callback SHA256:', hashlib.sha256(function.encode()).hexdigest(), flush=True)
        consumer = stage / 'consumer.c'
        consumer.write_text((root / 'tests/nss-layout-consumer.c').read_text()
                            .replace('/* SOURCE_FUNCTION */', function))
        compile_cmd = shlex.split(args.cc) + ['-std=c11', '-O0' if args.sanitize else '-O2', '-Wall', '-Wextra',
                                             '-Werror', '-Wno-sign-compare', '-I', str(stage)]
        if args.sanitize:
            compile_cmd += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
        for version in ('', '12_1', '12_2', '12_5'):
            mac, _, dependencies = recipe_flags(recipe, root, stage, version)
            _, provider, _ = recipe_flags(driver / 'Makefile', driver, stage, version)
            producer = stage / 'producer'
            reader = stage / 'consumer'
            # Compile exactly the recipe's defines, omitting unrelated include
            # paths, optimization and kernel-only warning flags.
            provider_defines = [f for f in shlex.split(provider) if f.startswith('-D')]
            subprocess.run(compile_cmd + provider_defines +
                           [str(root / 'tests/nss-layout-producer.c'), '-o', str(producer)],
                           check=True, timeout=30)
            subprocess.run(compile_cmd + shlex.split(mac) +
                           [str(consumer), '-o', str(reader)], check=True, timeout=30)
            print('Firmware selection:', version or 'unset', 'consumer defines:', mac, flush=True)
            data = stage / 'synthetic-message.bin'
            subprocess.run(shlex.split(args.runner) + [str(producer), str(data)], check=True, timeout=10)
            subprocess.run(shlex.split(args.runner) + [str(reader), str(data)], check=True, timeout=10)
        legacy, _, legacy_dependencies = recipe_flags(recipe, root, stage, '11_4')
        assert '-DCONFIG_NSS_FIRMWARE_VERSION_11_4' in legacy
        assert '-DNSS_FIRMWARE_VERSION_12_5' not in legacy
        assert 'CONFIG_NSS_FIRMWARE_VERSION_11_4' in legacy_dependencies.split()
        disabled, _, _ = recipe_flags(recipe, root, stage, '12_5', enabled=False)
        assert '-DNSS_FIRMWARE_VERSION_12_5' not in disabled
        assert 'CONFIG_NSS_FIRMWARE_VERSION_12_5' in dependencies.split()
    print('Actual recipe flags / source serialization / callback contract passed')
    print('Host source-interface model, not firmware ABI or complete module validation')


if __name__ == '__main__':
    main()
