#include <switch.h>
#include "heman_level11_lab.h"
#include "sd_journal.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>

#define SLOT0 "sdmc:/switch/heman_lore_lab/progress0.bin"
#define SLOT1 "sdmc:/switch/heman_lore_lab/progress1.bin"

static FsFileSystem mock_fs;
static int mock_mounted;
static unsigned mount_calls;
static unsigned commit_calls;
static int fail_next_mount;
static int fail_next_commit;
static uint8_t solids[HM_LORE_LAB_CELLS];
static hm_world world;
static hm_level11_native_session game;

FsFileSystem *fsdevGetDeviceFileSystem(const char *name) {
    if (name && strcmp(name, "sdmc") == 0 && mock_mounted)
        return &mock_fs;
    return NULL;
}

Result fsdevMountSdmc(void) {
    ++mount_calls;
    if (fail_next_mount) {
        fail_next_mount = 0;
        return -1;
    }
    mock_mounted = 1;
    return 0;
}

Result fsdevCommitDevice(const char *name) {
    ++commit_calls;
    if (!name || strcmp(name, "sdmc") != 0 || !mock_mounted)
        return -1;
    if (fail_next_commit) {
        fail_next_commit = 0;
        return -1;
    }
    return 0;
}

static void boot(void) {
    assert(hm_level11_lab_init(&world, solids, sizeof(solids), &game)
           == HM_LORE_APPLIED);
}

static void walk(unsigned frames) {
    unsigned i;
    const hm_input right = {1.0f, 0u, 0u};
    for (i = 0u; i < frames; ++i)
        assert(hm_level11_session_step(&game, right, 1.0f / 60.0f, 0u)
               != HM_LORE_INVALID);
}

static void expect_size(const char *path, off_t expected) {
    struct stat info;
    assert(stat(path, &info) == 0);
    assert(info.st_size == expected);
}

static void corrupt_payload(const char *path) {
    FILE *file = fopen(path, "r+b");
    int byte;
    assert(file != NULL);
    assert(fseek(file, 24L, SEEK_SET) == 0);
    byte = fgetc(file);
    assert(byte != EOF);
    assert(fseek(file, 24L, SEEK_SET) == 0);
    assert(fputc(byte ^ 0x40, file) != EOF);
    assert(fclose(file) == 0);
}

static void append_extra_byte(const char *path) {
    FILE *file = fopen(path, "ab");
    assert(file != NULL);
    assert(fputc(0x7f, file) != EOF);
    assert(fclose(file) == 0);
}

static void write_short_file(const char *path) {
    uint8_t short_record[60] = {0};
    FILE *file = fopen(path, "wb");
    assert(file != NULL);
    assert(fwrite(short_record, 1u, sizeof(short_record), file) == sizeof(short_record));
    assert(fclose(file) == 0);
}

static int run_premounted_case(void) {
    hm_level11_native_session before;
    boot();
    before = game;
    /* Simulate libnx having mounted sdmc before this adapter is called. */
    mock_mounted = 1;
    assert(!hm_switch_lore_sd_load(&game));
    assert(mount_calls == 0u && mock_mounted && commit_calls == 0u);
    assert(memcmp(&before, &game, sizeof(game)) == 0);
    assert(access("sdmc:/switch/heman_lore_lab", F_OK) == 0);
    puts("STAGE113_SWITCH_SD_PREMOUNT_REUSE_PASS");
    return 0;
}

int main(int argc, char **argv) {
    hm_level11_native_session before;

    if (argc == 2 && strcmp(argv[1], "pre-mounted") == 0)
        return run_premounted_case();
    if (argc != 1)
        return 2;

    boot();
    assert(mount_calls == 0u && commit_calls == 0u && !mock_mounted);
    before = game;

    /* A failed initial mount must not mutate the live session or create paths. */
    fail_next_mount = 1;
    assert(!hm_switch_lore_sd_load(&game));
    assert(mount_calls == 1u && !mock_mounted);
    assert(memcmp(&before, &game, sizeof(game)) == 0);
    assert(access("sdmc:/switch", F_OK) != 0);

    /* The next explicit call mounts lazily, creates the lab path, then fails
     * closed because neither journal slot exists. */
    assert(!hm_switch_lore_sd_load(&game));
    assert(mount_calls == 2u && mock_mounted);
    assert(memcmp(&before, &game, sizeof(game)) == 0);
    assert(access("sdmc:/switch/heman_lore_lab", F_OK) == 0);

    walk(30u);
    assert(game.lore.collected_mask == 2u);
    assert(hm_switch_lore_sd_save(&game));
    assert(commit_calls == 1u);
    expect_size(SLOT0, 120);
    assert(access(SLOT1, F_OK) != 0);

    assert(hm_level11_session_grant_wall_crusher(&game, 1u) == HM_LORE_APPLIED);
    assert(hm_switch_lore_sd_save(&game));
    assert(commit_calls == 2u);
    expect_size(SLOT0, 120);
    expect_size(SLOT1, 120);

    /* A fresh native session loads the newest compatible generation. */
    boot();
    assert(hm_switch_lore_sd_load(&game));
    assert(game.lore.collected_mask == 2u);
    assert(game.lore.wall_crusher_unlocked == 1u);

    /* A corrupt newest record falls back to the older intact slot. */
    corrupt_payload(SLOT1);
    boot();
    assert(hm_switch_lore_sd_load(&game));
    assert(game.lore.collected_mask == 2u);
    assert(game.lore.wall_crusher_unlocked == 0u);

    /* Extra bytes make the remaining older record invalid too; failure must
     * preserve the caller's live session byte-for-byte. */
    append_extra_byte(SLOT0);
    before = game;
    assert(!hm_switch_lore_sd_load(&game));
    assert(memcmp(&before, &game, sizeof(game)) == 0);

    /* A truncated 60-byte record must also be rejected without mutating state. */
    write_short_file(SLOT0);
    before = game;
    assert(!hm_switch_lore_sd_load(&game));
    assert(memcmp(&before, &game, sizeof(game)) == 0);

    /* Exercise a filesystem-commit error. The adapter must not acknowledge the
     * save; corrupting its uncertain candidate must still leave generation 1. */
    assert(remove(SLOT0) == 0);
    assert(remove(SLOT1) == 0);
    boot();
    walk(30u);
    assert(hm_switch_lore_sd_save(&game));
    assert(hm_level11_session_grant_wall_crusher(&game, 1u) == HM_LORE_APPLIED);
    fail_next_commit = 1;
    assert(!hm_switch_lore_sd_save(&game));
    assert(commit_calls == 4u);
    expect_size(SLOT1, 120);
    corrupt_payload(SLOT1);
    boot();
    assert(hm_switch_lore_sd_load(&game));
    assert(game.lore.collected_mask == 2u);
    assert(game.lore.wall_crusher_unlocked == 0u);

    puts("STAGE113_SWITCH_SD_ADAPTER_MOCK_PASS");
    return 0;
}
