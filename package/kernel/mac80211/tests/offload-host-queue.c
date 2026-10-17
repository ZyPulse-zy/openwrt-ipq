// SPDX-License-Identifier: GPL-2.0-only
/* Complete actual source function is inserted below. Kernel operations are
 * fixtures; this checks host queue initialization, not firmware TID/AC. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
struct ethhdr { unsigned char h_dest[6]; };
static int atomic_read(const int *v) { return *v; }
#define IEEE80211_AC_BE 2
#define HAS_TX_QUEUE 1
#define SUPPORTS_NSS_OFFLOAD 2
#define NL80211_IFTYPE_AP_VLAN 5
#define SCAN_SW_SCANNING 1
#define SDATA_STATE_OFFCHANNEL 1
#define HT_AGG_STATE_OPERATIONAL 1
#define IEEE80211_QOS_CTL_TAG1D_MASK 7
#define GFP_ATOMIC 0
#define IEEE80211_TX_CTRL_MLO_LINK_UNSPEC 0
#define IEEE80211_TX_CTL_HW_80211_ENCAP 4
#define IEEE80211_TX_CTL_REQ_TX_STATUS 8
#define unlikely(x) (x)
#define rcu_dereference(x) (x)
#define container_of(ptr, type, member) ((type *)(void *)(ptr))
#define test_bit(bit, field) ((*(field) & (bit)) != 0)
struct ieee80211_key { int conf; };
struct ieee80211_tx_info {
 unsigned flags, hw_queue, status_data, status_data_idr;
 struct { void *vif, *hw_key; } control;
};
struct sk_buff { unsigned char data[6]; unsigned priority, queue_mapping, len; void *sk; struct ieee80211_tx_info info; };
struct ieee80211_local { struct { unsigned flags; } hw; unsigned scanning; };
struct ieee80211_sub_if_data {
 struct ieee80211_local *local;
 struct { unsigned type, hw_queue[4]; } vif;
 unsigned state;
 void *bss;
 union { struct { int num_mcast_sta; } vlan; int ap; } u;
};
struct net_device { int unused; };
struct tid_ampdu_tx { unsigned state, timeout, last_tx; };
struct sta_info {
 struct { struct tid_ampdu_tx *tid_tx[8]; } ampdu_mlme;
 struct { struct { unsigned packets[4], bytes[4]; } tx_stats; } deflink;
};
static unsigned selected_ac, selected_calls, sent, checks;
static const unsigned jiffies = 10;
static bool ieee80211_hw_check(const void *hw, unsigned flag) { return (((const struct ieee80211_local *)hw)->hw.flags & flag) != 0; }
static unsigned ieee80211_select_queue(struct ieee80211_sub_if_data *s, struct sta_info *st, struct sk_buff *skb) { (void)s;(void)st;(void)skb;selected_calls++;return selected_ac; }
static void skb_set_queue_mapping(struct sk_buff *skb, unsigned q) { skb->queue_mapping=q; }
static bool is_multicast_ether_addr(const void *p) { (void)p;return false; }
static struct sk_buff *skb_share_check(struct sk_buff *skb, int f) { (void)f;return skb; }
static void ieee80211_aggr_check(void *s, void *st, void *skb) { (void)s;(void)st;(void)skb; }
static void __ieee80211_subif_start_xmit(void *skb, void *dev, int f, int link, void *cookie) { (void)skb;(void)dev;(void)f;(void)link;(void)cookie;assert(false); }
static unsigned ieee80211_sdata_netdev_features(const void *s) { (void)s;return 0; }
static struct sk_buff *ieee80211_tx_skb_fixup(struct sk_buff *skb, unsigned f, void *dev) { (void)f;(void)dev;return skb; }
#define IEEE80211_SKB_CB(skb) (&(skb)->info)
#define skb_list_walk_safe(skb, seg, next) for ((seg)=(skb),(next)=NULL;(seg);(seg)=(next))
static bool sk_requests_wifi_status(const void *sk) { (void)sk;return false; }
static unsigned ieee80211_store_ack_skb(void *s, void *skb, void *f, void *cookie) { (void)s;(void)skb;(void)f;(void)cookie;return 0; }
static void dev_sw_netstats_tx_add(void *dev, unsigned n, unsigned len) { (void)dev;assert(n==1 && len==100); }
static void ieee80211_tpt_led_trig_tx(void *s, unsigned len) { (void)s;(void)len; }
static bool ieee80211_tx_8023(void *s, struct sk_buff *skb, void *st, bool pending) { (void)s;(void)st;(void)pending;assert(skb->info.hw_queue>=10 && skb->info.hw_queue<=13);sent++;return true; }
static void kfree_skb(void *skb) { (void)skb;assert(false); }

/* SOURCE_FUNCTION */

int main(void) {
 for (unsigned nss=0;nss<2;nss++) for (unsigned has=0;has<2;has++) for (unsigned cpu=0;cpu<8;cpu++) {
  struct ieee80211_local local={.hw={.flags=(has?HAS_TX_QUEUE:0)|(nss?SUPPORTS_NSS_OFFLOAD:0)}};
  struct ieee80211_sub_if_data s={.local=&local,.vif={.hw_queue={10,11,12,13}}};
  struct sta_info sta={0};struct net_device dev={0};struct sk_buff skb={.queue_mapping=cpu,.priority=0x12340006,.len=100};
  selected_ac=cpu%4;selected_calls=sent=0;
  ieee80211_8023_xmit(&s,&dev,&sta,NULL,&skb,0,0,NULL);
  unsigned expected=has?IEEE80211_AC_BE:selected_ac;
  assert(skb.info.hw_queue==s.vif.hw_queue[expected]);checks++;
  assert(selected_calls==(has?0:1) && sent==1);checks++;
  assert(skb.priority==0x12340006);checks++;
  assert(skb.queue_mapping==(has?cpu:selected_ac));checks++;
  assert(sta.deflink.tx_stats.packets[expected]==(nss?0:1));checks++;
 }
 printf("Actual complete 8023 function assertions passed: %u\n",checks);
}
