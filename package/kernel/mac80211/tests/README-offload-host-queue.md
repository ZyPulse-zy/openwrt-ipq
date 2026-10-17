`test-offload-host-queue.py --archive /path/backports-VERSION.tar.zst` verifies
the archive against the current recipe hash, applies the complete patch recipe
with fuzz=0, extracts the actual `ieee80211_8023_xmit()` implementation, and
compiles/runs it with bounded kernel and classifier fixtures. It requires
Python 3, tar, zstd, patch and a C compiler; no root or hardware is needed.

The 160 checks cover all HAS_TX_QUEUE / SUPPORTS_NSS_OFFLOAD combinations and
CPU queue mappings 0–7. Software classification still selects its AC; the
hardware-owned path uses a safe BE host queue while retaining its original
netdev queue mapping and full skb priority. Station accounting stays in bounds.
The queue mapping must not be reused as an AC index on the offloaded path.

`--without-fix` omits this patch and must fail the strict compiler build with
an uninitialized-queue diagnostic. `--sanitize` enables ASan/UBSan. `--cc` and
`--runner` allow cross-execution. `--source` instead accepts a fully prepared
tree including this fix; `--without-fix` reverses only this patch in a temporary
copy before extraction.

The function is actually extracted rather than mirrored. Synchronization,
packet handling and classification callbacks are fixtures. This is not a
complete kernel module build, firmware TID/AC test or packet-loss/performance
measurement, and no production interface or router is touched.
