# NSS qosify package upgrade validation

The contribution changes only the source date, Git revision and mirror hash in
`package/network/config/qosify/Makefile`. The public control branch imports the
signed-off source commit without rewriting its author. All temporary baseline
recipe changes happen in the runner's independent checkout and are restored in
`finally`; Git verifies the candidate checkout is clean after both builds.

The official SHA-pinned OpenWrt 25.12 IPQ60xx SDK builds both complete packages
and their dependencies. Only the four required precompiled kernel packages are
selected on the make command line. Kernel `.config` and `Module.symvers` are
hashed before and after; no kernel source or ABI edits are permitted. SDK
extraction only omits the exact 20 pinned absolute host links. It does not
relax archive-member validation.

The test restores and verifies both complete qosify Git trees from the actual
SDK source archives. It extracts each actual APK and tests the packaged BPF
objects in private root network/mount namespaces: 976 Ethernet packet cases
and 96 TUN/TC datagrams per version. The old version has 108 Ethernet policy
mismatches, the update has 104; four existing-DSCP preservation cases improve
and no cases regress. Both have 16 TUN short-packet mismatches. These known
short-packet failures remain explicitly asserted; the independent boundary fix
is upstream PR openwrt/qosify#11. This upgrade does not include that unmerged fix.

Full production `loader.c` translation units are compiled against a native
libbpf built from pinned Linux source. Only the input BPF object path is
overridden. Tests invoke the actual loader for all four modes, read flags from
kernel maps, check map-value sizes against compiled production headers, replace
the old pinned map layout on upgrade, then restart and stop. No private pins or
program references survive the final process exit. These are native kernel
loader checks, not a claim of target-lib bpf runtime or complete daemon/ubus
execution. Actual AArch64/musl APK CLI usage is additionally checked under QEMU.

No original Athena checkout or deployed router is modified. IFB ingress
shaping, firmware, hardware throughput and end-to-end application quality are
outside this test. Download/build/test failures are retained as artifacts.

Run the workflow or invoke `driver.py --workspace NEW_DIRECTORY --source
INDEPENDENT_CANDIDATE_CHECKOUT` with the workflow's native prerequisites. The
driver deliberately requires a new workspace; it never reuses mutable SDK
state from a previous run.
