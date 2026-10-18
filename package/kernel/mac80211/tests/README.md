`python3 package/kernel/mac80211/tests/test-nss-peer-stats.py` reconstructs the
complete actual `nss.c` from its NSS patch sections in recipe order, extracts the
real peer statistics function, and compiles/runs it against bounded kernel I/O,
peer lookup and wire-structure fixtures. No root or target device is needed.

The regression uses two peers with 2 and 5 drop counts: the original function
incorrectly gives the second peer 7. Other cases exercise reversed order,
repeated notifications, all bins for 32 peers, skipped peers, ext-vdev accounting,
statistics disabled, zero drops and existing u32 counter wrap behavior.

`--without-fix` excludes the per-peer reset patch and must fail the second-peer
case. `--sanitize` enables ASan/UBSan. `--cc` and `--runner` support cross-built
execution. Both default and NSS_FIRMWARE_VERSION_12_5 preprocessing modes run;
the wire structs are fixtures, so this is not firmware layout/ABI validation.

The source function is actually extracted, not reimplemented in the test.
This does not compile a complete kernel module, load a driver, change hardware
or establish any packet-loss/performance improvement.

The sanitizer build uses -O0; ordinary and cross builds use -O2. The fixture
provides one valid radio. The existing source's zero-radio peer-lookup path is
outside this counter regression and is not claimed to be safe by these tests.

For the actual 12.5 driver statistics declarations, pass `--driver-header` with
`exports/nss_wifili_if.h` from the feed's pinned driver commit
`d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7`. Also supply `--driver-patches`
pointing to `qca-nss-drv/patches` from nss-packages commit
`0d970dbf0185e3f53709bd803e8a466598023c57`. An accessible source mirror is
[CodeLinaro-mirror/qsdk_oss_lklm_nss-drv](https://github.com/CodeLinaro-mirror/qsdk_oss_lklm_nss-drv/tree/d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7).
The runner validates the whole header's Git blob SHA and all three relevant
feed patch hashes, applies their header sections in recipe order without fuzz,
then copies seven complete statistics declarations and their two constants
verbatim. This includes the feed's conditional 12.2/12.5 field guards. A missing
or altered header patch fails closed. It does not substitute a hand-written
incoming wire layout in that mode.

```sh
python3 package/kernel/mac80211/tests/test-nss-peer-stats.py \
  --driver-header /path/to/nss-drv/exports/nss_wifili_if.h \
  --driver-patches /path/to/nss-packages/qca-nss-drv/patches
```

The actual header has **7** release-reason bins and a trailing `wpcs[1]`,
where the simplified fixture has four bins and a fixed array. The harness
allocates enough payload for 32 real rows without changing that declaration.
The 42 checks include the final real bin and isolation from its adjacent NAWDS
counter, alongside the existing per-peer cases. Native, sanitizer and cross
execution use identical declarations. Only sign-compare is suppressed in this
mode, matching kernel build policy for the callback's signed loop/u32 count.

The destination peer data, lookup and synchronization remain fixtures; only
the incoming declarations are source-exact. Both preprocessor paths use the
same feed-patched 12.5 source export, so this does not establish 11.4 layout compatibility, full
module compilation, transport length validation or actual firmware ABI behavior.
