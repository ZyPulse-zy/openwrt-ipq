# SPDX-License-Identifier: GPL-2.0-only
"""Pinned source export declarations for NSS layout regressions."""
import hashlib
import pathlib
import re
import subprocess
import tempfile

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
    parts = [re.match(r'/\*.*?\*/', text, re.S).group(), '#include <stdint.h>']
    for name in ('TQM_RR_MAX', 'MAX_RESERVED_TYPE'):
        parts.append(re.search(r'^#define NSS_WIFILI_' + name + r'\s+\d+\s*$',
                               text, re.M).group())
    for name in names:
        parts.append(re.search(r'^struct nss_wifili_' + name +
                               r' \{.*?^\};', text, re.M | re.S).group())
    return '\n\n'.join(parts) + '\n'
