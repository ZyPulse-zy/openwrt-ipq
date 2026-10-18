// SPDX-License-Identifier: GPL-2.0-only
/* A source-interface serialization model; never firmware output. */
#include "driver-types.h"
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char **argv)
{
	assert(argc == 2);
	size_t length = offsetof(struct nss_wifili_peer_stats, wpcs) +
			2 * sizeof(struct nss_wifili_peer_ctrl_stats);
	struct nss_wifili_peer_stats *msg = calloc(1, length);
	assert(msg);
	msg->npeers = 2;
	msg->wpcs[0].peer_id = 0;
	msg->wpcs[1].peer_id = 1;
	msg->wpcs[0].tx.tx_ucast_cnt = 10;
	msg->wpcs[1].tx.tx_ucast_cnt = 20;
	/* A 196-byte consumer mistakes this first-row retry field for peer 2's ID. */
	msg->wpcs[0].retry.tx_multiple_retry_count = 99;
	FILE *f = fopen(argv[1], "wb");
	assert(f);
	assert(fwrite(msg, 1, length, f) == length);
	assert(fclose(f) == 0);
	printf("Producer record=%zu, payload=%zu\n", sizeof(msg->wpcs[0]), length);
	free(msg);
	return 0;
}
