#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual 802.3 xmit function against bounded kernel fixtures."""
import argparse
import hashlib
import pathlib
import re
import resource
import shlex
import subprocess
import tempfile

FIX='999-921-mac80211-initialize-offload-host-queue.patch'
GROUPS=['build','subsys','ath','ath5k','ath9k','ath10k','ath11k','ath12k',
        'rt2x00','mt7601u','mwl','brcm','rtl','nss/subsys','nss/ath10k','nss/ath11k']


def extract(text):
    signature='static void ieee80211_8023_xmit('
    start=-1
    while True:
        start=text.index(signature,start+1)
        brace=text.index('{',start);semi=text.find(';',start)
        if semi<0 or semi>brace:break
    level,end=1,brace+1
    while level:
        level+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    source=parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--archive',type=pathlib.Path,help='recipe-matching backports tar.zst')
    source.add_argument('--source',type=pathlib.Path,help='complete prepared tree including this fix')
    parser.add_argument('--without-fix',action='store_true',help='reproduce the original queue diagnostic')
    parser.add_argument('--sanitize',action='store_true')
    parser.add_argument('--cc',default='cc')
    parser.add_argument('--runner',default='')
    args=parser.parse_args();resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    root=pathlib.Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='mac80211-queue-test-') as folder:
        temp=pathlib.Path(folder);stage=temp/'source';stage.mkdir()
        if args.archive:
            expected=re.search(r'^PKG_HASH:=(\w+)$',(root/'Makefile').read_text(),re.M).group(1)
            assert hashlib.sha256(args.archive.read_bytes()).hexdigest()==expected,'archive checksum mismatch'
            subprocess.run(['tar','--zstd','--extract','--file',str(args.archive.resolve()),
                            '--directory',str(stage),'--strip-components=1','--no-same-owner','--no-same-permissions'],check=True,timeout=30)
            count=0
            for group in GROUPS:
                for patch in sorted((root/'patches'/group).glob('*.patch')):
                    if args.without_fix and patch.name==FIX:continue
                    subprocess.run(['patch','--batch','--fuzz=0','--no-backup-if-mismatch','-p1',
                                    '-d',str(stage),'-i',str(patch.resolve())],check=True,capture_output=True,timeout=10)
                    count+=1
            print('Applied actual complete recipe patches:',count)
        else:
            source=stage/'net/mac80211/tx.c';source.parent.mkdir(parents=True)
            source.write_bytes((args.source/'net/mac80211/tx.c').read_bytes())
            if args.without_fix:
                subprocess.run(['patch','--batch','--fuzz=0','-R','-p1','-d',str(stage),'-i',
                                str(root/'patches/nss/subsys'/FIX)],check=True,capture_output=True,timeout=10)
        function=extract((stage/'net/mac80211/tx.c').read_text())
        print('Actual complete function SHA256:',hashlib.sha256(function.encode()).hexdigest())
        test=temp/'test.c'
        test.write_text((root/'tests/offload-host-queue.c').read_text().replace('/* SOURCE_FUNCTION */',function))
        output=temp/'test'
        cmd=shlex.split(args.cc)+['-std=c11','-O2','-Wall','-Wextra','-Werror']
        if args.sanitize:cmd+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
        subprocess.run(cmd+[str(test),'-o',str(output)],check=True,timeout=30)
        subprocess.run(shlex.split(args.runner)+[str(output)],check=True,timeout=10)
        print('Kernel/classifier fixtures only; firmware TID/AC and module build untested')


if __name__=='__main__':main()
