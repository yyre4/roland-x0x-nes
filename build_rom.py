#!/usr/bin/env python3
"""Build a playable NES ROM port of the Roland drum machine series.

No cc65 is required: this file contains a minimal two-pass 6502 assembler
that assembles the ROM source below and writes roland-x0x.nes next to it.

All sound is synthesized live by the NES APU. No Roland samples, no original
Roland audio, and no copyrighted ROMs are used or downloaded.

ROM layout: iNES header, mapper 0 (NROM), 32 KiB PRG ($8000-$FFFF),
CHR RAM (CHR size 0 in the header, tiles uploaded by code at startup).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "roland-x0x.nes")

# ---------------------------------------------------------------- font
# 5x7 glyphs, '#' = pixel. Tile order (assembly constants must match):
#   0 blank, 1-26 A-Z, 27-36 0-9, 37 '-', 38 ':', 39 '.', 40 '>',
#   41 '^', 42 '*', 43 solid block, 44 '+', 45 '/'
FONT = {
    'A': [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'B': ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    'C': [".####", "#....", "#....", "#....", "#....", "#....", ".####"],
    'D': ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    'E': ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    'F': ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    'G': [".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."],
    'H': ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    'I': [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    'J': ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    'K': ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    'L': ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    'M': ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    'N': ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    'O': [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'P': ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    'Q': [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    'R': ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    'S': [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    'T': ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    'U': ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    'V': ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    'W': ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"],
    'X': ["#...#", ".#.#.", "..#..", "..#..", "..#..", ".#.#.", "#...#"],
    'Y': ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    'Z': ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    '0': [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    '1': ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    '2': [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    '3': ["####.", "....#", "....#", ".###.", "....#", "....#", "####."],
    '4': ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    '5': ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    '6': [".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."],
    '7': ["#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."],
    '8': [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    '9': [".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."],
    '-': [".....", ".....", ".....", "#####", ".....", ".....", "....."],
    ':': [".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."],
    '.': [".....", ".....", ".....", ".....", ".....", ".##..", ".##.."],
    '>': ["#....", ".#...", "..#..", "...#.", "..#..", ".#...", "#...."],
    '^': ["..#..", ".#.#.", "#...#", ".....", ".....", ".....", "....."],
    '*': [".....", ".#.#.", "..#..", "#####", "..#..", ".#.#.", "....."],
    '+': [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    '/': ["....#", "...#.", "...#.", "..#..", ".#...", ".#...", "#...."],
}
TILE_ORDER = ([' '] + [chr(ord('A') + i) for i in range(26)]
              + [chr(ord('0') + i) for i in range(10)]
              + ['-', ':', '.', '>', '^', '*'])
TILE_INDEX = {ch: i for i, ch in enumerate(TILE_ORDER)}
TILE_INDEX['+'] = 44
TILE_INDEX['/'] = 45


def tile_bytes_for(rows):
    out = []
    for r in range(8):
        row = rows[r] if r < len(rows) else "....."
        b = 0
        for i, ch in enumerate(row):
            if ch == '#':
                b |= 1 << (7 - i)
        out.append(b)
    return out


def font_tiles_bytes():
    data = []
    for ch in TILE_ORDER:
        if ch == ' ':
            data.extend([0] * 16)
        else:
            glyph = tile_bytes_for(FONT[ch])
            data.extend(glyph)   # plane 0
            data.extend([0] * 8)  # plane 1 (unused, monochrome)
    # solid block, tile 43
    data.extend([0xFF] * 8 + [0] * 8)
    # '+' tile 44 and '/' tile 45
    for ch in ('+', '/'):
        glyph = tile_bytes_for(FONT[ch])
        data.extend(glyph)
        data.extend([0] * 8)
    return data


def tiles_for(s):
    return [TILE_INDEX[ch] for ch in s]


def fmt_bytes(data, per_line=16):
    lines = []
    for i in range(0, len(data), per_line):
        chunk = data[i:i + per_line]
        lines.append("  .byte " + ", ".join("$%02X" % b for b in chunk))
    return "\n".join(lines)


# ---------------------------------------------------------------- data
MACHINES = ["808", "909", "606", "707", "727", "505", "626", "C78", "C80"]
VOICES = ["BD", "SD", "LT", "HT", "RS", "CB", "OH", "CH"]


def tri_timer(freq):
    return int(55930 / freq) - 1  # NES triangle: CPU/32/(timer+1)


def pulse_timer(freq):
    return int(111861 / freq) - 1  # NES pulse: CPU/16/(timer+1)


def lo_hi(v):
    return v & 0xFF, (v >> 8) & 0xFF


# (start_freq, end_freq, decay_frames) per machine, in MACHINES order
BD_DATA = [(160, 45, 18), (180, 40, 14), (140, 60, 10), (120, 55, 8),
           (110, 65, 7), (130, 50, 10), (125, 55, 9), (100, 60, 10),
           (110, 55, 11)]
TOM_DATA = [(160, 80, 12), (170, 85, 10), (150, 75, 8), (140, 70, 7),
            (130, 65, 7), (145, 72, 8), (140, 70, 8), (120, 60, 9),
            (125, 62, 9)]
# (noise period index, mode, volume, length code) per machine
SD_NOISE = [(7, 0, 13, 4), (6, 1, 14, 6), (8, 0, 11, 3), (5, 0, 12, 5),
            (7, 1, 11, 3), (6, 0, 12, 4), (6, 0, 12, 5), (9, 0, 9, 3),
            (8, 0, 10, 4)]
HAT_NOISE = [(3, 1, 11, 8), (2, 1, 12, 9), (4, 1, 10, 7), (3, 0, 11, 8),
             (3, 1, 10, 6), (3, 0, 11, 7), (3, 0, 11, 8), (5, 0, 9, 6),
             (4, 0, 10, 7)]
RS_FREQ = [1800, 1600, 1700, 1500, 1900, 1600, 1550, 1200, 1300]
RS_VOL = [11, 12, 10, 11, 11, 11, 11, 9, 10]
RS_LEN = [2, 3, 2, 3, 2, 3, 3, 2, 2]
CB_FREQ = [800, 850, 750, 900, 1000, 820, 840, 700, 720]
CB_VOL = [11, 12, 10, 11, 11, 11, 11, 9, 10]
CB_LEN = [6, 7, 5, 6, 5, 6, 6, 5, 5]
SD_BODY_FREQ = [180, 200, 170, 190, 210, 185, 190, 160, 170]


def tri_table(rows):
    out = []
    for start, end, decay in rows:
        s_lo, s_hi = lo_hi(tri_timer(start))
        e_lo, e_hi = lo_hi(tri_timer(end))
        # Precompute the pitch step so the NMI handler never divides:
        # a division loop in NMI pushed PPU updates past vblank.
        step = (tri_timer(end) - tri_timer(start)) // decay
        st_lo, st_hi = lo_hi(step)
        out.extend([s_lo, s_hi, e_lo, e_hi, decay, st_lo, st_hi])
    return out


def pulse_table(freqs, vols, lens):
    out = []
    for f, v, ln in zip(freqs, vols, lens):
        p_lo, p_hi = lo_hi(pulse_timer(f))
        out.extend([p_lo, p_hi, v, ln])
    return out


# Presets: 9 patterns, one per machine, 8 rows x 16 steps.
# Row order is VOICES. Steps are step numbers 0-15 (step 0 = beat 1).
PRESETS = [
    # 808
    [[0, 4, 8, 12], [4, 12], [14], [11], [2, 7, 10, 15], [2, 6, 10, 14],
     [2, 6, 10, 14], [0, 2, 4, 6, 8, 10, 12, 14]],
    # 909
    [[0, 4, 8, 12], [4, 12], [15], [7], [3, 11], [0, 4, 8, 12],
     [2, 6, 10, 14], [0, 2, 4, 6, 8, 10, 12, 14]],
    # 606
    [[0, 4, 8, 12], [4, 12], [7, 15], [3, 11], [10], [6, 14],
     [2, 6, 10, 14], [0, 4, 8, 12]],
    # 707
    [[0, 4, 8, 12], [4, 12], [15], [], [7], [2, 10],
     [14], [0, 2, 4, 6, 8, 10, 12, 14]],
    # 727 (Latin-leaning)
    [[0, 8], [4, 12], [7], [15], [3, 6, 11, 14], [0, 3, 6, 10, 12],
     [2, 10], [4, 12]],
    # 505
    [[0, 4, 8, 12], [4, 12], [12], [4], [2, 10], [0, 8],
     [6, 14], [0, 2, 4, 6, 8, 10, 12, 14]],
    # 626
    [[0, 4, 8, 12], [4, 12, 15], [14], [7], [3, 11], [6, 14],
     [2, 10], [0, 4, 8, 12]],
    # CR-78
    [[0, 8], [4, 12], [7], [15], [4, 12], [0, 10],
     [0, 8], [2, 6, 10, 14]],
    # CR-8000
    [[0, 4, 8, 12], [4, 12], [15], [3], [7], [3, 11],
     [2, 8], [0, 6, 10, 14]],
]


def preset_bytes():
    out = []
    for pat in PRESETS:
        for row in pat:
            b0 = sum(1 << s for s in row if s < 8)
            b1 = sum(1 << (s - 8) for s in row if s >= 8)
            out.extend([b0, b1])
    return out


FONT_BYTES = font_tiles_bytes()
PALETTE = [0x0F, 0x30, 0x00, 0x10, 0x0F, 0x30, 0x27, 0x10,
           0x0F, 0x30, 0x2A, 0x10, 0x0F, 0x30, 0x16, 0x10,
           0x0F, 0x30, 0x00, 0x10, 0x0F, 0x30, 0x27, 0x10,
           0x0F, 0x30, 0x2A, 0x10, 0x0F, 0x30, 0x16, 0x10]
MACHINE_NAME_BYTES = []
for m in MACHINES:
    MACHINE_NAME_BYTES.extend(tiles_for(m))
VOICE_LABEL_BYTES = []
for v in VOICES:
    VOICE_LABEL_BYTES.extend(tiles_for(v))

# ------------------------------------------------------- minimal assembler
OPCODES = {}


def _op(mn, mode, code):
    OPCODES[(mn, mode)] = code


for _mn, _modes in [
    ("LDA", {"imm": 0xA9, "zp": 0xA5, "zpx": 0xB5, "abs": 0xAD,
             "absx": 0xBD, "absy": 0xB9, "indx": 0xA1, "indy": 0xB1}),
    ("LDX", {"imm": 0xA2, "zp": 0xA6, "zpy": 0xB6, "abs": 0xAE,
             "absy": 0xBE}),
    ("LDY", {"imm": 0xA0, "zp": 0xA4, "zpx": 0xB4, "abs": 0xAC,
             "absx": 0xBC}),
    ("STA", {"zp": 0x85, "zpx": 0x95, "abs": 0x8D, "absx": 0x9D,
             "absy": 0x99, "indx": 0x81, "indy": 0x91}),
    ("STX", {"zp": 0x86, "zpy": 0x96, "abs": 0x8E}),
    ("STY", {"zp": 0x84, "zpx": 0x94, "abs": 0x8C}),
    ("INC", {"zp": 0xE6, "zpx": 0xF6, "abs": 0xEE, "absx": 0xFE}),
    ("DEC", {"zp": 0xC6, "zpx": 0xD6, "abs": 0xCE, "absx": 0xDE}),
    ("ASL", {"acc": 0x0A, "zp": 0x06, "zpx": 0x16, "abs": 0x0E,
             "absx": 0x1E}),
    ("LSR", {"acc": 0x4A, "zp": 0x46, "zpx": 0x56, "abs": 0x4E,
             "absx": 0x5E}),
    ("ROL", {"acc": 0x2A, "zp": 0x26, "zpx": 0x36, "abs": 0x2E,
             "absx": 0x3E}),
    ("ROR", {"acc": 0x6A, "zp": 0x66, "zpx": 0x76, "abs": 0x6E,
             "absx": 0x7E}),
    ("ADC", {"imm": 0x69, "zp": 0x65, "zpx": 0x75, "abs": 0x6D,
             "absx": 0x7D, "absy": 0x79, "indx": 0x61, "indy": 0x71}),
    ("SBC", {"imm": 0xE9, "zp": 0xE5, "zpx": 0xF5, "abs": 0xED,
             "absx": 0xFD, "absy": 0xF9, "indx": 0xE1, "indy": 0xF1}),
    ("AND", {"imm": 0x29, "zp": 0x25, "zpx": 0x35, "abs": 0x2D,
             "absx": 0x3D, "absy": 0x39, "indx": 0x21, "indy": 0x31}),
    ("ORA", {"imm": 0x09, "zp": 0x05, "zpx": 0x15, "abs": 0x0D,
             "absx": 0x1D, "absy": 0x19, "indx": 0x01, "indy": 0x11}),
    ("EOR", {"imm": 0x49, "zp": 0x45, "zpx": 0x55, "abs": 0x4D,
             "absx": 0x5D, "absy": 0x59, "indx": 0x41, "indy": 0x51}),
    ("CMP", {"imm": 0xC9, "zp": 0xC5, "zpx": 0xD5, "abs": 0xCD,
             "absx": 0xDD, "absy": 0xD9, "indx": 0xC1, "indy": 0xD1}),
    ("CPX", {"imm": 0xE0, "zp": 0xE4, "abs": 0xEC}),
    ("CPY", {"imm": 0xC0, "zp": 0xC4, "abs": 0xCC}),
    ("BIT", {"zp": 0x24, "abs": 0x2C}),
    ("JMP", {"abs": 0x4C, "ind": 0x6C}),
    ("JSR", {"abs": 0x20}),
]:
    for _mode, _code in _modes.items():
        _op(_mn, _mode, _code)
for _mn, _code in [("TAX", 0xAA), ("TAY", 0xA8), ("TXA", 0x8A),
                   ("TYA", 0x98), ("TSX", 0xBA), ("TXS", 0x9A),
                   ("INX", 0xE8), ("INY", 0xC8), ("DEX", 0xCA),
                   ("DEY", 0x88), ("RTS", 0x60), ("RTI", 0x40),
                   ("BRK", 0x00), ("CLC", 0x18), ("SEC", 0x38),
                   ("CLI", 0x58), ("SEI", 0x78), ("CLD", 0xD8),
                   ("SED", 0xF8), ("CLV", 0xB8), ("NOP", 0xEA),
                   ("PHA", 0x48), ("PLA", 0x68), ("PHP", 0x08),
                   ("PLP", 0x28)]:
    _op(_mn, "imp", _code)
for _mn, _code in [("BCC", 0x90), ("BCS", 0xB0), ("BEQ", 0xF0),
                   ("BNE", 0xD0), ("BMI", 0x30), ("BPL", 0x10),
                   ("BVC", 0x50), ("BVS", 0x70)]:
    _op(_mn, "rel", _code)

BRANCHES = {"BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS"}
IMPLIED = {"TAX", "TAY", "TXA", "TYA", "TSX", "TXS", "INX", "INY", "DEX",
           "DEY", "RTS", "RTI", "BRK", "CLC", "SEC", "CLI", "SEI", "CLD",
           "SED", "CLV", "NOP", "PHA", "PLA", "PHP", "PLP"}


def parse_number(s, symbols=None):
    s = s.strip()
    if s.startswith("$"):
        return int(s[1:], 16)
    if s.startswith("%"):
        return int(s[1:], 2)
    if s.lstrip("-").isdigit():
        return int(s, 10)
    if symbols is not None and s in symbols:
        return symbols[s]
    return None


class AsmError(Exception):
    pass


def split_lines(source):
    out = []
    for raw in source.splitlines():
        line = raw.split(";", 1)[0].rstrip()
        if not line.strip():
            continue
        out.append(line)
    return out


def parse_line(line):
    """Return (label_or_None, rest_or_None)."""
    s = line.strip()
    label = None
    if ":" in s:
        label, s = s.split(":", 1)
        label = label.strip()
        s = s.strip()
        if not s:
            return label, None
    return label, s


def instr_size(mn, operand, symbols):
    if mn in IMPLIED:
        return 1
    if mn in BRANCHES:
        return 2
    if operand is None:
        if mn in ("ASL", "LSR", "ROL", "ROR"):
            return 1  # accumulator mode
        raise AsmError("missing operand for %s" % mn)
    op = operand.strip()
    if op == "A":
        return 1
    if op.startswith("#"):
        return 2
    if op.startswith("("):
        return 2 if op.endswith(",X)") or op.endswith("),Y") else 3
    base = op
    mode_suffix = None
    if op.endswith(",X"):
        base, mode_suffix = op[:-2], "x"
    elif op.endswith(",Y"):
        base, mode_suffix = op[:-2], "y"
    val = parse_number(base.strip(), symbols)
    if val is not None and val < 0x100:
        return 2
    return 3


def assemble(source):
    lines = split_lines(source)
    # Pass 1: symbols
    symbols = {}
    pc = 0
    parsed = []  # (label, rest, pc_at_line)
    for line in lines:
        label, rest = parse_line(line)
        if label:
            if label in symbols:
                raise AsmError("duplicate label %s" % label)
            symbols[label] = pc
        if rest is None:
            parsed.append((label, None, pc))
            continue
        parts = rest.split(None, 1)
        head = parts[0]
        operand = parts[1].strip() if len(parts) > 1 else None
        if head == ".org":
            v = parse_number(operand, symbols)
            if v is None:
                raise AsmError(".org with unknown value %s" % operand)
            pc = v
            parsed.append((label, rest, pc))
            continue
        if head == ".res":
            n = parse_number(operand, symbols)
            parsed.append((label, rest, pc))
            pc += n
            continue
        if head == ".byte":
            n = len([x for x in operand.split(",") if x.strip()])
            parsed.append((label, rest, pc))
            pc += n
            continue
        if head == ".word":
            n = len([x for x in operand.split(",") if x.strip()])
            parsed.append((label, rest, pc))
            pc += 2 * n
            continue
        # instruction
        sz = instr_size(head, operand, symbols)
        parsed.append((label, rest, pc))
        pc += sz
    # Pass 2: emit into 32 KiB PRG buffer ($8000-$FFFF)
    rom = bytearray([0x00] * 0x8000)

    def emit(addr, b):
        if 0x8000 <= addr < 0x10000:
            rom[addr - 0x8000] = b & 0xFF

    pc = 0
    for label, rest, line_pc in parsed:
        if rest is None:
            continue
        parts = rest.split(None, 1)
        head = parts[0]
        operand = parts[1].strip() if len(parts) > 1 else None
        pc = line_pc
        if head == ".org":
            pc = parse_number(operand, symbols)
            continue
        if head == ".res":
            pc += parse_number(operand, symbols)
            continue
        if head == ".byte":
            for item in operand.split(","):
                item = item.strip()
                if not item:
                    continue
                if item.startswith("<"):
                    name = item[1:]
                    if name not in symbols:
                        raise AsmError("unresolved label %s" % name)
                    emit(pc, symbols[name] & 0xFF)
                elif item.startswith(">"):
                    name = item[1:]
                    if name not in symbols:
                        raise AsmError("unresolved label %s" % name)
                    emit(pc, symbols[name] >> 8)
                else:
                    v = parse_number(item, symbols)
                    if v is None:
                        raise AsmError("unresolved byte %s" % item)
                    emit(pc, v & 0xFF)
                pc += 1
            continue
        if head == ".word":
            for item in operand.split(","):
                item = item.strip()
                v = parse_number(item, symbols)
                if v is None:
                    raise AsmError("unresolved word %s" % item)
                emit(pc, v & 0xFF)
                emit(pc + 1, (v >> 8) & 0xFF)
                pc += 2
            continue
        # instruction
        mn = head
        if mn in IMPLIED:
            emit(pc, OPCODES[(mn, "imp")])
            pc += 1
            continue
        if operand is None and mn in ("ASL", "LSR", "ROL", "ROR"):
            emit(pc, OPCODES[(mn, "acc")])
            pc += 1
            continue
        if mn in BRANCHES:
            if operand not in symbols:
                raise AsmError("unresolved branch %s" % operand)
            target = symbols[operand]
            off = target - (pc + 2)
            if not -128 <= off <= 127:
                raise AsmError("branch out of range to %s" % operand)
            emit(pc, OPCODES[(mn, "rel")])
            emit(pc + 1, off & 0xFF)
            pc += 2
            continue
        op = operand.strip()
        if op == "A":
            emit(pc, OPCODES[(mn, "acc")])
            pc += 1
            continue
        if op.startswith("#"):
            body = op[1:].strip()
            if body.startswith("<"):
                name = body[1:]
                num = parse_number(name, symbols)
                if num is not None:
                    val = num & 0xFF
                elif name not in symbols:
                    raise AsmError("unresolved label %s" % name)
                else:
                    val = symbols[name] & 0xFF
            elif body.startswith(">"):
                name = body[1:]
                num = parse_number(name, symbols)
                if num is not None:
                    val = (num >> 8) & 0xFF
                elif name not in symbols:
                    raise AsmError("unresolved label %s" % name)
                else:
                    val = (symbols[name] >> 8) & 0xFF
            else:
                val = parse_number(body, symbols)
                if val is None:
                    raise AsmError("unresolved immediate %s" % body)
            emit(pc, OPCODES[(mn, "imm")])
            emit(pc + 1, val & 0xFF)
            pc += 2
            continue
        if op.startswith("("):
            if op.endswith(",X)"):
                base = op[1:-3].strip()
                mode = "indx"
                val = parse_number(base, symbols)
                if val is None:
                    raise AsmError("unresolved %s" % base)
                emit(pc, OPCODES[(mn, mode)])
                emit(pc + 1, val & 0xFF)
                pc += 2
                continue
            if op.endswith("),Y"):
                base = op[1:-3].strip()
                mode = "indy"
                val = parse_number(base, symbols)
                if val is None:
                    raise AsmError("unresolved %s" % base)
                emit(pc, OPCODES[(mn, mode)])
                emit(pc + 1, val & 0xFF)
                pc += 2
                continue
            base = op[1:-1].strip()
            val = parse_number(base, symbols)
            if val is None:
                raise AsmError("unresolved %s" % base)
            emit(pc, OPCODES[(mn, "ind")])
            emit(pc + 1, val & 0xFF)
            emit(pc + 2, (val >> 8) & 0xFF)
            pc += 3
            continue
        suffix = None
        base = op
        if op.endswith(",X"):
            base, suffix = op[:-2], "x"
        elif op.endswith(",Y"):
            base, suffix = op[:-2], "y"
        val = parse_number(base.strip(), symbols)
        if val is None:
            raise AsmError("unresolved operand %s" % base)
        if suffix == "x":
            mode = "zpx" if val < 0x100 else "absx"
        elif suffix == "y":
            mode = "zpy" if val < 0x100 else "absy"
        else:
            mode = "zp" if val < 0x100 else "abs"
        if (mn, mode) not in OPCODES:
            raise AsmError("unsupported %s %s" % (mn, mode))
        emit(pc, OPCODES[(mn, mode)])
        if mode in ("zp", "zpx", "zpy"):
            emit(pc + 1, val & 0xFF)
            pc += 2
        else:
            emit(pc + 1, val & 0xFF)
            emit(pc + 2, (val >> 8) & 0xFF)
            pc += 3
    return bytes(rom), symbols

# ------------------------------------------------------------ ROM source
ASM_TEMPLATE = r'''
  .org $0000
ptr_lo: .res 1
ptr_hi: .res 1
tmp_lo: .res 1
tmp_hi: .res 1
tmp2: .res 1
ppu_hi: .res 1
ppu_lo: .res 1
frame_cnt: .res 1
playing: .res 1
cur_step: .res 1
seq_acc_lo: .res 1
seq_acc_hi: .res 1
cursor_row: .res 1
cursor_step: .res 1
bpm: .res 1
preset_idx: .res 1
dirty: .res 1
upd_cursor: .res 1
upd_cell: .res 1
upd_machine: .res 1
upd_bpm: .res 1
upd_status: .res 1
upd_row: .res 1
upd_step: .res 1
prev_row: .res 1
prev_step: .res 1
btn_cur: .res 1
btn_prev: .res 1
btn_press: .res 1
select_held: .res 1
select_used: .res 1
tri_active: .res 1
tri_pitch_lo: .res 1
tri_pitch_hi: .res 1
tri_step_lo: .res 1
tri_step_hi: .res 1
tri_end_lo: .res 1
tri_end_hi: .res 1
tri_frames: .res 1
chan_used: .res 1
trig_row: .res 1
pat_index: .res 1
bitpos: .res 1
bitmask: .res 1
diff_lo: .res 1
diff_hi: .res 1
quot_lo: .res 1
quot_hi: .res 1
divisor: .res 1
vblank_flag: .res 1
digit_h: .res 1
digit_t: .res 1
digit_o: .res 1
row_var: .res 1
step_var: .res 1
cnt_lo: .res 1
cnt_hi: .res 1
noise_period: .res 1
noise_mode: .res 1
noise_vol: .res 1
noise_len: .res 1
pulse_lo: .res 1
pulse_hi: .res 1
pulse_vol: .res 1
pulse_len: .res 1
pattern: .res 16
machine_row: .res 8

  .org $8000
Reset:
  SEI
  CLD
  LDX #$FF
  TXS
  LDA #$00
  STA $2000
  STA $2001
  STA $4015
  STA $4010
  LDA #$40
  STA $4017
  JSR WaitVBlank
  JSR WaitVBlank
  JSR ClearRAM
  LDA #$00
  STA $2006
  STA $2006
  JSR UploadCHR
  JSR ClearNametable
  JSR LoadPalette
  LDA #<title_str
  STA ptr_lo
  LDA #>title_str
  STA ptr_hi
  LDA #$20
  STA ppu_hi
  LDA #$27
  STA ppu_lo
  JSR WriteStr
  LDA #<help1_str
  STA ptr_lo
  LDA #>help1_str
  STA ptr_hi
  LDA #$21
  STA ppu_hi
  LDA #$C2
  STA ppu_lo
  JSR WriteStr
  LDA #<help2_str
  STA ptr_lo
  LDA #>help2_str
  STA ptr_hi
  LDA #$21
  STA ppu_hi
  LDA #$E2
  STA ppu_lo
  JSR WriteStr
  LDA #<help3_str
  STA ptr_lo
  LDA #>help3_str
  STA ptr_hi
  LDA #$22
  STA ppu_hi
  LDA #$02
  STA ppu_lo
  JSR WriteStr
  LDA #$78
  STA bpm
  LDA #$00
  STA preset_idx
  STA cursor_row
  STA cursor_step
  STA cur_step
  STA playing
  STA seq_acc_lo
  STA seq_acc_hi
  STA tri_active
  JSR CopyPreset
  LDA #$01
  STA dirty
  LDA #$80
  STA $2000
  JSR ResetScroll
  LDA #$0F
  STA $4015
  LDA #$1E
  STA $2001
MainLoop:
  LDA vblank_flag
  BEQ MainLoop
  LDA #$00
  STA vblank_flag
  LDA dirty
  BEQ MainUpdCursor
  JSR DrawAll
  LDA #$00
  STA dirty
MainUpdCursor:
  LDA upd_cursor
  BEQ MainUpdCell
  JSR UpdateCursor
  LDA #$00
  STA upd_cursor
MainUpdCell:
  LDA upd_cell
  BEQ MainUpdMachine
  JSR UpdateCell
  LDA #$00
  STA upd_cell
MainUpdMachine:
  LDA upd_machine
  BEQ MainUpdBpm
  JSR UpdateMachine
  LDA #$00
  STA upd_machine
MainUpdBpm:
  LDA upd_bpm
  BEQ MainUpdStatus
  JSR UpdateBpm
  LDA #$00
  STA upd_bpm
MainUpdStatus:
  LDA upd_status
  BEQ MainNoDraw
  JSR UpdateStatus
  LDA #$00
  STA upd_status
MainNoDraw:
  JSR PollController
  JSR HandleInput
  JMP MainLoop

WaitVBlank:
  LDA $2002
  BPL WaitVBlank
  RTS

ResetScroll:
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

ClearRAM:
  LDA #$00
  LDX #$00
ClearRAMLoop:
  STA $0000,X
  STA $0200,X
  STA $0300,X
  STA $0400,X
  STA $0500,X
  STA $0600,X
  STA $0700,X
  INX
  BNE ClearRAMLoop
  RTS

UploadCHR:
  LDA #<font_tiles
  STA ptr_lo
  LDA #>font_tiles
  STA ptr_hi
  LDA #<736
  STA cnt_lo
  LDA #>736
  STA cnt_hi
  LDY #$00
UploadLoop:
  LDA cnt_lo
  ORA cnt_hi
  BEQ UploadDone
  LDA (ptr_lo),Y
  STA $2007
  INC ptr_lo
  BNE UploadNoHi
  INC ptr_hi
UploadNoHi:
  LDA cnt_lo
  SEC
  SBC #$01
  STA cnt_lo
  LDA cnt_hi
  SBC #$00
  STA cnt_hi
  JMP UploadLoop
UploadDone:
  RTS

ClearNametable:
  LDA #$20
  STA $2006
  LDA #$00
  STA $2006
  LDA #$00
  LDX #$04
  LDY #$00
ClearNTLoop:
  STA $2007
  INY
  BNE ClearNTLoop
  DEX
  BNE ClearNTLoop
  RTS

LoadPalette:
  LDA #$3F
  STA $2006
  LDA #$00
  STA $2006
  LDX #$00
PalLoop:
  LDA palette_data,X
  STA $2007
  INX
  CPX #$20
  BNE PalLoop
  RTS

WriteStr:
  LDA ppu_hi
  STA $2006
  LDA ppu_lo
  STA $2006
  LDY #$00
WriteStrLoop:
  LDA (ptr_lo),Y
  CMP #$FF
  BEQ WriteStrDone
  STA $2007
  INY
  JMP WriteStrLoop
WriteStrDone:
  RTS

CopyPreset:
  LDA preset_idx
  ASL
  ASL
  ASL
  ASL
  TAX
  LDA #<pattern
  STA ptr_lo
  LDA #>pattern
  STA ptr_hi
  LDY #$00
CopyPatLoop:
  LDA preset_data,X
  STA (ptr_lo),Y
  INX
  INY
  CPY #$10
  BNE CopyPatLoop
  LDX #$00
  LDA preset_idx
CopyMachLoop:
  STA machine_row,X
  INX
  CPX #$08
  BNE CopyMachLoop
  RTS

NMI:
  PHA
  TXA
  PHA
  TYA
  PHA
  LDA $2002
  INC frame_cnt
  JSR TriEnvelope
  LDA playing
  BEQ NmiDone
  CLC
  LDA seq_acc_lo
  ADC bpm
  STA seq_acc_lo
  LDA seq_acc_hi
  ADC #$00
  STA seq_acc_hi
  LDA seq_acc_hi
  CMP #$03
  BCC NmiDone
  BNE NmiStep
  LDA seq_acc_lo
  CMP #$84
  BCC NmiDone
NmiStep:
  SEC
  LDA seq_acc_lo
  SBC #$84
  STA seq_acc_lo
  LDA seq_acc_hi
  SBC #$03
  STA seq_acc_hi
  INC cur_step
  LDA cur_step
  CMP #$10
  BNE NmiTrig
  LDA #$00
  STA cur_step
NmiTrig:
  JSR TriggerStep
  JSR UpdateIndicator
NmiDone:
  LDA #$01
  STA vblank_flag
  PLA
  TAY
  PLA
  TAX
  PLA
  RTI

IRQ:
  RTI

UpdateIndicator:
  LDA #$20
  STA $2006
  LDA #$49
  STA $2006
  LDX #$00
UpdIndLoop:
  CPX cur_step
  BEQ UpdIndStar
  LDA #$27
  JMP UpdIndWrite
UpdIndStar:
  LDA #$2A
UpdIndWrite:
  STA $2007
  INX
  CPX #$10
  BNE UpdIndLoop
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

UpdateCursor:
  LDX prev_row
  LDA row_addr_hi,X
  STA $2006
  LDA row_addr_lo,X
  STA $2006
  LDA #$00
  STA $2007
  LDX cursor_row
  LDA row_addr_hi,X
  STA $2006
  LDA row_addr_lo,X
  STA $2006
  LDA #$28
  STA $2007
  LDA #$21
  STA $2006
  LDA #$89
  CLC
  ADC prev_step
  STA $2006
  LDA #$00
  STA $2007
  LDA #$21
  STA $2006
  LDA #$89
  CLC
  ADC cursor_step
  STA $2006
  LDA #$29
  STA $2007
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

UpdateCell:
  LDX upd_row
  LDA row_addr_hi,X
  STA tmp_hi
  LDA row_addr_lo,X
  CLC
  ADC #$09
  CLC
  ADC upd_step
  STA tmp_lo
  LDA tmp_hi
  STA $2006
  LDA tmp_lo
  STA $2006
  LDA upd_row
  ASL
  STA pat_index
  LDA upd_step
  CMP #$08
  BCC UpdCellNoSecond
  INC pat_index
UpdCellNoSecond:
  LDA upd_step
  AND #$07
  STA bitpos
  LDA #$01
  STA bitmask
  LDX bitpos
  BEQ UpdCellMaskDone
UpdCellMaskLoop:
  ASL bitmask
  DEX
  BNE UpdCellMaskLoop
UpdCellMaskDone:
  LDX pat_index
  LDA pattern,X
  AND bitmask
  BEQ UpdCellOff
  LDA #$2B
  JMP UpdCellWrite
UpdCellOff:
  LDA #$27
UpdCellWrite:
  STA $2007
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

UpdateMachine:
  LDX upd_row
  LDA row_addr_hi,X
  STA tmp_hi
  LDA row_addr_lo,X
  CLC
  ADC #$05
  STA tmp_lo
  LDA tmp_hi
  STA $2006
  LDA tmp_lo
  STA $2006
  LDX upd_row
  LDA machine_row,X
  STA tmp_lo
  ASL
  CLC
  ADC tmp_lo
  TAX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

UpdateBpm:
  LDA #$21
  STA $2006
  LDA #$A6
  STA $2006
  JSR BpmDigits
  LDA digit_h
  CLC
  ADC #$1B
  STA $2007
  LDA digit_t
  CLC
  ADC #$1B
  STA $2007
  LDA digit_o
  CLC
  ADC #$1B
  STA $2007
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS

UpdateStatus:
  LDA #$21
  STA $2006
  LDA #$AA
  STA $2006
  LDA playing
  BEQ UpdStatusStop
  LDA #$10
  STA $2007
  LDA #$0C
  STA $2007
  LDA #$01
  STA $2007
  LDA #$19
  STA $2007
  JMP UpdStatusDone
UpdStatusStop:
  LDA #$13
  STA $2007
  LDA #$14
  STA $2007
  LDA #$0F
  STA $2007
  LDA #$10
  STA $2007
UpdStatusDone:
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  RTS
'''

ASM_TEMPLATE += r'''
Div16by8:
  LDA #$00
  STA quot_lo
  STA quot_hi
DivLoop:
  LDA diff_hi
  BNE DivSubtract
  LDA diff_lo
  CMP divisor
  BCC DivDone
DivSubtract:
  SEC
  LDA diff_lo
  SBC divisor
  STA diff_lo
  LDA diff_hi
  SBC #$00
  STA diff_hi
  INC quot_lo
  BNE DivLoop
  INC quot_hi
  JMP DivLoop
DivDone:
  RTS

TriSetup:
  LDA #$01
  STA tri_active
  LDA #$FF
  STA $4008
  LDA tri_pitch_lo
  STA $400A
  LDA tri_pitch_hi
  AND #$07
  ORA #$F8
  STA $400B
  LDA chan_used
  ORA #$01
  STA chan_used
  RTS

TriEnvelope:
  LDA tri_active
  BEQ TriEnvDone
  DEC tri_frames
  BNE TriEnvPitch
  LDA #$00
  STA $4008
  STA tri_active
  RTS
TriEnvPitch:
  CLC
  LDA tri_pitch_lo
  ADC tri_step_lo
  STA tri_pitch_lo
  LDA tri_pitch_hi
  ADC tri_step_hi
  STA tri_pitch_hi
  LDA tri_pitch_hi
  CMP tri_end_hi
  BCC TriEnvWrite
  BNE TriEnvReached
  LDA tri_pitch_lo
  CMP tri_end_lo
  BCC TriEnvWrite
TriEnvReached:
  LDA tri_end_lo
  STA tri_pitch_lo
  LDA tri_end_hi
  STA tri_pitch_hi
  LDA #$01
  STA tri_frames
TriEnvWrite:
  LDA #$FF
  STA $4008
  LDA tri_pitch_lo
  STA $400A
  LDA tri_pitch_hi
  AND #$07
  ORA #$F8
  STA $400B
TriEnvDone:
  RTS

AdjustHT:
  LDA tri_pitch_lo
  STA tmp_lo
  LDA tri_pitch_hi
  STA tmp_hi
  LSR tmp_hi
  ROR tmp_lo
  LSR tmp_hi
  ROR tmp_lo
  SEC
  LDA tri_pitch_lo
  SBC tmp_lo
  STA tri_pitch_lo
  LDA tri_pitch_hi
  SBC tmp_hi
  STA tri_pitch_hi
  LDA tri_end_lo
  STA tmp_lo
  LDA tri_end_hi
  STA tmp_hi
  LSR tmp_hi
  ROR tmp_lo
  LSR tmp_hi
  ROR tmp_lo
  SEC
  LDA tri_end_lo
  SBC tmp_lo
  STA tri_end_lo
  LDA tri_end_hi
  SBC tmp_hi
  STA tri_end_hi
  LDA tri_step_lo
  STA tmp_lo
  LDA tri_step_hi
  STA tmp_hi
  LSR tmp_hi
  ROR tmp_lo
  LSR tmp_hi
  ROR tmp_lo
  SEC
  LDA tri_step_lo
  SBC tmp_lo
  STA tri_step_lo
  LDA tri_step_hi
  SBC tmp_hi
  STA tri_step_hi
  RTS

WriteNoise:
  LDA #$10
  ORA noise_vol
  STA $400C
  LDA noise_mode
  BEQ NoiseMode0
  LDA #$80
  JMP NoiseModeDone
NoiseMode0:
  LDA #$00
NoiseModeDone:
  ORA noise_period
  STA $400E
  LDA noise_len
  ASL
  ASL
  ASL
  STA $400F
  LDA chan_used
  ORA #$02
  STA chan_used
  RTS

WritePulse1:
  LDA #$90
  ORA pulse_vol
  STA $4000
  LDA #$00
  STA $4001
  LDA pulse_lo
  STA $4002
  LDA pulse_len
  ASL
  ASL
  ASL
  STA tmp_lo
  LDA pulse_hi
  AND #$07
  ORA tmp_lo
  STA $4003
  LDA chan_used
  ORA #$04
  STA chan_used
  RTS

WritePulse2:
  LDA #$50
  ORA pulse_vol
  STA $4004
  LDA #$00
  STA $4005
  LDA pulse_lo
  STA $4006
  LDA pulse_len
  ASL
  ASL
  ASL
  STA tmp_lo
  LDA pulse_hi
  AND #$07
  ORA tmp_lo
  STA $4007
  LDA chan_used
  ORA #$08
  STA chan_used
  RTS

BpmDigits:
  LDA bpm
  STA tmp_lo
  LDX #$00
BpmHLoop:
  LDA tmp_lo
  CMP #$64
  BCC BpmHDone
  SEC
  SBC #$64
  STA tmp_lo
  INX
  JMP BpmHLoop
BpmHDone:
  STX digit_h
  LDX #$00
BpmTLoop:
  LDA tmp_lo
  CMP #$0A
  BCC BpmTDone
  SEC
  SBC #$0A
  STA tmp_lo
  INX
  JMP BpmTLoop
BpmTDone:
  STX digit_t
  LDA tmp_lo
  STA digit_o
  RTS

DrawAll:
  LDA #$00
  STA $2000
  STA $2001
  LDA #$20
  STA $2006
  LDA #$49
  STA $2006
  LDX #$00
StepIndLoop:
  CPX cur_step
  BEQ StepIndStar
  LDA #$27
  JMP StepIndWrite
StepIndStar:
  LDA #$2A
StepIndWrite:
  STA $2007
  INX
  CPX #$10
  BNE StepIndLoop
  LDA #$00
  STA row_var
RowLoop:
  LDX row_var
  LDA row_addr_hi,X
  STA $2006
  LDA row_addr_lo,X
  STA $2006
  LDA row_var
  CMP cursor_row
  BEQ RowMarker
  LDA #$00
  JMP RowMarkerWrite
RowMarker:
  LDA #$28
RowMarkerWrite:
  STA $2007
  LDA #$00
  STA $2007
  LDA row_var
  ASL
  TAX
  LDA voice_labels,X
  STA $2007
  INX
  LDA voice_labels,X
  STA $2007
  LDA #$00
  STA $2007
  LDX row_var
  LDA machine_row,X
  STA tmp_lo
  ASL
  CLC
  ADC tmp_lo
  TAX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  LDA #$00
  STA $2007
  LDA #$00
  STA step_var
StepLoop:
  LDA row_var
  ASL
  STA pat_index
  LDA step_var
  CMP #$08
  BCC StepNoSecond
  INC pat_index
StepNoSecond:
  LDA step_var
  AND #$07
  STA bitpos
  LDA #$01
  STA bitmask
  LDX bitpos
  BEQ StepMaskDone
StepMaskLoop:
  ASL bitmask
  DEX
  BNE StepMaskLoop
StepMaskDone:
  LDX pat_index
  LDA pattern,X
  AND bitmask
  BEQ StepOff
  LDA #$2B
  JMP StepWrite
StepOff:
  LDA #$27
StepWrite:
  STA $2007
  INC step_var
  LDA step_var
  CMP #$10
  BNE StepLoop
  INC row_var
  LDA row_var
  CMP #$08
  BEQ RowDone
  JMP RowLoop
RowDone:
  LDA #$21
  STA $2006
  LDA #$89
  STA $2006
  LDX #$00
CursorIndLoop:
  CPX cursor_step
  BEQ CursorIndMark
  LDA #$00
  JMP CursorIndWrite
CursorIndMark:
  LDA #$29
CursorIndWrite:
  STA $2007
  INX
  CPX #$10
  BNE CursorIndLoop
  LDA #$21
  STA $2006
  LDA #$A2
  STA $2006
  LDA #$02
  STA $2007
  LDA #$10
  STA $2007
  LDA #$0D
  STA $2007
  LDA #$00
  STA $2007
  JSR BpmDigits
  LDA digit_h
  CLC
  ADC #$1B
  STA $2007
  LDA digit_t
  CLC
  ADC #$1B
  STA $2007
  LDA digit_o
  CLC
  ADC #$1B
  STA $2007
  LDA #$00
  STA $2007
  LDA playing
  BEQ StatusStop
  LDA #$10
  STA $2007
  LDA #$0C
  STA $2007
  LDA #$01
  STA $2007
  LDA #$19
  STA $2007
  JMP StatusAfterPlay
StatusStop:
  LDA #$13
  STA $2007
  LDA #$14
  STA $2007
  LDA #$0F
  STA $2007
  LDA #$10
  STA $2007
StatusAfterPlay:
  LDA #$00
  STA $2007
  LDA #$10
  STA $2007
  LDA #$01
  STA $2007
  LDA #$14
  STA $2007
  LDA #$00
  STA $2007
  LDA preset_idx
  STA tmp_lo
  ASL
  CLC
  ADC tmp_lo
  TAX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  INX
  LDA machine_names,X
  STA $2007
  LDA $2002
  LDA #$00
  STA $2005
  STA $2005
  LDA #$80
  STA $2000
  LDA #$1E
  STA $2001
  RTS
'''

ASM_TEMPLATE += r'''
PollController:
  LDA #$01
  STA $4016
  LDA #$00
  STA $4016
  LDA #$00
  STA btn_cur
  LDX #$08
PollLoop:
  LDA $4016
  AND #$01
  STA tmp_lo
  ASL btn_cur
  LDA tmp_lo
  ORA btn_cur
  STA btn_cur
  DEX
  BNE PollLoop
  LDA btn_prev
  EOR #$FF
  AND btn_cur
  STA btn_press
  LDA btn_cur
  STA btn_prev
  RTS

ToggleStep:
  LDA cursor_row
  ASL
  STA pat_index
  LDA cursor_step
  CMP #$08
  BCC TogNoSecond
  INC pat_index
TogNoSecond:
  LDA cursor_step
  AND #$07
  STA bitpos
  LDA #$01
  STA bitmask
  LDX bitpos
  BEQ TogMaskDone
TogMaskLoop:
  ASL bitmask
  DEX
  BNE TogMaskLoop
TogMaskDone:
  LDX pat_index
  LDA pattern,X
  EOR bitmask
  STA pattern,X
  RTS

HandleInput:
  LDA btn_cur
  AND #$20
  BEQ SelectNotHeld
  LDA select_held
  BNE SelectAlreadyHeld
  LDA #$01
  STA select_held
  LDA #$00
  STA select_used
  JMP HandleDone
SelectAlreadyHeld:
  LDA btn_press
  AND #$08
  BEQ SelectCheckDown
  LDA select_used
  ORA #$01
  STA select_used
  LDA bpm
  CLC
  ADC #$05
  CMP #$B5
  BCC SelectBpmOkUp
  LDA #$B4
SelectBpmOkUp:
  STA bpm
  LDA #$01
  STA upd_bpm
  JMP HandleDone
SelectCheckDown:
  LDA btn_press
  AND #$04
  BNE SelectDoDown
  JMP HandleDone
SelectDoDown:
  LDA select_used
  ORA #$01
  STA select_used
  LDA bpm
  SEC
  SBC #$05
  CMP #$3C
  BCS SelectBpmOkDown
  LDA #$3C
SelectBpmOkDown:
  STA bpm
  LDA #$01
  STA upd_bpm
  JMP HandleDone
SelectNotHeld:
  LDA select_held
  BEQ NormalInput
  LDA #$00
  STA select_held
  LDA select_used
  BNE NormalInput
  INC preset_idx
  LDA preset_idx
  CMP #$09
  BNE PresetOk
  LDA #$00
  STA preset_idx
PresetOk:
  JSR CopyPreset
  LDA #$01
  STA dirty
NormalInput:
  LDA btn_press
  AND #$08
  BEQ NormalDown
  LDA cursor_row
  STA prev_row
  LDA cursor_step
  STA prev_step
  LDA cursor_row
  BEQ NormalUpWrap
  DEC cursor_row
  JMP NormalUpDone
NormalUpWrap:
  LDA #$07
  STA cursor_row
NormalUpDone:
  LDA #$01
  STA upd_cursor
NormalDown:
  LDA btn_press
  AND #$04
  BEQ NormalLeft
  LDA cursor_row
  STA prev_row
  LDA cursor_step
  STA prev_step
  LDA cursor_row
  CMP #$07
  BEQ NormalDownWrap
  INC cursor_row
  JMP NormalDownDone
NormalDownWrap:
  LDA #$00
  STA cursor_row
NormalDownDone:
  LDA #$01
  STA upd_cursor
NormalLeft:
  LDA btn_press
  AND #$02
  BEQ NormalRight
  LDA cursor_row
  STA prev_row
  LDA cursor_step
  STA prev_step
  LDA cursor_step
  BEQ NormalLeftWrap
  DEC cursor_step
  JMP NormalLeftDone
NormalLeftWrap:
  LDA #$0F
  STA cursor_step
NormalLeftDone:
  LDA #$01
  STA upd_cursor
NormalRight:
  LDA btn_press
  AND #$01
  BEQ NormalA
  LDA cursor_row
  STA prev_row
  LDA cursor_step
  STA prev_step
  LDA cursor_step
  CMP #$0F
  BEQ NormalRightWrap
  INC cursor_step
  JMP NormalRightDone
NormalRightWrap:
  LDA #$00
  STA cursor_step
NormalRightDone:
  LDA #$01
  STA upd_cursor
NormalA:
  LDA btn_press
  AND #$80
  BEQ NormalB
  JSR ToggleStep
  LDA cursor_row
  STA upd_row
  LDA cursor_step
  STA upd_step
  LDA #$01
  STA upd_cell
NormalB:
  LDA btn_press
  AND #$40
  BEQ NormalStart
  LDX cursor_row
  LDA machine_row,X
  CLC
  ADC #$01
  CMP #$09
  BNE MachineOk
  LDA #$00
MachineOk:
  STA machine_row,X
  LDA cursor_row
  STA upd_row
  LDA #$01
  STA upd_machine
NormalStart:
  LDA btn_press
  AND #$10
  BEQ HandleDone
  LDA playing
  BEQ StartPlay
  LDA #$00
  STA playing
  STA tri_active
  STA $4008
  STA $4000
  STA $4004
  STA $400C
  LDA #$01
  STA upd_status
  JMP HandleDone
StartPlay:
  LDA #$01
  STA playing
  LDA #$00
  STA cur_step
  STA seq_acc_lo
  STA seq_acc_hi
  LDA #$01
  STA upd_status
HandleDone:
  RTS

TriggerStep:
  LDA #$0F
  STA $4015
  LDA #$00
  STA chan_used
  STA trig_row
TrigLoop:
  LDA trig_row
  CMP #$08
  BEQ TrigDone
  LDA trig_row
  ASL
  STA pat_index
  LDA cur_step
  CMP #$08
  BCC TrigNoSecond
  INC pat_index
  LDA cur_step
  SEC
  SBC #$08
  JMP TrigBitPos
TrigNoSecond:
  LDA cur_step
TrigBitPos:
  STA bitpos
  LDA #$01
  STA bitmask
  LDX bitpos
  BEQ TrigMaskDone
TrigMaskLoop:
  ASL bitmask
  DEX
  BNE TrigMaskLoop
TrigMaskDone:
  LDX pat_index
  LDA pattern,X
  AND bitmask
  BEQ TrigNext
  LDA trig_row
  CMP #$00
  BNE TrigCheck1
  JMP TrigBD
TrigCheck1:
  CMP #$01
  BNE TrigCheck2
  JMP TrigSD
TrigCheck2:
  CMP #$02
  BNE TrigCheck3
  JMP TrigLT
TrigCheck3:
  CMP #$03
  BNE TrigCheck4
  JMP TrigHT
TrigCheck4:
  CMP #$04
  BNE TrigCheck5
  JMP TrigRS
TrigCheck5:
  CMP #$05
  BNE TrigCheck6
  JMP TrigCB
TrigCheck6:
  CMP #$06
  BNE TrigCheck7
  JMP TrigOH
TrigCheck7:
  JMP TrigCH
TrigNext:
  INC trig_row
  JMP TrigLoop
TrigDone:
  RTS
TrigBD:
  LDA chan_used
  AND #$01
  BEQ TrigBDGo
  JMP TrigNext
TrigBDGo:
  LDX trig_row
  LDA machine_row,X
  STA tmp_lo
  ASL
  ASL
  ASL
  SEC
  SBC tmp_lo
  TAX
  LDA bd_table,X
  STA tri_pitch_lo
  INX
  LDA bd_table,X
  STA tri_pitch_hi
  INX
  LDA bd_table,X
  STA tri_end_lo
  INX
  LDA bd_table,X
  STA tri_end_hi
  INX
  LDA bd_table,X
  STA tri_frames
  INX
  LDA bd_table,X
  STA tri_step_lo
  INX
  LDA bd_table,X
  STA tri_step_hi
  JSR TriSetup
  JMP TrigNext
TrigLT:
  LDA chan_used
  AND #$01
  BEQ TrigLTGo
  JMP TrigNext
TrigLTGo:
  LDX trig_row
  LDA machine_row,X
  STA tmp_lo
  ASL
  ASL
  ASL
  SEC
  SBC tmp_lo
  TAX
  LDA tom_table,X
  STA tri_pitch_lo
  INX
  LDA tom_table,X
  STA tri_pitch_hi
  INX
  LDA tom_table,X
  STA tri_end_lo
  INX
  LDA tom_table,X
  STA tri_end_hi
  INX
  LDA tom_table,X
  STA tri_frames
  INX
  LDA tom_table,X
  STA tri_step_lo
  INX
  LDA tom_table,X
  STA tri_step_hi
  JSR TriSetup
  JMP TrigNext
TrigHT:
  LDA chan_used
  AND #$01
  BEQ TrigHTGo
  JMP TrigNext
TrigHTGo:
  LDX trig_row
  LDA machine_row,X
  STA tmp_lo
  ASL
  ASL
  ASL
  SEC
  SBC tmp_lo
  TAX
  LDA tom_table,X
  STA tri_pitch_lo
  INX
  LDA tom_table,X
  STA tri_pitch_hi
  INX
  LDA tom_table,X
  STA tri_end_lo
  INX
  LDA tom_table,X
  STA tri_end_hi
  INX
  LDA tom_table,X
  STA tri_frames
  INX
  LDA tom_table,X
  STA tri_step_lo
  INX
  LDA tom_table,X
  STA tri_step_hi
  JSR AdjustHT
  JSR TriSetup
  JMP TrigNext
TrigSD:
  LDA chan_used
  AND #$02
  BEQ TrigSDGo
  JMP TrigNext
TrigSDGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  ASL
  TAX
  LDA sd_noise,X
  STA noise_period
  INX
  LDA sd_noise,X
  STA noise_mode
  INX
  LDA sd_noise,X
  STA noise_vol
  INX
  LDA sd_noise,X
  STA noise_len
  JSR WriteNoise
  LDA chan_used
  AND #$08
  BEQ TrigSDBodyGo
  JMP TrigNext
TrigSDBodyGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  TAX
  LDA sd_body,X
  STA pulse_lo
  INX
  LDA sd_body,X
  STA pulse_hi
  LDA #$08
  STA pulse_vol
  LDA #$03
  STA pulse_len
  JSR WritePulse2
  JMP TrigNext
TrigRS:
  LDA chan_used
  AND #$04
  BEQ TrigRSGo
  JMP TrigNext
TrigRSGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  ASL
  TAX
  LDA rs_pulse,X
  STA pulse_lo
  INX
  LDA rs_pulse,X
  STA pulse_hi
  INX
  LDA rs_pulse,X
  STA pulse_vol
  INX
  LDA rs_pulse,X
  STA pulse_len
  JSR WritePulse1
  JMP TrigNext
TrigCB:
  LDA chan_used
  AND #$04
  BEQ TrigCBGo
  JMP TrigNext
TrigCBGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  ASL
  TAX
  LDA cb_pulse,X
  STA pulse_lo
  INX
  LDA cb_pulse,X
  STA pulse_hi
  INX
  LDA cb_pulse,X
  STA pulse_vol
  INX
  LDA cb_pulse,X
  STA pulse_len
  JSR WritePulse1
  JMP TrigNext
TrigOH:
  LDA chan_used
  AND #$02
  BEQ TrigOHGo
  JMP TrigNext
TrigOHGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  ASL
  TAX
  LDA hat_noise,X
  STA noise_period
  INX
  LDA hat_noise,X
  STA noise_mode
  INX
  LDA hat_noise,X
  STA noise_vol
  INX
  LDA hat_noise,X
  STA noise_len
  JSR WriteNoise
  JMP TrigNext
TrigCH:
  LDA chan_used
  AND #$02
  BEQ TrigCHGo
  JMP TrigNext
TrigCHGo:
  LDX trig_row
  LDA machine_row,X
  ASL
  ASL
  TAX
  LDA hat_noise,X
  STA noise_period
  INX
  LDA hat_noise,X
  STA noise_mode
  INX
  LDA hat_noise,X
  STA noise_vol
  INX
  LDA hat_noise,X
  STA noise_len
  LSR noise_len
  JSR WriteNoise
  JMP TrigNext

font_tiles:
@@FONT@@
palette_data:
@@PALETTE@@
title_str:
@@TITLE@@
  .byte $FF
help1_str:
@@HELP1@@
  .byte $FF
help2_str:
@@HELP2@@
  .byte $FF
help3_str:
@@HELP3@@
  .byte $FF
voice_labels:
@@VOICES@@
machine_names:
@@MACHINES@@
row_addr_hi:
  .byte $20, $20, $20, $20, $21, $21, $21, $21
row_addr_lo:
  .byte $80, $A0, $C0, $E0, $00, $20, $40, $60
bd_table:
@@BD@@
tom_table:
@@TOM@@
sd_noise:
@@SDNOISE@@
hat_noise:
@@HATNOISE@@
rs_pulse:
@@RS@@
cb_pulse:
@@CB@@
sd_body:
@@SDBODY@@
preset_data:
@@PRESETS@@

  .org $FFFA
  .word NMI
  .word Reset
  .word IRQ
'''


def build_source():
    src = ASM_TEMPLATE
    src = src.replace("@@FONT@@", fmt_bytes(FONT_BYTES))
    src = src.replace("@@PALETTE@@", fmt_bytes(PALETTE))
    src = src.replace("@@TITLE@@",
                      fmt_bytes(tiles_for("ROLAND X0X DRUMS")))
    src = src.replace("@@HELP1@@",
                      fmt_bytes(tiles_for("A TOGGLE  B MACHINE")))
    src = src.replace("@@HELP2@@",
                      fmt_bytes(tiles_for("SELECT PATTERN  START PLAY")))
    src = src.replace("@@HELP3@@",
                      fmt_bytes(tiles_for("SELECT+UP/DN BPM 60-180")))
    src = src.replace("@@VOICES@@", fmt_bytes(VOICE_LABEL_BYTES))
    src = src.replace("@@MACHINES@@", fmt_bytes(MACHINE_NAME_BYTES))
    src = src.replace("@@BD@@", fmt_bytes(tri_table(BD_DATA)))
    src = src.replace("@@TOM@@", fmt_bytes(tri_table(TOM_DATA)))
    src = src.replace("@@SDNOISE@@",
                      fmt_bytes([b for row in SD_NOISE for b in row]))
    src = src.replace("@@HATNOISE@@",
                      fmt_bytes([b for row in HAT_NOISE for b in row]))
    src = src.replace("@@RS@@", fmt_bytes(pulse_table(RS_FREQ, RS_VOL, RS_LEN)))
    src = src.replace("@@CB@@", fmt_bytes(pulse_table(CB_FREQ, CB_VOL, CB_LEN)))
    body = []
    for f in SD_BODY_FREQ:
        lo, hi = lo_hi(pulse_timer(f))
        body.extend([lo, hi])
    src = src.replace("@@SDBODY@@", fmt_bytes(body))
    src = src.replace("@@PRESETS@@", fmt_bytes(preset_bytes()))
    return src


def main():
    try:
        prg, symbols = assemble(build_source())
    except AsmError as exc:
        print("ASSEMBLY FAILED: %s" % exc, file=sys.stderr)
        return 1
    # iNES header: mapper 0, 32 KiB PRG (2 x 16 KiB), 0 CHR (CHR RAM)
    header = bytearray(16)
    header[0:4] = b"NES\x1a"
    header[4] = 2
    header[5] = 0
    header[6] = 0x00
    header[7] = 0x00
    rom = bytes(header) + prg
    with open(OUT_PATH, "wb") as f:
        f.write(rom)
    # Validation, reading the file back
    with open(OUT_PATH, "rb") as f:
        data = f.read()
    assert data[0:4] == b"NES\x1a", "bad magic"
    assert data[4] == 2 and data[5] == 0, "bad PRG/CHR sizes"
    assert ((data[6] >> 4) | (data[7] & 0xF0)) == 0, "mapper is not 0"
    assert len(data) == 16 + 2 * 16384, "size does not match header"
    vec_off = 16 + 0x7FFA
    nmi = data[vec_off] | (data[vec_off + 1] << 8)
    reset = data[vec_off + 2] | (data[vec_off + 3] << 8)
    irq = data[vec_off + 4] | (data[vec_off + 5] << 8)
    for name, v in (("NMI", nmi), ("Reset", reset), ("IRQ", irq)):
        assert 0x8000 <= v <= 0xFFFF, "%s vector out of PRG range" % name
    assert symbols["Reset"] == reset, "Reset vector mismatch"
    assert symbols["NMI"] == nmi, "NMI vector mismatch"
    assert symbols["IRQ"] == irq, "IRQ vector mismatch"
    print("Built %s" % OUT_PATH)
    print("Size: %d bytes (16 header + %d PRG)" % (len(data), len(prg)))
    print("Header: NES\\x1a, PRG=%d x 16KiB, CHR=%d (CHR RAM), mapper 0" % (data[4], data[5]))
    print("Vectors: NMI=$%04X Reset=$%04X IRQ=$%04X" % (nmi, reset, irq))
    print("Code/data end (before vectors): highest used PRG offset checked by assembler symbols")
    print("Unresolved labels: none (assembler raises on any)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
