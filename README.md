# Roland X0X — NES Drum Machine

A playable NES ROM port of the Roland drum machine series. This is an
adaptation for the NES, not a 1:1 clone of the browser Web Audio version:
the screen, the sound chip, and the number of voices are all NES-sized.

## What it is

- A real `.nes` file, mapper 0 (NROM), 32 KiB PRG, CHR RAM.
- A 16-step drum sequencer driven by the NES NMI at 60 Hz.
- 8 voice rows: BD, SD, LT, HT, RS, CB, OH, CH.
- Every row's machine source is swappable, independently. You can run an
  808 kick under a 909 snare, with 606 hats and 727 percussion — the same
  mix-and-match idea as the browser version.
- All sound is synthesized live by the NES APU. No Roland samples, no
  original Roland audio, and no copyrighted ROMs are used.

## Machines

808, 909, 606, 707, 727, 505, 626, C78 (CR-78), C80 (CR-8000).

Machine variation is real data, not just relabels. Each machine has its
own table entries for:

- BD / toms (Triangle): pitch-drop start and end timer values, and
  decay in frames. HT is derived from the same tom table at a higher
  pitch than LT.
- SD / hats (Noise): noise period, noise mode (white / metallic),
  volume, and length code. Closed hats use a shorter length than open
  hats from the same machine's hat table.
- Rim / cowbell (Pulse 1): pitch, volume, and length code.
- Snare body (Pulse 2): a short low tone added under the noise snare,
  pitch per machine.

Voices a machine never shipped in hardware (for example a 727 bass
drum) are synthesized in that machine's character as an approximation.
They are not original sounds from that machine.

## Screen

The PPU background shows:

- Title, and a row of step markers showing the currently playing step.
- 8 voice rows, each with a 2-letter voice label, a 3-character machine
  code (808, 909, 606, 707, 727, 505, 626, C78, C80), and 16 step cells.
  A filled block is a step that will sound; a dot is an empty step.
- A `>` at the left of the cursor row, and a `^` under the cursor step.
- A status line: BPM, PLAY / STOP, and the current preset's machine.
- Help lines at the bottom of the screen.

## Controls (standard NES controller)

- D-pad Up / Down: move the cursor between voice rows (wraps).
- D-pad Left / Right: move the cursor between steps (wraps).
- A: toggle the step under the cursor on / off.
- B: cycle that row's machine source (808 → 909 → 606 → 707 → 727 →
  505 → 626 → C78 → C80 → back to 808).
- Start: play / stop. Starting resets the sequencer to step 0.
- Select (press and release): cycle a full preset pattern. Each preset
  sets all rows to that preset's machine, after which B can mix
  individual rows again.
- Select + Up / Down (hold Select, then press Up / Down): change BPM
  by 5, clamped to 60–180. Default BPM is 120.

## Presets

9 preset patterns, one per machine, each 8 rows × 16 steps, stored as
2 bytes per row in the ROM. The default pattern on power-up is the
808 preset.

Preset order (Select cycles in this order): 808, 909, 606, 707, 727,
505, 626, C78, C80.

## Sequencer timing

16th-note timing is derived from BPM and the 60 Hz frame rate. Each
frame adds the BPM to a 16-bit accumulator; a step fires when the
accumulator reaches 900 (900 / BPM frames per 16th note on average).
At 120 BPM that averages 7.5 frames per step, alternating 7 and 8
frames, so tempo stays accurate without rounding drift.

## APU channel mapping and priority

Only one voice can sound on a channel at a time. If several voices on
the same channel are active on the same step, the first in this order
wins for that step:

- Triangle ($4008–$400B): BD, then LT, then HT.
- Noise ($400C–$400F): SD, then OH, then CH.
- Pulse 1 ($4000–$4003): RS, then CB.
- Pulse 2 ($4004–$4007): snare body tone, added under an SD hit.

The triangle pitch drop is done in software: on each frame the
triangle timer is stepped from its start value toward its end value
until its decay frames run out, then the channel is silenced.

## How to run it

1. Build (or rebuild) the ROM:
   ```
   python3 build_rom.py
   ```
   This writes `roland-x0x.nes` in this folder. No cc65 or other
   assembler is needed — `build_rom.py` contains its own minimal
   two-pass 6502 assembler (labels, `.byte` / `.word`, and the
   opcodes and addressing modes this code uses).
2. Open `roland-x0x.nes` in a standard NES emulator, for example
   FCEUX or Mesen. Load it as a normal mapper 0 / NROM ROM; no
   special settings are needed. CHR RAM is used, so the header CHR
   size is 0 and the tiles are uploaded by the code at startup.
3. Press Start to play. Use the controls above to edit steps,
   swap machine sources, and change presets and tempo.

## Files

- `build_rom.py` — the assembler and ROM source; running it writes
  the ROM and validates the header, size, and vectors.
- `roland-x0x.nes` — the built ROM (32,784 bytes: 16-byte iNES
  header + 32,768 bytes PRG).
- `README.md` — this file.

ROM details, as verified by `build_rom.py`: iNES magic `NES\x1A`,
PRG size 2 × 16 KiB, CHR size 0 (CHR RAM), mapper 0, vectors
NMI $81D6, Reset $8000, IRQ $822B, all inside PRG ($8000–$FFFF),
total file size matches the header, and the assembler reports no
unresolved labels. Tested in Delta on iPhone, Oct 27, 2026:
loads, plays, and edits with no screen glitching; sound is
thinner/quieter than the browser version, as expected on NES
hardware.

## Limitations — read honestly

- This is an NES adaptation. The NES APU has only 5 channels, so
  voices share channels (see the priority list above), and the
  browser version's 16 voice slots, per-voice Tune / Decay / Tone
  knobs, Drive / Glue, and Tape recorder are not in this ROM.
- Sound character is an approximation within what the NES APU can
  do (triangle pitch drops, noise period / mode, and pulse tones).
  It is not a sample-accurate reproduction of any Roland machine.
- Audible output in a real emulator was NOT verified here: no NES
  emulator was available in the build environment, so the ROM was
  validated by assembling it cleanly and checking the header, size,
  vectors, preset bytes, and machine tables — not by listening to
  it. Play it in FCEUX or Mesen and confirm the sound on a real
  emulator before treating it as finished.

## Donations

- Ethereum: `0x2D4B15760e621af2aC100EC8e39A10D57621E4AC`
- Bitcoin: `bc1qvl6sy99kn9rll3jjzu96vfkmezcfjq6yf58qd9`
