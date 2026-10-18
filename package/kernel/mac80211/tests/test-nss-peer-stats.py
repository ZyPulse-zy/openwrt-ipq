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
DRIVER_BLOB = '6a7396bf3a49c1db7bd4412dd181a96f8474757e'
DRIVER_PATCHES = {
    '0007-nss-drv-Fix-nss_wifili_if-compilation-error-GCC-13.patch':
        '4d052625fa8f938b5982411f809f9e39fca018e5f9def5e94da9f6a877257e38',
    '0017-nss-drv-wifili-add-exported-symbols.patch':
        '75831dc3631339b144eef16287921227cc98d0a78981957b450da022a614f987',
    '0022-nss-drv-limit-fw-12.2.patch':
        '993297cf9aac475b0de6e1bef13f94e7bab6bbcdb0e31914b144f5c470186d7f',
}


def driver_types(path, patches):
    data = path.read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if blob != DRIVER_BLOB:
        raise ValueError('Driver header differs from pinned d5ee67bd84d1 export')
    target = 'exports/nss_wifili_if.h'
    with tempfile.TemporaryDirectory(prefix='nss-export-test-') as folder:
        stage = pathlib.Path(folder)
        header = stage / target
        header.parent.mkdir()
        header.write_bytes(data)
        seen = set()
        for patch in sorted(patches.glob('*.patch')):
            raw = patch.read_bytes()
            sections = re.split(r'(?=^--- (?:[ab]/|/dev/null))', raw.decode(), flags=re.M)
            relevant = [s for s in sections if re.search(
                r'^\+\+\+ b/' + re.escape(target) + r'(?:\s|$)', s, re.M)]
            if not relevant:
                continue
            if hashlib.sha256(raw).hexdigest() != DRIVER_PATCHES.get(patch.name):
                raise ValueError('Driver header patch differs from pinned feed: ' + patch.name)
            subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-d', str(stage)],
                           input=''.join(relevant), text=True, check=True,
                           capture_output=True, timeout=10)
            seen.add(patch.name)
        if seen != set(DRIVER_PATCHES):
            raise ValueError('Incomplete driver export patch series')
        text = header.read_text()
        print('Patched export SHA256:', hashlib.sha256(text.encode()).hexdigest())
    # Copy complete declarations verbatim, including their nested type fields;
    # unrelated kernel APIs from the rest of the header are not compiled.
    names = ('tx_dropped', 'tx_ctrl_stats', 'rx_err', 'rx_ctrl_stats',
             'retry_ctrl_stats', 'peer_ctrl_stats', 'peer_stats')
    parts = [re.match(r'/\*.*?\*/', text, re.S).group()]
    for name in ('TQM_RR_MAX', 'MAX_RESERVED_TYPE'):
        parts.append(re.search(r'^#define NSS_WIFILI_' + name + r'\s+\d+\s*$',
                               text, re.M).group())
    for name in names:
        parts.append(re.search(r'^struct nss_wifili_' + name +
                               r' \{.*?^\};', text, re.M | re.S).group())
    return '\n\n'.join(parts) + '\n'


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
    parser.add_argument('--driver-header', type=pathlib.Path,
                        help='pinned NSS d5ee67bd84d1 exports/nss_wifili_if.h')
    parser.add_argument('--driver-patches', type=pathlib.Path,
                        help='pinned nss-packages qca-nss-drv/patches directory')
    args = parser.parse_args()
    if bool(args.driver_header) != bool(args.driver_patches):
        parser.error('--driver-header and --driver-patches must be supplied together')
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
        if args.driver_header:
            (stage / 'driver-types.h').write_text(driver_types(args.driver_header,
                                                            args.driver_patches))
            print('Actual driver declarations from blob:', DRIVER_BLOB)
        for macro in (False, True):
            output = stage / ('test-12.5' if macro else 'test-default')
            cmd = shlex.split(args.cc) + ['-std=c11', '-O0' if args.sanitize else '-O2', '-Wall', '-Wextra', '-Werror']
            if macro:
                cmd.append('-DNSS_FIRMWARE_VERSION_12_5')
            if args.driver_header:
                # Kernel builds suppress sign-compare: the real npeers is u32,
                # unlike the intentionally simplified default fixture's int.
                cmd += ['-DREAL_NSS_STATS_TYPES', '-Wno-sign-compare']
            if args.sanitize:
                cmd += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
            subprocess.run(cmd + [str(test), '-o', str(output)], check=True, timeout=30)
            subprocess.run(shlex.split(args.runner) + [str(output)], check=True, timeout=10)
    print('Kernel/lookup fixtures; no module or firmware validation')


if __name__ == '__main__':
    main()
