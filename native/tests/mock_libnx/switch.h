#ifndef HEMAN_TEST_MOCK_LIBNX_SWITCH_H
#define HEMAN_TEST_MOCK_LIBNX_SWITCH_H

#include <stdint.h>

/* Host-only stand-in for the tiny libnx filesystem surface used by sd_journal.c.
 * This verifies adapter behavior, not real Nintendo Switch filesystem semantics. */
typedef int32_t Result;
typedef struct { int marker; } FsFileSystem;

#define R_FAILED(result) ((result) < 0)
#define R_SUCCEEDED(result) ((result) >= 0)

FsFileSystem *fsdevGetDeviceFileSystem(const char *name);
Result fsdevMountSdmc(void);
Result fsdevCommitDevice(const char *name);

#endif
