"""Source-contract guards for the experimental Switch SD journal adapter.

These tests protect the intended opt-in boundary; they are not evidence that
libnx SD calls have succeeded on a console or in an emulator.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "switch_lore/source/main.c").read_text(encoding="utf-8")
SD = (ROOT / "switch_lore/source/sd_journal.c").read_text(encoding="utf-8")


def section(source, start, end):
    """Return one uniquely anchored source section, failing closed on drift."""
    if source.count(start) != 1:
        raise AssertionError(f"expected one source anchor: {start!r}")
    offset = source.index(start)
    end_offset = source.find(end, offset + len(start))
    if end_offset < 0:
        raise AssertionError(f"missing end anchor after: {start!r}")
    return source[offset:end_offset]


class SwitchLoreSdContractTests(unittest.TestCase):
    def test_sd_io_is_lazy_and_only_reached_through_fresh_zl_button_edges(self):
        before_loop = MAIN.split("while (appletMainLoop())", 1)[0]
        self.assertNotIn("hm_switch_lore_sd_save", before_loop)
        self.assertNotIn("hm_switch_lore_sd_load", before_loop)
        self.assertNotIn("fsdevMountSdmc", MAIN)

        save_branch = section(
            MAIN,
            "if ((held & HidNpadButton_ZL) && (down & HidNpadButton_L)) {",
            "} else if ((held & HidNpadButton_ZL) &&",
        )
        load_branch = section(
            MAIN,
            "} else if ((held & HidNpadButton_ZL) &&\n"
            "                   (down & HidNpadButton_R)) {",
            "        } else {\n"
            "            tick = hm_level11_lab_tick(&session, &saved,",
        )
        self.assertIn("hm_switch_lore_sd_save(&session)", save_branch)
        self.assertIn("hm_switch_lore_sd_load(&candidate)", load_branch)
        self.assertNotIn("hm_switch_lore_sd_load(&session)", MAIN)

    def test_plain_l_and_r_stay_on_the_ram_only_path(self):
        controls = section(
            MAIN,
            "static uint32_t controls(uint64_t buttons) {",
            "int main(int argc, char **argv) {",
        )
        self.assertIn("if (buttons & HidNpadButton_L) value |= HM_LAB_SAVE;", controls)
        self.assertIn("if (buttons & HidNpadButton_R) value |= HM_LAB_LOAD;", controls)
        ordinary_branch = section(
            MAIN,
            "        } else {\n"
            "            tick = hm_level11_lab_tick(&session, &saved,",
            "        }\n"
            "        if (tick == HM_LORE_INVALID)",
        )
        self.assertIn("controls(held), controls(down)", ordinary_branch)
        self.assertNotIn("hm_switch_lore_sd_", ordinary_branch)

    def test_sd_mount_is_lazy_and_reuses_an_existing_libnx_mount(self):
        mount = section(
            SD,
            "static int ensure_mounted(void) {",
            "static int ensure_directory(void) {",
        )
        self.assertIn("if (storage.is_mounted) return 1;", mount)
        self.assertIn('fsdevGetDeviceFileSystem("sdmc")', mount)
        self.assertIn("result=fsdevMountSdmc();", mount)
        self.assertLess(
            mount.index('fsdevGetDeviceFileSystem("sdmc")'),
            mount.index("result=fsdevMountSdmc();"),
        )

    def test_paths_are_confined_to_two_named_lab_slots(self):
        self.assertIn('#define STORAGE_DIR "sdmc:/switch/heman_lore_lab"', SD)
        filename = section(
            SD,
            "static int file_name(unsigned slot, char *name, size_t capacity) {",
            "static int read_slot(",
        )
        self.assertIn("if (slot>1u || !name || capacity<PATH_CAP) return 0;", filename)
        self.assertIn('STORAGE_DIR "/progress%u.bin"', filename)

    def test_read_rejects_short_extra_or_failed_streams(self):
        reader = section(SD, "static int read_slot(", "static int write_slot(")
        self.assertIn("fread(output,1u,HM_LEVEL11_JOURNAL_RECORD_SIZE,file)", reader)
        self.assertIn("extra=fgetc(file);", reader)
        self.assertIn("read_error=ferror(file);", reader)
        self.assertIn("closed=fclose(file);", reader)
        self.assertIn("count==HM_LEVEL11_JOURNAL_RECORD_SIZE && extra==EOF", reader)
        self.assertIn("!read_error && closed==0", reader)

    def test_write_flushes_closes_commits_and_propagates_each_failure(self):
        writer = section(SD, "static int write_slot(", "static hm_level11_journal_io journal_io(")
        write_pos = writer.index("fwrite(")
        flush_pos = writer.index("fflush(file)")
        close_pos = writer.index("closed=fclose(file)")
        commit_pos = writer.index('fsdevCommitDevice("sdmc")')
        self.assertLess(write_pos, flush_pos)
        self.assertLess(flush_pos, close_pos)
        self.assertLess(close_pos, commit_pos)
        self.assertIn("count==HM_LEVEL11_JOURNAL_RECORD_SIZE", writer)
        self.assertIn("!write_error", writer)
        self.assertIn("flushed==0", writer)
        self.assertIn("closed==0", writer)
        self.assertIn("R_SUCCEEDED(committed)", writer)

    def test_sd_load_commits_to_live_session_only_after_candidate_validation(self):
        load_branch = section(
            MAIN,
            "} else if ((held & HidNpadButton_ZL) &&\n"
            "                   (down & HidNpadButton_R)) {",
            "        } else {\n"
            "            tick = hm_level11_lab_tick(&session, &saved,",
        )
        load_pos = load_branch.index("hm_switch_lore_sd_load(&candidate)")
        encode_pos = load_branch.index("hm_level11_snapshot_encode(&candidate")
        commit_pos = load_branch.index("session=candidate;")
        self.assertLess(load_pos, encode_pos)
        self.assertLess(encode_pos, commit_pos)
        self.assertIn("sd_status=2u;", load_branch)
        self.assertIn("tick=HM_LORE_BLOCKED;", load_branch)


if __name__ == "__main__":
    unittest.main()
