# Stage 111 — a playable, completely synthetic Level 1-1 mechanics lab NRO

This is a **NEW, standalone and opt-in Switch homebrew build**, not a
replacement for the confirmed stable two-room or experimental
three-room NeXium paths. It uses exactly the same independently authored
native C99 `hm_step` physics, role-sealed `hm_level11_native_session`,
Wall Crusher gate and Bio/Concept Art 09 lore bookkeeping, and versioned
96-byte experimental save receipt that were host-tested in Stages 102–108.

The level geometry, icons and player silhouette are **fictional**.
The authoritative original `He-Man-v2.0.0.ipa` remains private and was
not inspected in this run; this is **not** a reconstructed iOS 1-1 level.

## New experimental Switch program

`switch_lore/source/main.c` uses libnx's actual framebuffer, actual
PadState buttons and a simple software renderer, with no proprietary
fonts, screenshots, sounds, textures or graphics. The shared native
`hm_level11_lab_tick()` maps controller levels to physics and rewards,
so the Switch application does not invent collision flags.

| Switch button | Test-world behavior |
| --- | --- |
| D-pad Left/Right | Walk at 60Hz in shared C99 physics |
| A | Jump on a new button press |
| X | Attack; requires release and new press at gate |
| Y | **Debug cheat**, explicitly grant Wall Crusher |
| B | Restart the tutorial player/inventory, keeping the RAM save slot |
| L | Save the current state in a **RAM-only** 96-byte receipt |
| R | Load the RAM-only receipt (if one exists) |
| Plus | Exit homebrew |

At startup, the left→right course contains the open Concept Art item
at x56, a hypothetical Wall Crusher sensor at x104, and the gated
Skeletor Bio pickup at x148. These numbers come from the deliberately
fabricated native test world, not from original iOS geometry or video.

The upper-left HUD has five rectangular lights, left to right:
Wall Crusher unlocked, gate opened, Bio earned, Concept Art earned,
and in-memory save present. An orange light indicates attack held,
and a green bar grows with the number of earned collectibles.
The magenta/cyan map markers darken after genuine C99 collection.
The gate marker changes from orange to green after a real native
attack contact and ability grant. This is a functional diagnostic
display, **not the original game's artwork or UI**.

## Host and Switch evidence

The host test `native/tests/test_level11_lab.c` calls the exact
same source-only C99 lab world and controller translator linked into
the Switch NRO, and verifies:

- A genuine native walk that touches Bio too early but earns only the
  open Concept Art;
- Save to RAM, restart, restore, debug grant Wall Crusher;
- Returning to the same gate, real fresh X attack, returning to Bio,
  finally earning it exactly once;
- Held-attack suppression, release and new press, jump and restart;
- Damaged saves, malformed button transitions and mutated tile arrays
  failing without minting rewards.

```sh
sh native/run_tests.sh gcc
sh native/run_tests.sh clang
```

The workflow `.github/workflows/switch-lore-lab.yml` separately
compiles with GCC and Clang ASan/UBSan, then builds the **actual AArch64
NRO** in the devkitPro container and verifies its NRO0 header. Successful
cross-compilation is not itself guest/HID/PNG or Switch hardware proof.

Build locally where devkitPro/libnx are installed:

```sh
export DEVKITPRO=/opt/devkitpro
make -C switch_lore clean all
```

Output: `switch_lore/heman_level11_lore_lab.nro`.

**Save is not persistent**: it exists in RAM until the application
exits. The format is our own lab design, not an emulation or port of
commercial iOS save contents. The game never opens the original IPA,
writes commercial assets, saves private map locations or connects to
the official level 1-1. No original paid upgrade/purchase system
is implemented; Y is an openly labelled synthetic test shortcut.

## What remains blocked

Genuine original iOS 1-1 fixture ownership, contact timing, camera
transform, collision geometry, character sprites, hit animations,
achievement semantics and source data still require independent
validation of the user-owned private IPA and video evidence before
a source-faithful level can be shipped. The tracking
[Issue #110](https://github.com/stanmasked/he-man-remake/issues/110)
remains OPEN; this opt-in NRO is a gameplay integration **test**, not
source-authenticity evidence.
