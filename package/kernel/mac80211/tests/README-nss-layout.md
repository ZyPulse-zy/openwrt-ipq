# Selected NSS export layout regression

The mac80211 recipe passes the 11.4 selection macro but omits the 12.5 macro.
The NSS driver recipe selects the 12.5 export layout when that firmware option
is enabled. Feed-patched peer records are 196 bytes without that define and
212 bytes with it, so the ath11k consumer can read later rows at the wrong
offset. Firmware selection also needs to participate in package rebuild
dependencies rather than leaving a previously compiled layout cached.

The change gates `NSS_FIRMWARE_VERSION_12_5` on the selected firmware and ath11k
NSS support, and tracks both firmware options used by the recipe. It does not
hardcode 12.5 for every NSS device or enable the define for a non-NSS build.

```sh
python3 package/kernel/mac80211/tests/test-nss-layout.py \
  --driver-header /path/to/nss-drv/exports/nss_wifili_if.h \
  --driver-package /path/to/nss-packages/qca-nss-drv
```

Use driver source `d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7` from
[CodeLinaro-mirror/qsdk_oss_lklm_nss-drv](https://github.com/CodeLinaro-mirror/qsdk_oss_lklm_nss-drv/tree/d5ee67bd84d1ee7ed81eb6758e62a6db5a0cf4c7)
and feed `0d970dbf0185e3f53709bd803e8a466598023c57` from
[qosmio/nss-packages](https://github.com/qosmio/nss-packages/tree/0d970dbf0185e3f53709bd803e8a466598023c57).
The whole export blob and every relevant header patch are hash-pinned. Three
header patch sections apply in recipe order with fuzz=0; the complete seven
statistics declarations, including their 12.5 field guards, are copied verbatim.

GNU make evaluates the actual mac80211 and driver recipes in a temporary
metadata fixture; only framework includes are empty. It reads their real
defines and dependency lists, without reimplementing the selection condition.
The two binaries compile with those actual recipe defines. The producer writes
two synthetic source-interface rows; the consumer executes the complete actual
ath11k callback reconstructed from its patch series. Kernel synchronization,
peer lookup and destination counters remain fixtures.

Under the original recipe, the 12.5 producer writes 212-byte rows while the
consumer expects 196: peer packet counts become `10/0` instead of `10/20`.
The fixed recipe passes the same serialization/callback test for unset, 12.1,
12.2 and 12.5 source branches. Additional flag/dependency checks preserve the
11.4 selection and ensure disabled ath11k NSS cannot enable the 12.5 define.
The test does **not** claim actual 11.4/12.1/12.2 firmware compatibility.

`--mac-recipe` can point to an exact baseline Makefile for the negative test.
`--sanitize`, `--cc` and `--runner` support native ASan/UBSan and cross execution.
Normal/cross builds use -O2; sanitizer uses -O0 because the unrelated existing
zero-radio lookup branch produces a maybe-uninitialized diagnostic under
optimized instrumentation. The fixture supplies one valid radio. That path
is not repaired or declared safe here; sign-compare follows kernel policy.

The producer is a **host header model**, never captured or synthesized firmware
evidence. This regression establishes recipe/export/consumer source consistency
and rebuild metadata, not a complete SDK/Kbuild/module build, packet transport
length checks, runtime firmware ABI, hardware behavior or network performance.
It neither modifies a router nor imports private flow samples.
