# NSS initialization registration lifetime

`ath11k_nss_init()` registers an NSS interface before checking its context
state. On the unready-context branch, the original jumps straight to local
memory cleanup and leaves the subsystem data-path registration holding `ab`.
The repair routes this branch through the existing unregister label. Failures
before registration keep their existing cleanup path and return values.

```sh
python3 package/kernel/mac80211/tests/test-nss-init.py \
  --driver-source /path/to/nss-drv/nss_wifili.c
# Optionally apply every complete mac80211 recipe patch first:
python3 package/kernel/mac80211/tests/test-nss-init.py \
  --driver-source /path/to/nss-drv/nss_wifili.c \
  --archive /path/to/backports-6.18.26.tar.zst --sanitize
```

Use the driver pinned by the NSS feed:
`d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7`, available at
[the CodeLinaro source mirror](https://github.com/CodeLinaro-mirror/qsdk_oss_lklm_nss-drv/blob/d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7/nss_wifili.c).
The runner verifies the whole file's Git blob SHA, then extracts its complete
`nss_register_wifili_if()` and `nss_unregister_wifili_if()` implementations.
The nss-packages feed at `0d970dbf0185e3f53709bd803e8a466598023c57` does not
patch this file. These real functions demonstrate that registration does not
reject an uninitialized context; its state check occurs later in ath11k.

The runner reconstructs the complete actual ath11k `nss.c` in patch order and
extracts the complete init function. `--archive` additionally verifies the
recipe archive hash and applies all complete patch groups with fuzz=0.
The original (`--without-fix`) must fail specifically with
`FAIL unready context: registration survived failed init`.

For each of the three valid NSS interface numbers, the 27-scenario suite covers
success, unsupported target, message allocation failure, partial descriptor
allocation failure, invalid interface, unready context, send failure, completion
timeout and NACK. It checks error preservation, registration/unregistration
pairing, local message release and descriptor cleanup. Both mesh preprocessing
modes run; each passes 231 assertions. `--sanitize`, `--cc` and `--runner` support
sanitizer and cross execution with the same source functions.

Core data-path registration, allocations, ring/message structures, completion
and kernel APIs are bounded test fixtures. The source registration/init control
flow is real; the fixture does not establish DMA behavior, callback concurrency,
actual timeout timing, complete module compilation or firmware/hardware results.
No source-tree cleanup or full-device crash diagnosis is inferred from this
single failure-path fix. No router, driver or service is loaded by the test.
