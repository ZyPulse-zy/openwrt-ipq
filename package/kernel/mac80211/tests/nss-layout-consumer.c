// SPDX-License-Identifier: GPL-2.0-only
/* Real callback and source-exact incoming types; kernel/destination fixtures. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint64_t u64;
typedef uint32_t u32;
#define ATH11K_DBG_NSS 0
#define ath11k_dbg(...) ((void)0)
#define rcu_read_lock() ((void)0)
#define rcu_read_unlock() ((void)0)
#define spin_lock_bh(p) ((void)(p))
#define spin_unlock_bh(p) ((void)(p))
#define ATH11K_NSS_TXRX_NETDEV_STATS(direction, dev, bytes, packets) ((void)(dev))
static u64 jiffies = 1234;
struct peer_stats {
	u32 tx_packets, tx_bytes, tx_retries, tx_failed, rx_packets, rx_bytes, rx_dropped;
	u32 tx_amsdu, tx_non_amsdu, tx_ofdma, tx_failed_retries, tx_multiple_retries;
	u32 tx_mpdu_retries, tx_mpdu_total_retries, rx_amsdu, rx_non_amsdu, rx_retries;
	u32 rx_intra_bss, rx_intra_bss_fail, rx_mic_err, rx_decrypt_err;
	u64 last_ack, last_rx;
};
#include "driver-types.h"
struct ath11k_peer {
	void *sta, *vif;
	struct {
		struct peer_stats *nss_stats;
		bool ext_vdev_up;
		void *ext_vif;
	} nss;
};
struct ath11k {
	int radio;
};
struct ath11k_pdev {
	struct ath11k *ar;
};
static struct ath11k radio;
struct ath11k_base {
	struct {
		bool stats_enabled;
	} nss;
	int base_lock;
	int num_radios;
	struct ath11k_pdev pdevs[1];
};
static struct ath11k_peer peers[32];
static struct peer_stats totals[32];
static struct ath11k_peer *ath11k_peer_find_by_id(struct ath11k *ar, int id)
{
	(void)ar;
	return id >= 0 && id < 32 ? &peers[id] : NULL;
}
/* SOURCE_FUNCTION */
int main(int argc, char **argv)
{
	assert(argc == 2);
	FILE *f = fopen(argv[1], "rb");
	assert(f);
	unsigned char *bytes = calloc(1, 65536);
	assert(bytes);
	size_t length = fread(bytes, 1, 65536, f);
	assert(!ferror(f) && feof(f));
	fclose(f);
	struct nss_wifili_peer_stats *msg = (void *)bytes;
	assert(length >= offsetof(struct nss_wifili_peer_stats, wpcs) + 2 * sizeof(msg->wpcs[0]));
	assert(msg->npeers == 2);
	struct ath11k_base ab = {
	    .nss = {.stats_enabled = true}, .num_radios = 1, .pdevs = {{.ar = &radio}}};
	memset(totals, 0, sizeof(totals));
	for (int i = 0; i < 32; i++) {
		peers[i].sta = (void *)1;
		peers[i].nss.nss_stats = &totals[i];
	}
	ath11k_nss_get_peer_stats(&ab, msg);
	printf("Consumer record=%zu, packets=%u/%u\n", sizeof(msg->wpcs[0]), totals[0].tx_packets,
	       totals[1].tx_packets);
	if (totals[0].tx_packets != 10 || totals[1].tx_packets != 20) {
		fprintf(stderr, "FAIL second peer row decoded with wrong layout\n");
		free(bytes);
		return 1;
	}
	free(bytes);
	return 0;
}
