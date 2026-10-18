#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise complete ath11k NSS init and real driver registration functions.

Only resource/control-flow contracts are tested; kernel I/O and message/ring
types remain bounded fixtures. No module, timing or hardware claim is implied.
"""
import argparse
import hashlib
from pathlib import Path
import re
import resource
import shlex
import subprocess
import tempfile

TARGET = 'drivers/net/wireless/ath/ath11k/nss.c'
FIX = '999-922-ath11k-nss-unregister-on-unready-context.patch'
DRIVER_BLOB = '209f8cda545c4843131c0b3257d4710afe61e7ae'
GROUPS = ['build', 'subsys', 'ath', 'ath5k', 'ath9k', 'ath10k', 'ath11k', 'ath12k',
          'rt2x00', 'mt7601u', 'mwl', 'brcm', 'rtl', 'nss/subsys', 'nss/ath10k', 'nss/ath11k']


def function(text, name):
    # Each signature begins on one line; the driver register signature wraps.
    match = re.search(r'^(?:static )?(?:struct \w+\s*\*\s*|(?:int|void)\s+)'
                      + re.escape(name) + r'\(', text, re.M)
    start = match.start()
    brace = text.index('{', match.end())
    level, end = 1, brace + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver-source', type=Path, required=True,
                        help='d5ee67bd84d1 nss-drv/nss_wifili.c')
    parser.add_argument('--without-fix', action='store_true')
    parser.add_argument('--archive', type=Path,
                        help='optionally apply the complete recipe to its matching backports archive')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--runner', default='')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    raw = args.driver_source.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if blob != DRIVER_BLOB:
        raise ValueError('Driver source differs from pinned d5ee67bd84d1')
    driver = raw.decode()
    root = Path(__file__).resolve().parents[1]
    fixture = (root / 'tests/nss-init.c').read_text()
    with tempfile.TemporaryDirectory(prefix='ath11k-nss-init-') as folder:
        stage = Path(folder)
        source = stage / TARGET
        applied = 0
        if args.archive:
            expected = re.search(r'^PKG_HASH:=(\w+)$', (root / 'Makefile').read_text(), re.M).group(1)
            if hashlib.sha256(args.archive.read_bytes()).hexdigest() != expected:
                raise ValueError('Backports archive checksum mismatch')
            subprocess.run(['tar', '--zstd', '-xf', str(args.archive.resolve()),
                            '-C', str(stage), '--strip-components=1', '--no-same-owner',
                            '--no-same-permissions'], check=True, timeout=30)
            for group in GROUPS:
                for patch in sorted((root / 'patches' / group).glob('*.patch')):
                    if args.without_fix and patch.name == FIX:
                        continue
                    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(stage),
                                    '-i', str(patch.resolve())], check=True,
                                   capture_output=True, timeout=10)
                    applied += 1
            print('Applied complete recipe patches:', applied, flush=True)
        else:
            source.parent.mkdir(parents=True)
            for patch in sorted((root / 'patches/nss/ath11k').glob('*.patch')):
                if args.without_fix and patch.name == FIX:
                    continue
                sections = re.split(r'(?=^--- (?:[ab]/|/dev/null))', patch.read_text(), flags=re.M)
                relevant = [s for s in sections if re.search(
                    r'^\+\+\+ b/' + re.escape(TARGET) + r'(?:\s|$)', s, re.M)]
                if relevant:
                    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(stage)],
                                   input=''.join(relevant), text=True, capture_output=True,
                                   check=True, timeout=10)
                    applied += 1
            print('Applied actual NSS source sections:', applied, flush=True)
        init = function(source.read_text(), 'ath11k_nss_init')
        bindings = '\n\n'.join(function(driver, name) for name in
                               ('nss_register_wifili_if', 'nss_unregister_wifili_if'))
        # Keep the upstream license with the copied functions in the temporary TU.
        license = re.match(r'/\*.*?\*/', driver, re.S).group()
        test = stage / 'test.c'
        test.write_text(license + '\n' + fixture.replace('/* DRIVER_FUNCTIONS */', bindings)
                        .replace('/* INIT_FUNCTION */', init))
        print('Complete init SHA256:', hashlib.sha256(init.encode()).hexdigest(), flush=True)
        print('Actual driver register/unregister SHA256:',
              hashlib.sha256(bindings.encode()).hexdigest(), flush=True)
        for mesh in (False, True):
            output = stage / ('mesh' if mesh else 'normal')
            cmd = shlex.split(args.cc) + ['-std=c11', '-O1' if args.sanitize else '-O2',
                                         '-Wall', '-Wextra', '-Werror']
            if mesh:
                cmd.append('-DCPTCFG_ATH11K_NSS_MESH_SUPPORT')
            if args.sanitize:
                cmd += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            subprocess.run(cmd + [str(test), '-o', str(output)], check=True, timeout=30)
            subprocess.run(shlex.split(args.runner) + [str(output)], check=True, timeout=10)
    print('Real registration/init control flow; kernel/ring/message I/O fixtures only')


if __name__ == '__main__':
    main()
