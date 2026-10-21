#include <switch.h>
#include <errno.h>
#include <stdio.h>
#include <sys/stat.h>
#include <string.h>

#include "heman_level11_journal.h"
#include "sd_journal.h"

#define STORAGE_DIR "sdmc:/switch/heman_lore_lab"
#define PATH_CAP 128u
typedef struct { int is_mounted; } sd_context;
static sd_context storage={0};

static int ensure_mounted(void) {
    Result result;
    if (storage.is_mounted) return 1;
    /* Existing libnx sdmc mount can be reused without remounting. */
    if (!fsdevGetDeviceFileSystem("sdmc")) {
        result=fsdevMountSdmc();
        if (R_FAILED(result)) return 0;
    }
    storage.is_mounted=1;
    return 1;
}
static int ensure_directory(void) {
    if (!ensure_mounted()) return 0;
    if (mkdir("sdmc:/switch",0777)!=0 && errno!=EEXIST) return 0;
    if (mkdir(STORAGE_DIR,0777)!=0 && errno!=EEXIST) return 0;
    return 1;
}
static int file_name(unsigned slot, char *name, size_t capacity) {
    int length;
    if (slot>1u || !name || capacity<PATH_CAP) return 0;
    length=snprintf(name,capacity,STORAGE_DIR "/progress%u.bin",slot);
    return length>0 && (size_t)length<capacity;
}
static int read_slot(void *ignored,unsigned slot,uint8_t *output) {
    char name[PATH_CAP];
    FILE *file;
    size_t count;
    int extra,read_error,closed;
    (void)ignored;
    if (!output || !file_name(slot,name,sizeof(name))) return 0;
    file=fopen(name,"rb");
    if (!file) return 0;
    count=fread(output,1u,HM_LEVEL11_JOURNAL_RECORD_SIZE,file);
    extra=fgetc(file);
    read_error=ferror(file);
    closed=fclose(file);
    /* EOF is valid only when the stream reached the true end cleanly.
     * A read error must not be mistaken for a well-formed 120-byte file. */
    return count==HM_LEVEL11_JOURNAL_RECORD_SIZE && extra==EOF &&
           !read_error && closed==0;
}
static int write_slot(void *ignored,unsigned slot,const uint8_t *bytes) {
    char name[PATH_CAP];
    FILE *file;
    size_t count;
    int write_error,flushed,closed;
    Result committed;
    (void)ignored;
    if (!bytes || !file_name(slot,name,sizeof(name))) return 0;
    file=fopen(name,"wb");
    if (!file) return 0;
    count=fwrite(bytes,1u,HM_LEVEL11_JOURNAL_RECORD_SIZE,file);
    write_error=ferror(file);
    flushed=fflush(file);
    closed=fclose(file);
    /* libnx explicitly requires a filesystem commit after each file close
     * following writes. Request it even after a short/error write, because
     * the inactive slot may already have been truncated or partly changed. */
    committed=fsdevCommitDevice("sdmc");
    /* The other previously valid slot remains untouched. Filesystem commit
     * improves durability but is not a proof against every power-loss mode. */
    return count==HM_LEVEL11_JOURNAL_RECORD_SIZE && !write_error &&
           flushed==0 && closed==0 && R_SUCCEEDED(committed);
}
static hm_level11_journal_io journal_io(void) {
    hm_level11_journal_io io;
    io.context=&storage;
    io.read_slot=read_slot;
    io.write_slot=write_slot;
    return io;
}
int hm_switch_lore_sd_save(const hm_level11_native_session *session) {
    hm_level11_journal_io io;
    if (!ensure_directory()) return 0;
    io=journal_io();
    return hm_level11_journal_store(session,&io,NULL);
}
int hm_switch_lore_sd_load(hm_level11_native_session *session) {
    hm_level11_journal_io io;
    if (!ensure_directory()) return 0;
    io=journal_io();
    return hm_level11_journal_restore(session,&io,NULL);
}
