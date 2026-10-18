// SPDX-License-Identifier: GPL-2.0-only
/* Complete source functions are inserted at the markers. Kernel/ring/message
 * types and operations are fixtures; this is a registration-lifetime test. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32;
typedef int nss_tx_status_t;
typedef void (*nss_wifili_callback_t)(void);
typedef void (*nss_wifili_msg_callback_t)(void);
#define NSS_WIFILI_INTERNAL_INTERFACE 203
#define NSS_WIFILI_EXTERNAL_INTERFACE0 204
#define NSS_WIFILI_EXTERNAL_INTERFACE1 205
#define NSS_MAX_NET_INTERFACES 256
#define NSS_STATE_INITIALIZED 1
#define NSS_TX_SUCCESS 0
#define ATH11K_WIFILI_TARGET_TYPE_UNKNOWN 0
#define ATH11K_NSS_MSG_ACK 1
#define ATH11K_NSS_MSG_TIMEOUT_MS 6000
#define NSS_WIFILI_INIT_MSG 1
#define DP_RXDMA_NSS_REFILL_RING_SIZE 32
#define HAL_SRNG_RING_ID_LMAC1_ID_START 0
#define DP_TCL_NUM_RING_MAX 4
#define DP_REO_DST_RING_MAX 4
#define WIFILI_MULTISOC_THREAD_MAP_ENABLE 1
#define GFP_ATOMIC 0
#define ENOTSUPP EOPNOTSUPP
#define ATH11K_DBG_NSS 0
#define nss_assert assert
#define nss_info(...) ((void)0)
#define EXPORT_SYMBOL(name)
#define ath11k_info(...) ((void)0)
#define ath11k_warn(...) ((void)0)
#define ath11k_dbg(...) ((void)0)
#define ath11k_err(...) ((void)0)
struct net_device {
	int unused;
};
struct device {
	void *of_node;
};
struct nss_ctx_instance {
	int state;
};
static struct {
	struct nss_ctx_instance nss[1];
	unsigned wifi_handler_id;
	nss_wifili_msg_callback_t wifili_msg_callback;
} nss_top_main;
struct ring {
	struct {
		void *ring_id;
	} tcl_data_ring, tcl_comp_ring;
	void *ring_id;
};
struct ath11k_dp {
	struct ring tx_ring[4], reo_dst_ring[4], reo_reinject_ring, rx_rel_ring, reo_except_ring;
};
struct ath11k_base {
	struct device *dev;
	struct ath11k_dp dp;
	uintptr_t mem_pa;
	int userpd_id;
	struct {
		unsigned hal_desc_sz;
	} hw_params;
	struct {
		struct {
			uintptr_t paddr;
		} rdp, wrp;
	} hal;
	struct {
		unsigned if_num;
		int complete, response;
		struct nss_ctx_instance *ctx;
	} nss;
};
/* These minimal message shapes support control-flow execution only. */
struct nss_wifili_init_msg {
	unsigned target_type, flags, num_tcl_data_rings, num_reo_dest_rings;
	struct {
		unsigned tlv_size, rx_buf_len;
	} wrip;
	struct {
		u32 dev_base_addr, shadow_rdptr_mem_addr, shadow_wrptr_mem_addr,
		    lmac_rings_start_id;
	} hssm;
	int tcl_ring_info[4], tx_comp_ring[4], reo_dest_ring[4], reo_reinject_ring, rx_rel_ring,
	    reo_exception_ring;
};
struct nss_wifili_msg {
	int cm;
	union {
		struct nss_wifili_init_msg init;
	} msg;
};
enum fault {
	NONE,
	UNKNOWN_TARGET,
	ALLOC,
	DESCRIPTORS,
	INVALID_IF,
	UNREADY,
	SEND,
	TIMEOUT,
	NACK,
	FAULTS
};
static enum fault fault;
static unsigned interface_number, registrations, unregistrations, releases, live_messages;
static bool live_descriptors, priority;
static struct net_device *registered;
static unsigned checks, scenarios;
static const char *names[] = {
    "success",	       "target", "allocation", "descriptors", "invalid interface",
    "unready context", "send",	 "timeout",    "NACK"};
static void check(bool ok, const char *label)
{
	checks++;
	if (!ok) {
		fprintf(stderr, "FAIL %s: %s\n", names[fault], label);
		abort();
	}
}
static void nss_core_register_subsys_dp(struct nss_ctx_instance *ctx, unsigned ifnum,
					nss_wifili_callback_t a, nss_wifili_callback_t b,
					void *unused, struct net_device *dev, unsigned features)
{
	(void)ctx;
	(void)ifnum;
	(void)a;
	(void)b;
	(void)unused;
	(void)features;
	check(!registered, "duplicate live registration");
	registered = dev;
	registrations++;
}
static void nss_core_unregister_subsys_dp(struct nss_ctx_instance *ctx, unsigned ifnum)
{
	(void)ctx;
	(void)ifnum;
	check(registered != NULL, "unregister without registration");
	registered = NULL;
	unregistrations++;
}
static void nss_wifili_release_external_if(unsigned ifnum)
{
	(void)ifnum;
	releases++;
}
/* DRIVER_FUNCTIONS */
static unsigned ath11k_nss_get_target_type(struct ath11k_base *ab)
{
	(void)ab;
	return fault == UNKNOWN_TARGET ? 0 : 1;
}
static void *kzalloc(size_t size, int flags)
{
	(void)flags;
	if (fault == ALLOC)
		return NULL;
	void *p = calloc(1, size);
	assert(p);
	live_messages++;
	return p;
}
static void kfree(void *p)
{
	if (p) {
		check(live_messages == 1, "message lifetime");
		live_messages--;
		free(p);
	}
}
static bool of_property_read_bool(void *node, const char *name)
{
	(void)node;
	(void)name;
	return priority;
}
static void ath11k_nss_fill_srng_info(struct ath11k_base *ab, void *ring, int *info)
{
	(void)ab;
	(void)ring;
	*info = 7;
}
static int ath11k_nss_fill_tx_desc_info(struct ath11k_base *ab, struct nss_wifili_init_msg *msg)
{
	(void)ab;
	(void)msg;
	live_descriptors = true;
	return fault == DESCRIPTORS ? -ENOMEM : 0;
}
static void ath11k_nss_tx_desc_mem_free(struct ath11k_base *ab)
{
	(void)ab;
	live_descriptors = false;
}
static unsigned ath11k_nss_get_interface_type(struct ath11k_base *ab)
{
	(void)ab;
	return fault == INVALID_IF ? NSS_MAX_NET_INTERFACES : interface_number;
}
static void ath11k_nss_wifili_ext_callback_wrapper(void)
{
}
static void ath11k_nss_wifili_event_receive(void)
{
}
static int nss_cmn_get_state(struct nss_ctx_instance *ctx)
{
	return ctx->state;
}
static void nss_cmn_msg_init(int *cm, unsigned ifnum, int type, size_t size,
			     nss_wifili_msg_callback_t callback, void *app)
{
	(void)app;
	check(ifnum == interface_number && type == NSS_WIFILI_INIT_MSG &&
		  size == sizeof(struct nss_wifili_init_msg) && callback != NULL,
	      "init message contract");
	*cm = 1;
}
static void reinit_completion(int *complete)
{
	*complete = 0;
}
static nss_tx_status_t nss_wifili_tx_msg(struct nss_ctx_instance *ctx, struct nss_wifili_msg *msg)
{
	check(ctx == &nss_top_main.nss[0] && registered != NULL,
	      "send requires registered context");
	check(msg->msg.init.flags == (priority ? WIFILI_MULTISOC_THREAD_MAP_ENABLE : 0),
	      "radio priority flag");
	if (fault == NACK)
		((struct ath11k_base *)registered)->nss.response = 0;
	return fault == SEND ? -1 : 0;
}
static unsigned msecs_to_jiffies(unsigned ms)
{
	return ms;
}
static int wait_for_completion_timeout(int *complete, unsigned ticks)
{
	(void)complete;
	check(ticks == 6000, "bounded completion timeout requested");
	return fault == TIMEOUT ? 0 : 1;
}
#ifdef CPTCFG_ATH11K_NSS_MESH_SUPPORT
static void ath11k_debugfs_nss_soc_create(struct ath11k_base *ab)
{
	(void)ab;
}
static int ath11k_nss_mesh_capability(struct ath11k_base *ab)
{
	(void)ab;
	return 0;
}
#endif
/* INIT_FUNCTION */
int main(void)
{
	for (interface_number = 203; interface_number <= 205; interface_number++) {
		for (fault = NONE; fault < FAULTS; fault++) {
			struct device dev = {0};
			struct ath11k_base ab = {.dev = &dev};
			nss_top_main.nss[0].state = fault == UNREADY ? 0 : NSS_STATE_INITIALIZED;
			registered = NULL;
			registrations = unregistrations = releases = live_messages = 0;
			live_descriptors = false;
			priority = (interface_number % 2) == 0;
			int ret = ath11k_nss_init(&ab);
			scenarios++;
			if (fault == NONE) {
				check(ret == 0 && registered == (struct net_device *)&ab,
				      "success retains owned registration");
				check(registrations == 1 && unregistrations == 0 &&
					  live_descriptors,
				      "success resources remain available");
				check(ab.nss.ctx == &nss_top_main.nss[0],
				      "success context published");
				nss_unregister_wifili_if(ab.nss.if_num);
				ath11k_nss_tx_desc_mem_free(&ab);
			} else {
				int expected = fault == UNKNOWN_TARGET ? -ENOTSUPP
					       : fault == ALLOC	       ? -ENOMEM
								       : -EINVAL;
				check(ret == expected, "original error status preserved");
				check(registered == NULL, "registration survived failed init");
				check(!live_descriptors,
				      "descriptor resources survived failed init");
			}
			check(registrations == unregistrations && releases == unregistrations,
			      "exactly one unregister per registration");
			check(live_messages == 0, "message released on every outcome");
		}
	}
	printf("Actual init/register lifecycle: %u scenarios, %u checks passed\n", scenarios,
	       checks);
	return 0;
}
