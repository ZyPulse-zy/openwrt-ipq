// SPDX-License-Identifier: GPL-2.0-or-later
/* The production loader runs unchanged except for its input object path. */
#include "qosify.h"
static const char *test_object;
#undef CLASSIFY_PROG_PATH
#define CLASSIFY_PROG_PATH test_object
#include QOSIFY_LOADER_SOURCE

static bool private_namespaces(void)
{
	const char *names[] = { "net", "mnt" };
	const char *vars[] = { "QOSIFY_PARENT_NETNS", "QOSIFY_PARENT_MNTNS" };
	char path[64], value[128];
	int i, n;

	if (geteuid())
		return false;
	for (i = 0; i < 2; i++) {
		const char *parent = getenv(vars[i]);
		snprintf(path, sizeof(path), "/proc/self/ns/%s", names[i]);
		n = readlink(path, value, sizeof(value) - 1);
		if (!parent || n < 0)
			return false;
		value[n] = 0;
		if (!strcmp(parent, value))
			return false;
	}
	return true;
}

int main(int argc, char **argv)
{
	unsigned flags;
	if (!private_namespaces()) {
		fputs("Refusing loader test without private root network and mount namespaces\n", stderr);
		return 2;
	}
	if (argc != 3)
		return 2;
	test_object = argv[1];
	if (qosify_loader_init())
		return 1;
	printf("{\"header_sizes\":{\"class_map\":%zu,\"ipv4_map\":%zu,\"ipv6_map\":%zu}}\n",
		sizeof(struct qosify_class), sizeof(struct qosify_ip_map_val), sizeof(struct qosify_ip_map_val));
	for (flags = 0; flags < 4; flags++) {
		struct bpf_prog_info info = {};
		uint32_t len = sizeof(info);
		uint32_t maps[32], actual_flags = 99, i;
		int fd;
		const char *suffix = qosify_get_program(flags, &fd);
		if (!suffix)
			return 1;
		info.nr_map_ids = ARRAY_SIZE(maps);
		info.map_ids = (uint64_t)(uintptr_t) maps;
		if (bpf_obj_get_info_by_fd(fd, &info, &len)) {
			perror("program info with map IDs");
			return 1;
		}
		if (info.nr_map_ids > ARRAY_SIZE(maps))
			return 1;
		for (i = 0; i < info.nr_map_ids; i++) {
			struct bpf_map_info map = {};
			uint32_t map_len = sizeof(map), key = 0;
			int map_fd = bpf_map_get_fd_by_id(maps[i]);
			if (map_fd < 0 || bpf_obj_get_info_by_fd(map_fd, &map, &map_len))
				return 1;
			if (strstr(map.name, "rodata") && map.value_size == sizeof(actual_flags)) {
				if (bpf_map_lookup_elem(map_fd, &key, &actual_flags))
					return 1;
			}
			close(map_fd);
		}
		if (actual_flags != flags) {
			fprintf(stderr, "Kernel flags expected=%u actual=%u maps=%u\n", flags, actual_flags, info.nr_map_ids);
			return 1;
		}
		printf("{\"flags\":%u,\"actual_kernel_flags\":%u,\"suffix\":\"%s\",\"id\":%u}\n", flags, actual_flags, suffix, info.id);
	}
#ifdef TEST_LOADER_STOP
	if (!strcmp(argv[2], "stop"))
		qosify_loader_stop();
#endif
	return 0;
}
