#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <time.h>

#ifndef PROBE_ID
#define PROBE_ID 0
#endif

int main(void) {
    struct timespec entered;
    if (clock_gettime(CLOCK_MONOTONIC, &entered) != 0) return 1;
    uint64_t nanos = (uint64_t)entered.tv_sec * UINT64_C(1000000000)
        + (uint64_t)entered.tv_nsec;
    return printf("{\"entry_ns\":%" PRIu64 ",\"probe\":%d}\n", nanos, PROBE_ID) < 0;
}
