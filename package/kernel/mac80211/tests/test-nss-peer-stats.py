#!/usr/bin/env python3
"""Compile the actual patched NSS peer statistics function with kernel I/O fixtures.

No firmware ABI, module build or target hardware validation is implied.
"""
import argparse
import hashlib
import pathlib
import re
import resource
import shlex
import subprocess
import tempfile

TARGET = 'drivers/net/wireless/ath/ath11k/nss.c'
FIX = '999-921-ath11k-nss-reset-per-peer-drop-total.patch'


def extract(text):
    signature = 'static void ath11k_nss_get_peer_stats('
    start = -1
    while True:
        start = text.index(signature, start + 1)
        brace = text.index('{', start)
        semicolon = text.find(';', start)
        if semicolon == -1 or semicolon > brace:
            break
    level, end = 1, brace + 1
    while level:
        level += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--without-fix', action='store_true', help='reproduce original failure')
    parser.add_argument('--sanitize', action='store_true')
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--runner', default='', help='optional cross-execution command')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root = pathlib.Path(__file__).resolve().parents[1]
    fixture = (root / 'tests/nss-peer-stats.c').read_text()
    with tempfile.TemporaryDirectory(prefix='ath11k-nss-test-') as folder:
        stage = pathlib.Path(folder)
        source = stage / TARGET
        source.parent.mkdir(parents=True)
        applied = 0
        # nss.c is introduced by the NSS series. Reconstruct just its complete
        # file by applying every relevant section in the actual recipe order.
        for patch in sorted((root / 'patches/nss/ath11k').glob('*.patch')):
            if args.without_fix and patch.name == FIX:
                continue
            sections = re.split(r'(?=^--- (?:[ab]/|/dev/null))', patch.read_text(), flags=re.M)
            relevant = [s for s in sections if re.search(r'^\+\+\+ b/' + re.escape(TARGET) + r'(?:\s|$)', s, re.M)]
            if relevant:
                subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(stage)],
                               input=''.join(relevant), text=True, check=True,
                               capture_output=True, timeout=10)
                applied += 1
        function = extract(source.read_text())
        print('Complete source function SHA256:', hashlib.sha256(function.encode()).hexdigest())
        print('Applied actual patch sections:', applied)
        test = stage / 'test.c'
        test.write_text(fixture.replace('/* SOURCE_FUNCTION */', function))
        for macro in (False, True):
            output = stage / ('test-12.5' if macro else 'test-default')
            cmd = shlex.split(args.cc) + ['-std=c11', '-O0' if args.sanitize else '-O2', '-Wall', '-Wextra', '-Werror']
            if macro:
                cmd.append('-DNSS_FIRMWARE_VERSION_12_5')
            if args.sanitize:
                cmd += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            subprocess.run(cmd + [str(test), '-o', str(output)], check=True, timeout=30)
            subprocess.run(shlex.split(args.runner) + [str(output)], check=True, timeout=10)
    print('Kernel/lookup/wire fixtures only; no module or firmware validation')


if __name__ == '__main__':
    main()
