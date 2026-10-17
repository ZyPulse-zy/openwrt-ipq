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
