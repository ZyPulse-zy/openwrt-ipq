// SPDX-License-Identifier: GPL-2.0-only
/* The runner inserts the complete real source function at SOURCE_FUNCTION.
 * Only kernel synchronization, peer lookup and the wire-struct fixture are
 * simulated; this is not a full module build or firmware ABI test. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
typedef uint64_t u64;
typedef uint32_t u32;
#define NSS_WIFILI_TQM_RR_MAX 4
#define ATH11K_DBG_NSS 0
#define ath11k_dbg(...) ((void)0)
#define rcu_read_lock() ((void)0)
#define rcu_read_unlock() ((void)0)
#define spin_lock_bh(p) ((void)(p))
#define spin_unlock_bh(p) ((void)(p))
#define ATH11K_NSS_TXRX_NETDEV_STATS(direction, dev, bytes, packets) ((void)(dev))
static u64 jiffies=1234;
struct peer_stats {
 u32 tx_packets,tx_bytes,tx_retries,tx_failed,rx_packets,rx_bytes,rx_dropped;
 u32 tx_amsdu,tx_non_amsdu,tx_ofdma,tx_failed_retries,tx_multiple_retries;
 u32 tx_mpdu_retries,tx_mpdu_total_retries,rx_amsdu,rx_non_amsdu,rx_retries;
 u32 rx_intra_bss,rx_intra_bss_fail,rx_mic_err,rx_decrypt_err;
 u64 last_ack,last_rx;
};
struct nss_wifili_peer_ctrl_stats {
 int peer_id;
 struct { u32 tx_success_cnt,tx_mcast_cnt,tx_ucast_cnt,tx_bcast_cnt;
  u32 tx_mcast_bytes,tx_ucast_bytes,tx_bcast_bytes,retries,amsdu_cnt,non_amsdu_cnt,ofdma;
  struct {u32 drop_stats[NSS_WIFILI_TQM_RR_MAX];} dropped;
 } tx;
 struct {u32 rx_recvd,rx_recvd_bytes,amsdu_cnt,non_amsdu_cnt,rx_intra_bss_pkts_num,rx_intra_bss_fail_num;
  struct{u32 mic_err,decrypt_err;}err;
 }rx;
 struct{u32 tx_failed_retry_count,tx_multiple_retry_count,tx_mpdu_retry_count,tx_mpdu_total_retry_count,rx_retry_count;}retry;
};
struct nss_wifili_peer_stats{int npeers;struct nss_wifili_peer_ctrl_stats wpcs[32];};
struct ath11k_peer{void *sta,*vif;struct{struct peer_stats *nss_stats;bool ext_vdev_up;void *ext_vif;}nss;};
struct ath11k { int radio; };
struct ath11k_pdev { struct ath11k *ar; };
static struct ath11k radio;
struct ath11k_base{struct{bool stats_enabled;}nss;int base_lock;int num_radios;struct ath11k_pdev pdevs[1];};
static struct ath11k_peer peers[32];static struct peer_stats totals[32];
static struct ath11k_peer *ath11k_peer_find_by_id(struct ath11k *ar,int id){(void)ar;return id>=0&&id<32?&peers[id]:NULL;}
/* SOURCE_FUNCTION */
static unsigned checks=0;
static void check(bool ok,const char *label){checks++;if(!ok){fprintf(stderr,"FAIL %s\n",label);assert(ok);}}
static void setup(void){memset(totals,0,sizeof(totals));memset(peers,0,sizeof(peers));for(int i=0;i<32;i++){peers[i].sta=(void*)1;peers[i].nss.nss_stats=&totals[i];}}
int main(void){
 struct ath11k_base ab={.nss={.stats_enabled=true},.num_radios=1,.pdevs={{.ar=&radio}}};
 struct nss_wifili_peer_stats msg={.npeers=2};setup();
 for(int i=0;i<2;i++){msg.wpcs[i].peer_id=i;msg.wpcs[i].tx.tx_ucast_cnt=10;msg.wpcs[i].tx.tx_ucast_bytes=1000;}
 msg.wpcs[0].tx.dropped.drop_stats[0]=2;msg.wpcs[1].tx.dropped.drop_stats[0]=5;
 ath11k_nss_get_peer_stats(&ab,&msg);
 check(totals[0].tx_failed==2,"first peer drop total");
 check(totals[1].tx_failed==5,"second peer receives only its own drops");
 check(totals[0].tx_bytes==1000&&totals[1].tx_packets==10,"other counters preserved");
 ath11k_nss_get_peer_stats(&ab,&msg);check(totals[0].tx_failed==4&&totals[1].tx_failed==10,"repeated message");
 setup();struct nss_wifili_peer_ctrl_stats swap=msg.wpcs[0];msg.wpcs[0]=msg.wpcs[1];msg.wpcs[1]=swap;
 ath11k_nss_get_peer_stats(&ab,&msg);check(totals[0].tx_failed==2&&totals[1].tx_failed==5,"order independence");
 setup();msg=(struct nss_wifili_peer_stats){.npeers=32};
 for(int i=0;i<32;i++){msg.wpcs[i].peer_id=i;for(int j=0;j<NSS_WIFILI_TQM_RR_MAX;j++)msg.wpcs[i].tx.dropped.drop_stats[j]=i+j;}
 ath11k_nss_get_peer_stats(&ab,&msg);
 for(int i=0;i<32;i++)check(totals[i].tx_failed==(u32)(4*i+6),"32 peers, all drop bins");
 setup();msg.wpcs[3].peer_id=99;peers[5].sta=NULL;peers[7].nss.ext_vdev_up=true;
 ath11k_nss_get_peer_stats(&ab,&msg);
 check(totals[3].tx_failed==0&&totals[5].tx_failed==0,"missing and unassociated peer skipped");
 check(totals[4].tx_failed==22&&totals[6].tx_failed==30&&totals[7].tx_failed==34,"skip and ext-vdev isolation");
 setup();ab.nss.stats_enabled=false;ath11k_nss_get_peer_stats(&ab,&msg);check(totals[1].tx_failed==0,"statistics disabled");ab.nss.stats_enabled=true;
 msg=(struct nss_wifili_peer_stats){.npeers=2};msg.wpcs[0].peer_id=0;msg.wpcs[1].peer_id=1;
 msg.wpcs[0].tx.dropped.drop_stats[0]=7;totals[0].tx_failed=UINT32_MAX-2;
 ath11k_nss_get_peer_stats(&ab,&msg);check(totals[0].tx_failed==4&&totals[1].tx_failed==0,"existing wrap semantics and zero peer");
 printf("Actual complete peer statistics function assertions passed: %u\n",checks);return 0;
}
