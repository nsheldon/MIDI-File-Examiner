#!/usr/bin/env python3
"""
MIDI File Examiner
A comprehensive MIDI file analysis tool that extracts and displays
metadata, timing information, and message details from MIDI files.
"""

import sys
import os
import io
import argparse
from collections import defaultdict

try:
    import mido
except ImportError:
    print("Error: mido library is required. Install it with: pip install mido")
    sys.exit(1)

__version__ = "1.1.2"

# ── Terminal colour support ───────────────────────────────────────────────────

# True-color RGB, nearest xterm-256 index, basic-16 bg/fg codes.
# Colours match the GUI sidebar: Roland orange (GS), Yamaha purple (XG),
# forest green / lighter forest green (GM / GM2).
_STANDARD_ANSI = {
    #           bg_rgb               fg_rgb       bg_256  fg_256  bg_16  fg_16
    "GM":  ((0x22, 0x8B, 0x22), (  0,   0,   0),     28,      0,    42,    30),
    "GM2": ((0x3D, 0xAA, 0x3D), (  0,   0,   0),     71,      0,    42,    30),
    "GS":  ((0xF2, 0x65, 0x22), (  0,   0,   0),    202,      0,    43,    30),
    "XG":  ((0x49, 0x27, 0x86), (255, 255, 255),     54,     15,    45,    37),
}

_color_support_cache = None


def _detect_color_support():
    """Return 'truecolor', '256', 'basic', or 'none' for stdout."""
    global _color_support_cache
    if _color_support_cache is not None:
        return _color_support_cache
    if not sys.stdout.isatty():
        _color_support_cache = 'none'
        return _color_support_cache
    colorterm = os.environ.get('COLORTERM', '').lower()
    if colorterm in ('truecolor', '24bit'):
        _color_support_cache = 'truecolor'
        return _color_support_cache
    term_program = os.environ.get('TERM_PROGRAM', '')
    if term_program in ('iTerm.app', 'Hyper', 'WezTerm'):
        _color_support_cache = 'truecolor'
        return _color_support_cache
    term = os.environ.get('TERM', '')
    if '256color' in term or term_program in ('Apple_Terminal', 'vscode'):
        _color_support_cache = '256'
        return _color_support_cache
    if 'xterm' in term or 'color' in term or term in ('screen', 'tmux'):
        _color_support_cache = '256'
        return _color_support_cache
    _color_support_cache = 'basic'
    return _color_support_cache


def _colorize_standard(text, standard):
    """Wrap text in ANSI escape codes matching the standard's brand colour.

    Falls back gracefully through true-color → 256-colour → basic-16 → plain
    depending on what the terminal supports.
    """
    support = _detect_color_support()
    if support == 'none' or standard not in _STANDARD_ANSI:
        return text
    bg_rgb, fg_rgb, bg_256, fg_256, bg_basic, fg_basic = _STANDARD_ANSI[standard]
    reset = '\033[0m'
    if support == 'truecolor':
        bg = f'\033[48;2;{bg_rgb[0]};{bg_rgb[1]};{bg_rgb[2]}m'
        fg = f'\033[38;2;{fg_rgb[0]};{fg_rgb[1]};{fg_rgb[2]}m'
    elif support == '256':
        bg = f'\033[48;5;{bg_256}m'
        fg = f'\033[38;5;{fg_256}m'
    else:
        bg = f'\033[{bg_basic}m'
        fg = f'\033[{fg_basic}m'
    return f'{bg}{fg}{text}{reset}'


# ── Note names and CC names (used by statistics) ─────────────────────────────

_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def _midi_note_name(n):
    """Convert a MIDI note number to a human-readable name (e.g. 60 → 'C4')."""
    return f"{_NOTE_NAMES[n % 12]}{(n // 12) - 1}"


_CC_NAMES = {
    0: "Bank MSB",    1: "Modulation",   2: "Breath",
    4: "Foot Ctrl",   5: "Port. Time",   6: "Data Entry",
    7: "Volume",      8: "Balance",      10: "Pan",
    11: "Expression", 12: "Effect 1",    13: "Effect 2",
    32: "Bank LSB",   38: "Data LSB",
    64: "Sustain",    65: "Portamento",  66: "Sostenuto",
    67: "Soft Pedal", 68: "Legato",
    71: "Resonance",  72: "Release",     73: "Attack",
    74: "Brightness", 84: "Port. Ctrl",
    91: "Reverb",     92: "Tremolo",     93: "Chorus",
    94: "Celeste",    95: "Phaser",
    96: "Data Inc",   97: "Data Dec",
    98: "NRPN LSB",   99: "NRPN MSB",   100: "RPN LSB",  101: "RPN MSB",
    120: "All Snd Off", 121: "Reset Ctrl", 123: "All Notes Off",
}


# ── Directory scanning ────────────────────────────────────────────────────────

def _scan_directory(root, max_depth=6):
    """Return (files, warnings) for all MIDI files in *root* up to *max_depth* levels deep.

    Depth is measured from *root* itself (depth 0).  Files directly inside
    *root* are at depth 0; files one folder down are at depth 1, and so on.
    Files found at depth > *max_depth* are not included, and a warning is
    generated if any such files exist.
    """
    included = []
    excluded_count = 0

    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == '.' else len(rel.split(os.sep))

        midi_here = [f for f in filenames if f.lower().endswith(('.mid', '.midi'))]

        # Sort subdirectory names in-place (controls os.walk traversal order)
        # and MIDI filenames case-insensitively so the sidebar hierarchy is
        # presented in alphabetical order regardless of letter case.
        dirnames.sort(key=str.lower)

        if depth <= max_depth:
            for name in sorted(midi_here, key=str.lower):
                included.append(os.path.join(dirpath, name))
        else:
            excluded_count += len(midi_here)
            # Prune deeper descent — no need to go further once we're past the limit.
            dirnames.clear()

    warnings = []
    if excluded_count:
        warnings.append(
            f"Directory scan limited to {max_depth} level(s) deep; "
            f"{excluded_count} MIDI file(s) in deeper subdirectories were not included."
        )

    return included, warnings


def collect_midi_files(path, max_depth=6):
    """Collect MIDI file paths from *path* (a file or directory).

    If *path* is a MIDI file, returns ([path], []).
    If *path* is a directory, scans recursively up to *max_depth* levels.
    Returns (files, warnings).
    """
    path = os.path.abspath(path)
    if os.path.isfile(path):
        if path.lower().endswith(('.mid', '.midi')):
            return [path], []
        return [], []
    if os.path.isdir(path):
        return _scan_directory(path, max_depth)
    return [], []


# Import the database module for patch lookups
import midi_patches_db


def get_instrument_name(program, channel=None, bank_msb=0, bank_lsb=0, standard=None):
    """Get instrument name from program number using database lookup.

    For channel 10 (percussion), returns drum kit name instead.
    Channel is 1-indexed (1-16) to match MIDI convention.

    Args:
        program: Program Change, 0-127
        channel: MIDI channel (1-16)
        bank_msb: Bank Select MSB, default 0
        bank_lsb: Bank Select LSB, default 0
        standard: Optional MIDI standard ('GM', 'GM2', 'GS', 'XG')

    Returns:
        Instrument or drum kit name
    """
    return midi_patches_db.get_instrument_name(
        program, channel, bank_msb, bank_lsb, standard
    )


def get_drum_kit_name(program, bank_msb=0, bank_lsb=0, standard=None):
    """Get drum kit name from program number using database lookup.

    Args:
        program: Program Change (drum kit number), 0-127
        bank_msb: Bank Select MSB, default 0
        bank_lsb: Bank Select LSB, default 0
        standard: Optional MIDI standard

    Returns:
        Drum kit name
    """
    return midi_patches_db.get_drum_kit_name(program, bank_msb, bank_lsb, standard)


def identify_sysex(data):
    """Identify common SysEx messages (GM, GM2, GS, XG)."""
    if len(data) < 4:
        return None, "Unknown SysEx"

    # Convert to list if needed
    data = list(data)

    # GM System On: F0 7E 7F 09 01 F7
    if data[:5] == [0x7E, 0x7F, 0x09, 0x01]:
        return "GM", "GM System On"

    # GM System Off: F0 7E 7F 09 00 F7
    if data[:5] == [0x7E, 0x7F, 0x09, 0x00]:
        return "GM", "GM System Off"

    # GM2 System On: F0 7E 7F 09 03 F7
    if data[:5] == [0x7E, 0x7F, 0x09, 0x03]:
        return "GM2", "GM2 System On"

    # Roland GS Reset: F0 41 10 42 12 40 00 7F 00 41 F7
    if len(data) >= 5 and data[0] == 0x41 and data[2] == 0x42:
        if len(data) >= 8 and data[4] == 0x40 and data[5] == 0x00 and data[6] == 0x7F:
            return "GS", "GS Reset"
        return "GS", "GS SysEx"

    # Yamaha XG System On: F0 43 10 4C 00 00 7E 00 F7
    if len(data) >= 4 and data[0] == 0x43 and data[2] == 0x4C:
        if len(data) >= 7 and data[3] == 0x00 and data[4] == 0x00 and data[5] == 0x7E:
            return "XG", "XG System On"
        return "XG", "XG SysEx"

    # Check manufacturer IDs
    if data[0] == 0x41:
        return "Roland", "Roland SysEx"
    if data[0] == 0x43:
        return "Yamaha", "Yamaha SysEx"
    if data[0] == 0x42:
        return "Korg", "Korg SysEx"
    if data[0] == 0x7E:
        return "Universal", "Universal Non-Real Time"
    if data[0] == 0x7F:
        return "Universal", "Universal Real Time"

    return None, "Unknown SysEx"


def format_smpte(hours, minutes, seconds, frames, subframes):
    """Format SMPTE offset."""
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}.{subframes:02d}"


def ticks_to_time(ticks, tempo, ppqn):
    """Convert ticks to seconds."""
    if ppqn == 0:
        return 0
    return (ticks / ppqn) * (tempo / 1000000)


def ticks_to_measure_beat(absolute_ticks, ppqn, time_signatures):
    """Convert absolute ticks to measure:beat.subdivision format.

    Args:
        absolute_ticks: Absolute tick position from start of file
        ppqn: Pulses (ticks) per quarter note
        time_signatures: List of time signature events with 'abs_time' field,
                        sorted by abs_time. Each has numerator, denominator.

    Returns:
        Tuple of (measure, beat, subdivision) where measure and beat are 1-indexed
    """
    if not time_signatures:
        # Default to 4/4 if no time signature
        time_signatures = [{"abs_time": 0, "numerator": 4, "denominator": 4}]

    # Find applicable time signature regions and calculate measure/beat
    current_tick = 0
    current_measure = 1
    ts_idx = 0

    while ts_idx < len(time_signatures):
        ts = time_signatures[ts_idx]
        next_ts_tick = (time_signatures[ts_idx + 1]["abs_time"]
                       if ts_idx + 1 < len(time_signatures) else float('inf'))

        # Ticks per beat for this time signature
        # denominator 4 = quarter note = ppqn ticks
        # denominator 8 = eighth note = ppqn/2 ticks
        # denominator 2 = half note = ppqn*2 ticks
        ticks_per_beat = ppqn * 4 // ts["denominator"]
        ticks_per_measure = ticks_per_beat * ts["numerator"]

        # How many ticks are in this time signature region?
        region_end = min(next_ts_tick, absolute_ticks)
        ticks_in_region = region_end - current_tick

        if ticks_in_region <= 0:
            ts_idx += 1
            continue

        if absolute_ticks <= next_ts_tick:
            # Target is in this region
            ticks_from_region_start = absolute_ticks - current_tick
            measures_in_region = ticks_from_region_start // ticks_per_measure
            remaining_ticks = ticks_from_region_start % ticks_per_measure

            measure = current_measure + measures_in_region
            beat = remaining_ticks // ticks_per_beat + 1
            subdivision = remaining_ticks % ticks_per_beat

            return (int(measure), int(beat), int(subdivision))
        else:
            # Move past this region
            measures_in_region = ticks_in_region // ticks_per_measure
            current_measure += measures_in_region
            current_tick = next_ts_tick
            ts_idx += 1

    # Shouldn't reach here, but fallback
    return (1, 1, 0)


def format_position(absolute_ticks, ppqn, time_signatures):
    """Format tick position as 'measure:beat.sub (tick N)'.

    Args:
        absolute_ticks: Absolute tick position
        ppqn: Pulses per quarter note
        time_signatures: List of time signature events with abs_time

    Returns:
        Formatted string like "measure 5, beat 2 (tick 1920)"
    """
    measure, beat, subdivision = ticks_to_measure_beat(absolute_ticks, ppqn, time_signatures)
    if subdivision > 0:
        return f"measure {measure}, beat {beat}.{subdivision} (tick {absolute_ticks})"
    else:
        return f"measure {measure}, beat {beat} (tick {absolute_ticks})"


def determine_minimum_xg_level(results):
    """Determine the minimum XG level required to play an XG MIDI file.

    Examines all program changes and their bank select values to determine
    which XG level is required. Uses the XG voice database for known entries
    and heuristics (bank LSB >= 64 implies Level 2+) for unlisted banks.

    XG Levels:
        1 = Basic XG (MU50, MU80, MU90)
        2 = XG Level 2 / MU100 Native (MU100, MU100R, SW1000XG)
        3 = XG Level 3 / MU128 (MU128 only)

    Args:
        results: The analysis results dict (must have detected_standard == "XG")

    Returns:
        Dict with keys: minimum_xg_level, minimum_xg_device, minimum_xg_reason
    """
    conn = midi_patches_db.get_connection()
    cursor = conn.cursor()

    XG_LEVEL_DEVICES = {
        1: "XG Level 1 (MU50/MU80/MU90)",
        2: "XG Level 2 (MU100)",
        3: "XG Level 3 (MU128)",
    }
    max_level = 1
    level_reasons = {2: set(), 3: set()}

    for pc in results["program_changes"]:
        msb = pc["bank_msb"]
        lsb = pc["bank_lsb"]
        program = pc["program"]
        is_percussion = pc["is_percussion"]

        if is_percussion:
            # Look up drum kit level
            cursor.execute("""
                SELECT minimum_level, name FROM percussion_sets
                WHERE standard = 'XG' AND bank_msb = ? AND bank_lsb = ? AND program = ?
            """, (msb, lsb, program))
            row = cursor.fetchone()
            if row and row[0] is not None:
                lvl, name = row
                if lvl > max_level:
                    max_level = lvl
                if lvl >= 2:
                    level_reasons[lvl].add(name or f"Drum Kit {program}")
            elif msb in (126, 127):
                # Unknown SFX/drum kit in XG banks — at least Level 1 XG
                pass
        else:
            # Model Exclusive bank (MSB=48) — always Level 2+
            if msb == 48:
                if max_level < 2:
                    max_level = 2
                name = pc.get("program_name") or f"Bank {msb}:{lsb} Pgm {program+1}"
                level_reasons[2].add(name)
                continue

            # "Other Waves" and "Other Instrument" banks (LSB 64-127) — Level 2+
            if msb == 0 and lsb >= 64:
                if max_level < 2:
                    max_level = 2
                # Check database for specific Level 3 entries
                cursor.execute("""
                    SELECT minimum_level, name FROM patches
                    WHERE standard = 'XG' AND bank_msb = ? AND bank_lsb = ? AND program = ?
                """, (msb, lsb, program))
                row = cursor.fetchone()
                if row and row[0] is not None:
                    lvl, name = row
                    if lvl > max_level:
                        max_level = lvl
                    if lvl >= 2:
                        level_reasons[lvl].add(name or f"Bank {msb}:{lsb} Pgm {program+1}")
                else:
                    # Unlisted voice in Other Waves bank — Level 2 by bank heuristic
                    level_reasons[2].add(f"Bank {msb}:{lsb} Pgm {program+1}")
                continue

            # Standard XG banks (MSB=0, LSB=0-63): look up in database
            cursor.execute("""
                SELECT minimum_level, name FROM patches
                WHERE standard = 'XG' AND bank_msb = ? AND bank_lsb = ? AND program = ?
            """, (msb, lsb, program))
            row = cursor.fetchone()
            if row and row[0] is not None:
                lvl, name = row
                if lvl > max_level:
                    max_level = lvl
                if lvl >= 2:
                    level_reasons[lvl].add(name or f"Bank {msb}:{lsb} Pgm {program+1}")

    conn.close()

    # Build reason string
    reason = ""
    if max_level >= 2:
        culprit_level = max_level
        culprit_patches = level_reasons.get(culprit_level, set())
        if not culprit_patches:
            # May have Level 2 patches but no Level 3; show Level 2 reasons
            culprit_patches = level_reasons.get(2, set())
        if culprit_patches:
            patch_list = ", ".join(sorted(culprit_patches)[:3])
            if len(culprit_patches) > 3:
                patch_list += f" (+{len(culprit_patches) - 3} more)"
            level_name = "Level 2" if culprit_level == 2 else "Level 3"
            reason = f"uses {level_name}-exclusive voice(s): {patch_list}"

    return {
        "minimum_xg_level": max_level,
        "minimum_xg_device": XG_LEVEL_DEVICES.get(max_level, f"XG Level {max_level}"),
        "minimum_xg_reason": reason,
    }


def determine_minimum_sc_version(results):
    """Determine the minimum Sound Canvas version required to play a GS MIDI file.

    Examines all program changes and their bank select values to find which
    Sound Canvas generation first introduced each patch used in the file.

    Args:
        results: The analysis results dict (must have detected_standard == "GS")

    Returns:
        Dict with keys: minimum_sc_version, minimum_sc_generation,
        uses_cm64_pcm, uses_cm64_la
    """
    conn = midi_patches_db.get_connection()
    cursor = conn.cursor()

    SC_GENERATIONS = {1: "SC-55", 2: "SC-88", 3: "SC-88Pro", 4: "SC-8850"}
    max_generation = 1  # Default to SC-55 (generation 1)
    uses_cm64_pcm = False
    uses_cm64_la = False
    # Track patches that require each generation (gen -> set of name strings)
    generation_reasons = {2: set(), 3: set(), 4: set()}

    for pc in results["program_changes"]:
        msb = pc["bank_msb"]
        program = pc["program"]
        is_percussion = pc["is_percussion"]

        # Check for CM-64 patches
        if msb == 126:
            uses_cm64_pcm = True
            continue
        if msb == 127:
            uses_cm64_la = True
            continue

        if is_percussion:
            # Find the minimum bank_lsb that has this drum kit, plus its name
            cursor.execute("""
                SELECT MIN(bank_lsb), name FROM percussion_sets
                WHERE standard = 'GS' AND bank_msb = 0 AND program = ?
            """, (program,))
        else:
            # Find the minimum bank_lsb that has this (msb, program) combo, plus its name
            cursor.execute("""
                SELECT MIN(bank_lsb), name FROM patches
                WHERE standard = 'GS' AND bank_msb = ? AND program = ?
            """, (msb, program))

        row = cursor.fetchone()
        if row and row[0] is not None:
            min_lsb = row[0]
            if min_lsb > max_generation:
                max_generation = min_lsb
            if min_lsb >= 2:
                patch_name = row[1] if row[1] else pc.get("program_name", f"Program {program}")
                if min_lsb in generation_reasons:
                    generation_reasons[min_lsb].add(patch_name)

    conn.close()

    # Build reason string: list the patches that require the minimum version
    reason = ""
    if max_generation >= 2:
        # Collect patches that require exactly the minimum generation (the tightest constraint)
        culprit_patches = generation_reasons.get(max_generation, set())
        if culprit_patches:
            patch_list = ", ".join(sorted(culprit_patches)[:3])
            if len(culprit_patches) > 3:
                patch_list += f" (+{len(culprit_patches) - 3} more)"
            reason = f"uses {SC_GENERATIONS[max_generation]}-exclusive patch(es): {patch_list}"

    return {
        "minimum_sc_version": SC_GENERATIONS.get(max_generation, f"Unknown ({max_generation})"),
        "minimum_sc_generation": max_generation,
        "minimum_sc_reason": reason,
        "uses_cm64_pcm": uses_cm64_pcm,
        "uses_cm64_la": uses_cm64_la,
    }


_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB — refuse files larger than this


def _decoded_has_japanese(s):
    """Return True if *s* contains characters from definitively Japanese Unicode blocks.

    Checks for hiragana, full-width katakana, and CJK ideographs.  Half-width
    katakana (U+FF61–U+FF9F) is intentionally excluded: those code points
    overlap with Latin-1 special characters (e.g. U+00A9 © decodes as U+FF69 ｩ
    in CP932), so treating them as proof of Japanese encoding causes false
    positives on Western strings that use Latin-1 symbols.
    """
    for ch in s:
        cp = ord(ch)
        if (0x3040 <= cp <= 0x30FF or   # Hiragana + full-width Katakana
                0x31F0 <= cp <= 0x31FF or   # Katakana Phonetic Extensions
                0x3400 <= cp <= 0x4DBF or   # CJK Extension A
                0x4E00 <= cp <= 0x9FFF or   # CJK Unified Ideographs
                0xF900 <= cp <= 0xFAFF or   # CJK Compatibility Ideographs
                0xFF01 <= cp <= 0xFF60 or   # Full-width Latin / punctuation
                0xFFE0 <= cp <= 0xFFE6):    # Full-width currency / signs
            return True
    return False


# Control characters that are safe to keep in displayed text (tab, LF, CR).
_SAFE_CTRL = {0x09, 0x0A, 0x0D}


def _sanitize_midi_text(s):
    """Strip dangerous control characters from a decoded MIDI text string.

    Keeps printable characters, space, tab (0x09), LF (0x0A), and CR (0x0D).
    Removes all other C0 controls (0x00–0x1F), DEL (0x7F), and ESC (0x1B)
    which could be used to inject terminal escape sequences into CLI output.
    """
    return ''.join(
        ch for ch in s
        if ord(ch) >= 0x20 or ord(ch) in _SAFE_CTRL
    )


def decode_midi_text(text):
    """Decode a MIDI meta-message text string to properly-encoded Unicode.

    mido decodes all meta-message text as Latin-1.  Re-encode to the original
    bytes, then try encodings in order: pure ASCII (if no high bytes), UTF-8,
    CP932 (Windows Shift-JIS, common in Japanese MIDI files), EUC-JP.
    For Japanese encodings, the decoded result must contain at least one
    character from a definitively Japanese Unicode block; otherwise the bytes
    are treated as Latin-1 (e.g. © is 0xA9 in Latin-1 but decodes to the
    half-width katakana ｩ in CP932 — a false positive).
    Falls back to the original Latin-1 string if nothing else works.
    Control characters that could be used for terminal injection are stripped
    from the result.
    """
    try:
        raw = text.encode('latin-1')
    except (UnicodeEncodeError, AttributeError):
        return text  # already properly decoded or not a string

    # Pure ASCII — no re-encoding needed
    if all(b < 0x80 for b in raw):
        return _sanitize_midi_text(text)

    for encoding in ('utf-8', 'cp932', 'euc-jp'):
        try:
            decoded = raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
        # For Japanese encodings, require at least one definitively Japanese
        # character so that Latin-1 strings with high bytes (©, ®, °, etc.)
        # are not misidentified as Japanese text.
        if encoding in ('cp932', 'euc-jp') and not _decoded_has_japanese(decoded):
            continue
        return _sanitize_midi_text(decoded)

    # Lenient retry: tolerate truncated multibyte sequences (e.g. an incomplete
    # Shift-JIS lead byte at the end of a fixed-width track-name field).
    # Only Japanese encodings are retried leniently; UTF-8 is not included
    # because errors='ignore' would silently drop valid Latin-1 high bytes
    # (e.g. 0xA9 © → empty) before the Latin-1 fallback is reached.
    for encoding in ('cp932', 'euc-jp'):
        try:
            decoded = raw.decode(encoding, errors='ignore')
            if decoded.strip() and _decoded_has_japanese(decoded):
                return _sanitize_midi_text(decoded)
        except LookupError:
            continue

    return _sanitize_midi_text(text)  # fall back to Latin-1 (original mido behaviour)


def _validate_midi_input(filepath):
    """Raise IOError if *filepath* fails basic safety checks.

    Checks performed:
    - File size must not exceed _MAX_FILE_SIZE (5 MB).
    - File must begin with the MIDI header magic bytes 'MThd'.

    Raises IOError with a descriptive message on failure.
    """
    try:
        size = os.path.getsize(filepath)
    except OSError as e:
        raise IOError(f"Cannot read file: {e}") from e

    if size > _MAX_FILE_SIZE:
        mb = size / (1024 * 1024)
        raise IOError(
            f"File is too large to analyze ({mb:.1f} MB). "
            f"Maximum supported size is {_MAX_FILE_SIZE // (1024 * 1024)} MB."
        )

    try:
        with open(filepath, 'rb') as f:
            magic = f.read(4)
    except OSError as e:
        raise IOError(f"Cannot read file: {e}") from e

    if magic != b'MThd':
        raise IOError(
            "File does not appear to be a valid MIDI file "
            "(missing 'MThd' header)."
        )


def _trim_track_garbage(filepath):
    """Return a BytesIO of the MIDI file with track-chunk anomalies fixed.

    Handles two known corruption patterns:

    1. Trailing bytes after EOT (e.g. 7th Guest): bytes beyond the mandatory
       FF 2F 00 End of Track marker are stripped and the chunk length is
       patched.

    2. Truncated track chunks (e.g. Doom E3M5): if a track's declared length
       extends past the end of the file, the available bytes are searched for
       an EOT.  If one is found it is used as the track's end.  If not, the
       track (and all subsequent tracks) is dropped and the MThd track-count
       field is patched down accordingly.

    Returns None if the file does not need patching or cannot be read.
    """
    _EOT = b'\xff\x2f\x00'
    try:
        with open(filepath, 'rb') as f:
            data = bytearray(f.read())
    except OSError:
        return None

    # Locate and validate the MIDI header
    if data[:4] != b'MThd' or len(data) < 14:
        return None
    hdr_len = int.from_bytes(data[4:8], 'big')
    pos = 8 + hdr_len
    trimmed = False
    tracks_seen = 0  # count of tracks fully (or usefully partially) parsed

    while pos + 8 <= len(data):
        if data[pos:pos+4] != b'MTrk':
            break
        declared   = int.from_bytes(data[pos+4:pos+8], 'big')
        track_start = pos + 8
        track_end   = track_start + declared

        if track_end > len(data):
            # --- Truncated track: fewer bytes in the file than declared ---
            available = len(data) - track_start
            chunk = bytes(data[track_start:track_start + available])
            eot_idx = chunk.rfind(_EOT)
            if eot_idx != -1:
                # Usable partial track: trim at EOT
                proper_end = eot_idx + len(_EOT)
                new_declared = proper_end
                data[pos+4:pos+8] = new_declared.to_bytes(4, 'big')
                data = data[:track_start + new_declared]
                tracks_seen += 1
            else:
                # No EOT anywhere in the available data — drop this track
                # and everything after it.
                data = data[:pos]
            # Either way, patch the MThd track count and stop processing.
            data[10:12] = tracks_seen.to_bytes(2, 'big')
            trimmed = True
            break

        # --- Full track available: look for trailing garbage after EOT ---
        chunk = data[track_start:track_end]
        eot_idx = chunk.rfind(_EOT)
        if eot_idx != -1:
            proper_end = eot_idx + len(_EOT)
            if proper_end < len(chunk):
                # Trailing bytes present — trim the chunk
                new_declared = proper_end
                data[pos+4:pos+8] = new_declared.to_bytes(4, 'big')
                data = (data[:track_start + new_declared]
                        + data[track_end:])
                track_end = track_start + new_declared
                trimmed = True

        tracks_seen += 1
        pos = track_end

    return io.BytesIO(bytes(data)) if trimmed else None


def _compute_length(mid):
    """Return the MIDI file length in seconds, capping each delta time at the
    MIDI spec maximum VLQ value (0x0FFFFFFF = 268,435,455 ticks) so that a
    single corrupt delta cannot inflate the reported song duration.

    Tracks that contain any oversized delta are excluded from the end-tick
    calculation; only clean tracks determine the song length.  If every track
    has at least one oversized delta the capped values are used as a last
    resort.

    Also returns a bool indicating whether any delta times were capped.
    """
    MAX_DELTA = 0x0FFFFFFF  # MIDI spec maximum variable-length quantity

    ppqn = mid.ticks_per_beat
    if ppqn <= 0:
        # SMPTE timing — delegate entirely to mido.
        return mid.length, False

    any_capped = False

    # First pass: collect per-track end ticks, flagging tracks with bad deltas.
    track_end_ticks  = []   # (end_tick, has_corrupt_delta) per track
    for track in mid.tracks:
        abs_tick     = 0
        track_bad    = False
        for msg in track:
            if msg.time > MAX_DELTA:
                abs_tick  += MAX_DELTA
                track_bad  = True
                any_capped = True
            else:
                abs_tick  += msg.time
        track_end_ticks.append((abs_tick, track_bad))

    # Prefer clean tracks when determining song length.
    clean_ends = [t for t, bad in track_end_ticks if not bad]
    end_tick   = max(clean_ends) if clean_ends else max(t for t, _ in track_end_ticks)

    # Collect tempo changes using only clean-track positions where possible.
    # We still scan all tracks so we don't miss a tempo event, but cap deltas
    # on corrupt tracks so their positions are at least bounded.
    tempo_map = []   # list of (abs_tick, tempo_us)
    for track in mid.tracks:
        abs_tick = 0
        for msg in track:
            delta     = min(msg.time, MAX_DELTA)
            abs_tick += delta
            if msg.type == 'set_tempo':
                tempo_map.append((abs_tick, msg.tempo))
    tempo_map.sort()

    # Convert ticks → seconds honouring tempo changes.
    current_tempo = 500_000   # default: 120 BPM
    current_tick  = 0
    total_secs    = 0.0

    for change_tick, new_tempo in tempo_map:
        if change_tick >= end_tick:
            break
        total_secs   += (change_tick - current_tick) * current_tempo / ppqn / 1_000_000
        current_tick  = change_tick
        current_tempo = new_tempo

    total_secs += (end_tick - current_tick) * current_tempo / ppqn / 1_000_000
    return total_secs, any_capped


def _load_midi(filepath):
    """Load a MIDI file, retrying with workarounds for known mido parse errors.

    Returns (mid, clipped, smpte_fallback, trim_fallback, key_sig_fallback):
      clipped         — note/data bytes were clamped to valid range
      smpte_fallback  — unrecognised SMPTE frame-rate code was defaulted to 24 fps
      trim_fallback   — trailing/missing track chunk bytes were patched or dropped
      key_sig_fallback— invalid key signature mode byte was replaced with 'major'

    Raises IOError with a descriptive message if the file cannot be read.
    """
    _validate_midi_input(filepath)  # size and magic-byte checks

    import mido.midifiles.meta as _meta

    def _try_load(clip):
        return mido.MidiFile(filepath, clip=clip)

    def _try_load_smpte_tolerant(clip):
        # Some files contain SMPTE Offset meta events (0xFF 0x54) with
        # out-of-spec frame-rate codes that mido rejects with KeyError.
        # Patch the decode method to fall back to 24 fps for unknown codes.
        orig_decode = _meta.MetaSpec_smpte_offset.decode

        def _lenient_decode(self, message, data):
            fr_code = data[0] >> 5
            message.frame_rate = _meta._smpte_framerate_decode.get(fr_code, 24)
            message.hours = data[0] & 0b00011111
            message.minutes = data[1]
            message.seconds = data[2]
            message.frames = data[3]
            message.sub_frames = data[4]

        _meta.MetaSpec_smpte_offset.decode = _lenient_decode
        try:
            return mido.MidiFile(filepath, clip=clip)
        finally:
            _meta.MetaSpec_smpte_offset.decode = orig_decode

    def _try_load_key_sig_tolerant(clip):
        # Some files contain key signature meta events (0xFF 0x59) with an
        # invalid mode byte (e.g. 0xFF = 255 instead of 0 = major / 1 = minor).
        # Patch the decode method to fall back gracefully rather than raising
        # KeySignatureError.
        orig_decode = _meta.MetaSpec_key_signature.decode

        def _lenient_decode(self, message, data):
            key  = _meta.signed('byte', data[0])
            mode = data[1]
            try:
                message.key = _meta._key_signature_decode[(key, mode)]
            except KeyError:
                # Try the same key count as major; then fall back to C major.
                message.key = _meta._key_signature_decode.get((key, 0), 'C')

        _meta.MetaSpec_key_signature.decode = _lenient_decode
        try:
            return mido.MidiFile(filepath, clip=clip)
        finally:
            _meta.MetaSpec_key_signature.decode = orig_decode

    def _try_load_trimmed(clip):
        # Some files have padding bytes after the End of Track marker inside
        # one or more track chunks, which causes mido to raise EOFError.
        # Strip the garbage and reload from an in-memory BytesIO.
        buf = _trim_track_garbage(filepath)
        if buf is None:
            raise ValueError("no trimming needed or possible")
        return mido.MidiFile(file=buf, clip=clip)

    for clip in (False, True):
        try:
            return _try_load(clip), clip, False, False, False
        except EOFError:
            # Likely trailing garbage after an End of Track marker.
            try:
                return _try_load_trimmed(clip), clip, False, True, False
            except Exception:
                pass
        except KeyError:
            # Likely an unrecognised SMPTE frame-rate code — retry with patch.
            try:
                return _try_load_smpte_tolerant(clip), clip, True, False, False
            except Exception:
                pass
        except _meta.KeySignatureError:
            # Invalid key signature mode byte — retry with lenient decoder.
            try:
                return _try_load_key_sig_tolerant(clip), clip, False, False, True
            except Exception:
                pass
        except Exception:
            pass

    # All attempts failed — run once more to capture a clean error message.
    try:
        _try_load(clip=True)
    except Exception as e:
        raise IOError(f"Cannot open MIDI file: {e}") from e
    raise IOError("Cannot open MIDI file: unknown error")


def analyze_midi_file(filepath):
    """Analyze a MIDI file and return structured data."""
    mid, clipped, smpte_fallback, trim_fallback, key_sig_fallback = _load_midi(filepath)

    results = {
        "file_info": {},
        "metadata": {},
        "timing": {},
        "sysex": [],
        "program_changes": [],
        "bank_selects": [],
        "tracks": [],
        "text_events": [],
        "markers": [],
        "cue_points": [],
        "warnings": [],
    }

    if clipped:
        results["warnings"].append(
            "File contains out-of-range data bytes (clipped to valid range during parsing)."
        )
    if smpte_fallback:
        results["warnings"].append(
            "File contains an unrecognised SMPTE frame-rate code in a SMPTE Offset meta event "
            "(0xFF 0x54); the frame rate was ignored and defaulted to 24 fps."
        )
    if trim_fallback:
        results["warnings"].append(
            "File contains malformed track chunk data (trailing bytes after an End of Track "
            "marker, or one or more truncated/missing tracks); the affected data was patched "
            "or dropped during parsing."
        )
    if key_sig_fallback:
        results["warnings"].append(
            "File contains a key signature meta event (0xFF 0x59) with an invalid mode byte; "
            "the mode was replaced with 'major' during parsing."
        )

    length_secs, delta_capped = _compute_length(mid)
    results["file_info"]["length_seconds"] = length_secs
    if delta_capped:
        results["warnings"].append(
            "File contains one or more delta times exceeding the MIDI spec maximum "
            "(0x0FFFFFFF ticks); oversized deltas were capped when computing song length."
        )

    # File info
    results["file_info"]["filename"] = filepath
    results["file_info"]["format"] = mid.type
    results["file_info"]["num_tracks"] = len(mid.tracks)
    results["file_info"]["length_seconds"] = length_secs

    # PPQN / Ticks per beat
    results["timing"]["ppqn"] = mid.ticks_per_beat

    # Check for SMPTE timing
    # In mido, SMPTE timing is indicated by negative ticks_per_beat
    if mid.ticks_per_beat < 0:
        results["timing"]["timing_type"] = "SMPTE"
        # Extract SMPTE format from the value
        fps = -(mid.ticks_per_beat >> 8)
        subframes = mid.ticks_per_beat & 0xFF
        results["timing"]["smpte_fps"] = fps
        results["timing"]["smpte_subframes"] = subframes
    else:
        results["timing"]["timing_type"] = "PPQ"

    # Track bank select state per channel
    channel_banks = defaultdict(lambda: {"msb": 0, "lsb": 0})

    # Track note-on absolute times per channel (for post-processing)
    channel_note_ons = defaultdict(list)

    # Track detected MIDI standard (GM, GM2, GS, XG)
    detected_standard = None

    # First pass: collect time signatures with absolute times
    # (needed for measure/beat calculations)
    time_signatures_abs = []
    for track in mid.tracks:
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.type == 'time_signature':
                time_signatures_abs.append({
                    "abs_time": abs_time,
                    "numerator": msg.numerator,
                    "denominator": msg.denominator
                })
    # Sort by absolute time and remove duplicates at same position
    time_signatures_abs.sort(key=lambda x: x["abs_time"])
    # Store for use in output formatting
    results["timing"]["time_signatures_abs"] = time_signatures_abs

    # Process each track
    for track_idx, track in enumerate(mid.tracks):
        track_info = {
            "index": track_idx,
            "name": None,
            "events": 0
        }

        # Track absolute time for this track
        abs_time = 0

        for msg in track:
            abs_time += msg.time
            track_info["events"] += 1

            # Meta messages
            if msg.type == 'track_name':
                track_info["name"] = decode_midi_text(msg.name)
                if track_idx == 0:
                    results["metadata"]["sequence_name"] = decode_midi_text(msg.name)

            elif msg.type == 'copyright':
                results["metadata"]["copyright"] = decode_midi_text(msg.text)

            elif msg.type == 'text':
                results["text_events"].append({
                    "track": track_idx,
                    "text": decode_midi_text(msg.text),
                    "abs_time": abs_time
                })

            elif msg.type == 'marker':
                results["markers"].append({
                    "track": track_idx,
                    "marker": decode_midi_text(msg.text),
                    "abs_time": abs_time
                })

            elif msg.type == 'cue_marker':
                results["cue_points"].append({
                    "track": track_idx,
                    "cue": decode_midi_text(msg.text),
                    "abs_time": abs_time
                })

            elif msg.type == 'set_tempo':
                if "tempo" not in results["timing"]:
                    results["timing"]["tempo"] = []
                bpm = mido.tempo2bpm(msg.tempo)
                results["timing"]["tempo"].append({
                    "microseconds_per_beat": msg.tempo,
                    "bpm": round(bpm, 2),
                    "abs_time": abs_time
                })

            elif msg.type == 'time_signature':
                if "time_signature" not in results["timing"]:
                    results["timing"]["time_signature"] = []
                notated_32nd = msg.notated_32nd_notes_per_beat
                if notated_32nd == 0:
                    warn = "File contains an invalid notated_32nd_notes_per_beat value of 0 in a time signature event; defaulted to 8."
                    if warn not in results["warnings"]:
                        results["warnings"].append(warn)
                    notated_32nd = 8
                results["timing"]["time_signature"].append({
                    "numerator": msg.numerator,
                    "denominator": msg.denominator,
                    "clocks_per_click": msg.clocks_per_click,
                    "notated_32nd_notes_per_beat": notated_32nd,
                    "abs_time": abs_time
                })

            elif msg.type == 'key_signature':
                results["metadata"]["key_signature"] = {
                    "key": msg.key
                }

            elif msg.type == 'smpte_offset':
                results["timing"]["smpte_offset"] = {
                    "hours": msg.hours,
                    "minutes": msg.minutes,
                    "seconds": msg.seconds,
                    "frames": msg.frames,
                    "sub_frames": msg.sub_frames,
                    "formatted": format_smpte(msg.hours, msg.minutes, msg.seconds,
                                             msg.frames, msg.sub_frames)
                }

            elif msg.type == 'instrument_name':
                if "instruments" not in results["metadata"]:
                    results["metadata"]["instruments"] = []
                results["metadata"]["instruments"].append({
                    "track": track_idx,
                    "name": decode_midi_text(msg.name)
                })

            elif msg.type == 'lyrics':
                if "lyrics" not in results["metadata"]:
                    results["metadata"]["lyrics"] = []
                results["metadata"]["lyrics"].append({
                    "track": track_idx,
                    "text": decode_midi_text(msg.text),
                    "abs_time": abs_time
                })

            # SysEx messages
            elif msg.type == 'sysex':
                sysex_type, description = identify_sysex(msg.data)
                results["sysex"].append({
                    "track": track_idx,
                    "type": sysex_type,
                    "description": description,
                    "data": list(msg.data),
                    "data_hex": ' '.join(f'{b:02X}' for b in msg.data)
                })
                # Track detected MIDI standard (priority: XG > GS > GM2 > GM)
                if sysex_type in ("GM", "GM2", "GS", "XG"):
                    standard_priority = {"GM": 1, "GM2": 2, "GS": 3, "XG": 4}
                    current_priority = standard_priority.get(detected_standard, 0)
                    if standard_priority[sysex_type] > current_priority:
                        detected_standard = sysex_type

            # Note-ons: track abs_time per channel for post-processing
            elif msg.type == 'note_on' and msg.velocity > 0:
                channel_note_ons[msg.channel + 1].append(abs_time)

            # Control changes (Bank Select)
            elif msg.type == 'control_change':
                if msg.control == 0:  # Bank Select MSB
                    channel_banks[msg.channel]["msb"] = msg.value
                    results["bank_selects"].append({
                        "track": track_idx,
                        "channel": msg.channel + 1,
                        "type": "MSB",
                        "value": msg.value,
                        "abs_time": abs_time
                    })
                elif msg.control == 32:  # Bank Select LSB
                    channel_banks[msg.channel]["lsb"] = msg.value
                    results["bank_selects"].append({
                        "track": track_idx,
                        "channel": msg.channel + 1,
                        "type": "LSB",
                        "value": msg.value,
                        "abs_time": abs_time
                    })

            # Program changes
            elif msg.type == 'program_change':
                bank = channel_banks[msg.channel]
                channel_num = msg.channel + 1  # Convert to 1-indexed
                results["program_changes"].append({
                    "track": track_idx,
                    "channel": channel_num,
                    "program": msg.program,
                    "program_name": get_instrument_name(
                        msg.program, channel_num,
                        bank["msb"], bank["lsb"],
                        detected_standard
                    ),
                    "bank_msb": bank["msb"],
                    "bank_lsb": bank["lsb"],
                    "is_percussion": channel_num == 10,
                    "abs_time": abs_time
                })

        results["tracks"].append(track_info)

    # If no standard detected via SysEx, check if file is GM-compatible:
    # all bank selects must use value=0 (base GM range)
    standard_assumed = False
    standard_assumed_reason = None
    standard_unknown_reason = None
    standard_upgraded_from = None   # set when GM→GM2 upgrade happens
    standard_upgrade_reason = None
    if detected_standard is None:
        has_bank_selects = bool(results["bank_selects"])
        has_program_changes = bool(results["program_changes"])
        all_gm_banks = all(
            bs["value"] == 0
            for bs in results["bank_selects"]
        )
        if not has_bank_selects and not has_program_changes:
            # No MIDI standard evidence at all — leave as unknown
            standard_unknown_reason = "no SysEx, bank select, or program change messages detected"
        elif all_gm_banks:
            detected_standard = "GM"
            standard_assumed = True
            if has_bank_selects:
                standard_assumed_reason = "no reset SysEx found; all bank selects use GM values"
            else:
                standard_assumed_reason = "no reset SysEx found; no bank selects detected"
        else:
            # Build a human-readable reason. Non-zero MSBs are the primary
            # indicator; only fall back to LSBs if all MSBs are zero.
            bad_msbs = sorted({
                (bs["channel"], bs["value"])
                for bs in results["bank_selects"]
                if bs["type"] == "MSB" and bs["value"] != 0
            })
            if bad_msbs:
                parts = [f"MSB {v} on channel {ch}" for ch, v in bad_msbs]
                noun = "value" if len(parts) == 1 else "values"
                standard_unknown_reason = (
                    f"no SysEx detected; unrecognized bank {noun}: "
                    + ", ".join(parts)
                )
            else:
                bad_lsbs = sorted({
                    (bs["channel"], bs["value"])
                    for bs in results["bank_selects"]
                    if bs["type"] == "LSB" and bs["value"] != 0
                })
                parts = [f"LSB {v} on channel {ch}" for ch, v in bad_lsbs]
                noun = "value" if len(parts) == 1 else "values"
                standard_unknown_reason = (
                    f"no SysEx detected; non-standard bank {noun}: "
                    + ", ".join(parts)
                )

    # If a GM Reset was detected, check whether the file actually targets GM2:
    # GM only defines program 0 on the percussion channel. Any other program
    # on channel 10 implies the file requires GM2 (which adds TR-808, Jazz,
    # Brush, Orchestra kits, etc.).
    if detected_standard == "GM":
        ch10_non_gm = any(
            pc["program"] != 0
            for pc in results["program_changes"]
            if pc["is_percussion"]
        )
        if ch10_non_gm:
            non_gm_kits = sorted({
                pc["program"]
                for pc in results["program_changes"]
                if pc["is_percussion"] and pc["program"] != 0
            })
            kit_list = ", ".join(str(p) for p in non_gm_kits)
            noun = "program" if len(non_gm_kits) == 1 else "programs"
            upgrade_reason = f"GM2-only percussion {noun} on channel 10: {kit_list}"
            if standard_assumed:
                # GM was itself assumed (no SysEx); keep assumed path
                standard_assumed_reason = (
                    f"no reset SysEx found; non-GM percussion {noun} on channel 10: {kit_list}"
                )
            else:
                # GM was confirmed via SysEx; record the upgrade separately
                standard_upgraded_from = "GM"
                standard_upgrade_reason = upgrade_reason
            detected_standard = "GM2"

    # Store detected MIDI standard
    results["detected_standard"] = detected_standard
    results["standard_assumed"] = standard_assumed
    results["standard_assumed_reason"] = standard_assumed_reason
    results["standard_unknown_reason"] = standard_unknown_reason
    results["standard_upgraded_from"] = standard_upgraded_from
    results["standard_upgrade_reason"] = standard_upgrade_reason

    # Detect Soft Karaoke (KAR) format: look for the canonical @KMIDI marker
    # in text events.  Collect @V version, @T titles, @L language, @I info,
    # @K keywords, @W warnings.  The marker may have a trailing suffix (e.g.
    # "tm"), so use startswith.  @KMIDI must be checked before @K.
    kar_version = None
    kar_titles = []
    kar_languages = []
    kar_info = []
    kar_keywords = []
    kar_warnings = []
    is_karaoke = False
    for evt in results["text_events"]:
        t = evt["text"].strip()
        if t.startswith("@KMIDI KARAOKE FILE"):
            is_karaoke = True
        elif t.startswith("@V"):
            kar_version = t[2:].strip()
        elif t.startswith("@T"):
            kar_titles.append(t[2:].strip())
        elif t.startswith("@L"):
            kar_languages.append(t[2:].strip())
        elif t.startswith("@I"):
            kar_info.append(t[2:].strip())
        elif t.startswith("@K"):
            kar_keywords.append(t[2:].strip())
        elif t.startswith("@W"):
            kar_warnings.append(t[2:].strip())
    results["karaoke"] = {
        "is_karaoke": is_karaoke,
        "version": kar_version,
        "titles": kar_titles,
        "languages": kar_languages,
        "info": kar_info,
        "keywords": kar_keywords,
        "warnings": kar_warnings,
    } if is_karaoke else None

    # Post-process program changes: fix cases where a bank select arrived
    # AFTER the program change on the same channel.  Some files send the
    # program change first, then CC0/CC32.  This includes the same-tick case
    # where bank selects share the exact abs_time as the program change but
    # appear later in the byte stream.  Only apply the bank retroactively if
    # NO note-on events on that channel occurred between the program change and
    # the bank select — if notes were played first, the bank select is a new
    # instrument selection, not a correction to the earlier program change.

    # Build per-channel bank-select timeline: sorted list of
    # (abs_time, running_msb, running_lsb) after each MSB or LSB event.
    channel_bs_timeline = defaultdict(list)
    for ch in set(bs["channel"] for bs in results["bank_selects"]):
        ch_bss = sorted(
            (bs for bs in results["bank_selects"] if bs["channel"] == ch),
            key=lambda b: b["abs_time"]
        )
        cur_msb, cur_lsb = 0, 0
        for bs in ch_bss:
            if bs["type"] == "MSB":
                cur_msb = bs["value"]
            else:
                cur_lsb = bs["value"]
            channel_bs_timeline[ch].append((bs["abs_time"], cur_msb, cur_lsb))

    for pc in results["program_changes"]:
        if pc["bank_msb"] != 0 or pc["bank_lsb"] != 0:
            continue
        ch = pc["channel"]
        if ch not in channel_bs_timeline:
            continue
        pc_time = pc["abs_time"]
        # First bank select at or after this program change (same-tick bank
        # selects that follow the PC in byte order are treated as paired).
        future = [(t, m, l) for (t, m, l) in channel_bs_timeline[ch] if t >= pc_time]
        if not future:
            continue
        bs_time, new_msb, new_lsb = future[0]
        if new_msb == 0 and new_lsb == 0:
            continue
        # If any note-on on this channel falls strictly between the program
        # change and the bank select, the bank select belongs to a new
        # instrument selection.  Same-tick note-ons are allowed (they fire
        # simultaneously with the setup messages).
        if any(pc_time < t < bs_time for t in channel_note_ons[ch]):
            continue
        pc["bank_msb"] = new_msb
        pc["bank_lsb"] = new_lsb

    # Re-resolve program names now that the final standard is known.
    # Names were looked up during the track loop when detected_standard may
    # have been None or GM; refresh them so every entry reflects the correct
    # standard (e.g. GM2 percussion kit names after a GM→GM2 upgrade).
    # When the standard is unknown, leave program_name as None so the display
    # omits patch database names.
    for pc in results["program_changes"]:
        if detected_standard is None:
            pc["program_name"] = None
        else:
            pc["program_name"] = get_instrument_name(
                pc["program"], pc["channel"],
                pc["bank_msb"], pc["bank_lsb"],
                detected_standard
            )

    # For GM/GM2: if a channel has note-ons but no program change, it uses the
    # default program 0 on bank 0:0.  Add a synthetic entry so the channel
    # appears in the Program output.
    if detected_standard in ("GM", "GM2"):
        channels_with_pc = {pc["channel"] for pc in results["program_changes"]}
        for ch, note_times in sorted(channel_note_ons.items()):
            if note_times and ch not in channels_with_pc:
                results["program_changes"].append({
                    "track": 0,
                    "channel": ch,
                    "program": 0,
                    "program_name": get_instrument_name(
                        0, ch, 0, 0, detected_standard
                    ),
                    "bank_msb": 0,
                    "bank_lsb": 0,
                    "is_percussion": ch == 10,
                    "abs_time": note_times[0],
                    "assumed": True,
                })

    # For XG: Bank Select MSB 127 designates any channel as a rhythm/percussion
    # channel, not just channel 10. MSB 126 is the SFX kit, also rhythm-arranged.
    # Apply this after standard is finalized and names are re-resolved.
    if detected_standard == "XG":
        for pc in results["program_changes"]:
            if pc["bank_msb"] in (126, 127) and not pc["is_percussion"]:
                pc["is_percussion"] = True
                name = midi_patches_db.get_percussion_name(
                    pc["bank_msb"], pc["bank_lsb"], pc["program"], detected_standard
                )
                pc["program_name"] = name if name else f"Drum Kit {pc['program']}"

    # Determine minimum Sound Canvas version for GS files
    if detected_standard == "GS":
        results["gs_info"] = determine_minimum_sc_version(results)

    # Determine minimum XG level for XG files
    if detected_standard == "XG":
        results["xg_info"] = determine_minimum_xg_level(results)

    # Collect per-channel / per-track statistics
    _collect_statistics(mid, results)

    return results


def _collect_statistics(mid, results):
    """Collect per-channel and per-track event statistics from the MIDI data.

    Runs a separate pass over the raw MIDI messages so that the main analysis
    loop stays uncluttered.  Results are stored in results["statistics"].
    """
    ppqn = mid.ticks_per_beat if mid.ticks_per_beat > 0 else 480

    ch_acc = {}   # channel (1-indexed) -> accumulator dict
    tr_acc = {}   # track index -> accumulator dict

    def _ch(ch):
        if ch not in ch_acc:
            ch_acc[ch] = {
                "note_count": 0,
                "pitch_min": 127, "pitch_max": 0,
                "vel_min": 127,   "vel_max": 0,  "vel_sum": 0,
                "dur_ticks": [],
                "pending": {},    # pitch -> abs_tick of most-recent note-on
                "active":  set(), # currently sounding pitches (polyphony)
                "peak_poly": 0,
                "cc": {},         # cc_num -> event count
                "pb_count": 0, "pb_min": 8191, "pb_max": -8192,
                "at_count": 0, "at_min": 127,  "at_max": 0,
                "poly_at_count": 0,
            }
        return ch_acc[ch]

    def _tr(ti):
        if ti not in tr_acc:
            tr_acc[ti] = {
                "note_on": 0, "note_off": 0,
                "cc": 0, "pb": 0, "at": 0, "poly_at": 0, "sysex": 0,
            }
        return tr_acc[ti]

    global_active = {}   # (channel, pitch) -> True
    global_peak   = 0
    totals = {
        "note_on": 0, "note_off": 0, "control_change": 0,
        "pitch_bend": 0, "aftertouch": 0, "poly_aftertouch": 0,
        "program_change": 0, "sysex": 0,
    }

    for track_idx, track in enumerate(mid.tracks):
        tr  = _tr(track_idx)
        abs_time = 0
        for msg in track:
            abs_time += msg.time
            if msg.is_meta:
                continue
            ch = getattr(msg, 'channel', None)
            if ch is not None:
                ch += 1   # convert to 1-indexed
            t = msg.type

            if t == 'note_on' and msg.velocity > 0:
                c = _ch(ch)
                tr["note_on"] += 1;  totals["note_on"] += 1
                c["note_count"] += 1
                if msg.note < c["pitch_min"]: c["pitch_min"] = msg.note
                if msg.note > c["pitch_max"]: c["pitch_max"] = msg.note
                if msg.velocity < c["vel_min"]: c["vel_min"] = msg.velocity
                if msg.velocity > c["vel_max"]: c["vel_max"] = msg.velocity
                c["vel_sum"] += msg.velocity
                c["pending"][msg.note] = abs_time
                c["active"].add(msg.note)
                if len(c["active"]) > c["peak_poly"]:
                    c["peak_poly"] = len(c["active"])
                global_active[(ch, msg.note)] = True
                if len(global_active) > global_peak:
                    global_peak = len(global_active)

            elif t == 'note_off' or (t == 'note_on' and msg.velocity == 0):
                c = _ch(ch)
                tr["note_off"] += 1;  totals["note_off"] += 1
                c["active"].discard(msg.note)
                global_active.pop((ch, msg.note), None)
                start = c["pending"].pop(msg.note, None)
                if start is not None:
                    c["dur_ticks"].append(abs_time - start)

            elif t == 'control_change':
                c = _ch(ch)
                tr["cc"] += 1;  totals["control_change"] += 1
                c["cc"][msg.control] = c["cc"].get(msg.control, 0) + 1

            elif t == 'pitchwheel':
                c = _ch(ch)
                tr["pb"] += 1;  totals["pitch_bend"] += 1
                c["pb_count"] += 1
                if msg.pitch < c["pb_min"]: c["pb_min"] = msg.pitch
                if msg.pitch > c["pb_max"]: c["pb_max"] = msg.pitch

            elif t == 'aftertouch':
                c = _ch(ch)
                tr["at"] += 1;  totals["aftertouch"] += 1
                c["at_count"] += 1
                if msg.value < c["at_min"]: c["at_min"] = msg.value
                if msg.value > c["at_max"]: c["at_max"] = msg.value

            elif t == 'polytouch':
                c = _ch(ch)
                tr["poly_at"] += 1;  totals["poly_aftertouch"] += 1
                c["poly_at_count"] += 1

            elif t == 'program_change':
                totals["program_change"] += 1

            elif t == 'sysex':
                tr["sysex"] += 1;  totals["sysex"] += 1

    # ── Convert accumulators to clean, JSON-serialisable dicts ────────────────

    by_channel = {}
    for ch in sorted(ch_acc):
        a = ch_acc[ch]
        entry = {"note_count": a["note_count"]}
        if a["note_count"] > 0:
            entry["pitch_min"]      = a["pitch_min"]
            entry["pitch_max"]      = a["pitch_max"]
            entry["vel_min"]        = a["vel_min"]
            entry["vel_max"]        = a["vel_max"]
            entry["vel_avg"]        = round(a["vel_sum"] / a["note_count"], 1)
            entry["peak_polyphony"] = a["peak_poly"]
            if a["dur_ticks"]:
                entry["dur_avg_beats"] = round(
                    sum(a["dur_ticks"]) / len(a["dur_ticks"]) / ppqn, 3)
                entry["dur_min_beats"] = round(min(a["dur_ticks"]) / ppqn, 3)
                entry["dur_max_beats"] = round(max(a["dur_ticks"]) / ppqn, 3)
        if a["cc"]:
            entry["control_changes"] = {k: v for k, v in sorted(a["cc"].items())}
        if a["pb_count"]:
            entry["pitch_bend"] = {
                "count": a["pb_count"], "min": a["pb_min"], "max": a["pb_max"],
            }
        if a["at_count"]:
            entry["aftertouch"] = {
                "count": a["at_count"], "min": a["at_min"], "max": a["at_max"],
            }
        if a["poly_at_count"]:
            entry["poly_aftertouch_count"] = a["poly_at_count"]
        by_channel[ch] = entry

    by_track = {ti: dict(a) for ti, a in sorted(tr_acc.items())}

    results["statistics"] = {
        "by_channel":          by_channel,
        "by_track":            by_track,
        "totals":              totals,
        "global_peak_polyphony": global_peak,
    }


def sanitize_text(text):
    """Strip non-printable control characters from MIDI text strings.

    MIDI text events sometimes contain embedded null bytes or other control
    characters used as padding. Terminals silently ignore them, but GUI text
    widgets render them as visible replacement-character boxes. Strip anything
    below U+0020 except horizontal tab.
    """
    return ''.join(ch for ch in text if ch == '\t' or ord(ch) >= 0x20)


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print('=' * 60)


def print_subsection(title):
    """Print a subsection header."""
    print(f"\n--- {title} ---")


def _print_statistics(results):
    """Print the STATISTICS section."""
    stats = results.get("statistics")
    if not stats:
        return

    percussion_channels = {
        pc["channel"] for pc in results.get("program_changes", [])
        if pc.get("is_percussion")
    }

    print_section("STATISTICS")

    by_channel = stats["by_channel"]

    # ── Notes by channel ──────────────────────────────────────────────────────
    note_channels = {ch: d for ch, d in by_channel.items() if d["note_count"] > 0}
    if note_channels:
        print_subsection("Notes by Channel")
        for ch, d in sorted(note_channels.items()):
            is_perc = ch in percussion_channels
            print(f"  Ch {ch:2d}" + (" (Perc):" if is_perc else ":"))
            print(f"    Notes:      {d['note_count']:,}")
            print(f"    Pitch:      {_midi_note_name(d['pitch_min'])}–{_midi_note_name(d['pitch_max'])}")
            print(f"    Velocity:   {d['vel_min']}–{d['vel_max']}  avg {d['vel_avg']:.0f}")
            if "dur_avg_beats" in d:
                print(f"    Duration:   {d['dur_min_beats']:.2f}–{d['dur_max_beats']:.2f}  avg {d['dur_avg_beats']:.2f} beats")
            print(f"    Polyphony:  peak {d['peak_polyphony']}")

    # ── Control changes by channel ────────────────────────────────────────────
    cc_channels = {ch: d for ch, d in by_channel.items() if d.get("control_changes")}
    if cc_channels:
        print_subsection("Control Changes by Channel")
        for ch, d in sorted(cc_channels.items()):
            print(f"  Ch {ch:2d}:")
            for cc_num, count in sorted(d["control_changes"].items()):
                name = _CC_NAMES.get(cc_num)
                label = f"CC {cc_num:3d}"
                if name:
                    label += f" ({name})"
                print(f"    {label} ×{count}")

    # ── Pitch bend by channel ─────────────────────────────────────────────────
    pb_channels = {ch: d for ch, d in by_channel.items() if d.get("pitch_bend")}
    if pb_channels:
        print_subsection("Pitch Bend by Channel")
        for ch, d in sorted(pb_channels.items()):
            pb = d["pitch_bend"]
            print(f"  Ch {ch:2d}:")
            print(f"    Events:     {pb['count']:,}")
            print(f"    Range:      {pb['min']:+d} to {pb['max']:+d}  (full range: ±8191)")

    # ── Aftertouch by channel ─────────────────────────────────────────────────
    at_channels      = {ch: d for ch, d in by_channel.items() if d.get("aftertouch")}
    poly_at_channels = {ch: d for ch, d in by_channel.items()
                        if d.get("poly_aftertouch_count", 0) > 0}
    if at_channels or poly_at_channels:
        print_subsection("Aftertouch by Channel")
        if at_channels:
            print("  Channel Aftertouch:")
            for ch, d in sorted(at_channels.items()):
                at = d["aftertouch"]
                print(f"    Ch {ch:2d}:")
                print(f"      Events:   {at['count']:,}")
                print(f"      Range:    {at['min']}–{at['max']}")
        if poly_at_channels:
            print("  Polyphonic Aftertouch:")
            for ch, d in sorted(poly_at_channels.items()):
                print(f"    Ch {ch:2d}:")
                print(f"      Events:   {d['poly_aftertouch_count']:,}")

    # ── Per-track event breakdown ─────────────────────────────────────────────
    by_track = stats["by_track"]
    perf_tracks = {
        ti: d for ti, d in by_track.items()
        if any(d[k] > 0 for k in ("note_on", "cc", "pb", "at", "poly_at", "sysex"))
    }
    if perf_tracks:
        print_subsection("Event Breakdown by Track")
        for ti, d in sorted(perf_tracks.items()):
            name = ""
            if ti < len(results["tracks"]):
                tn = results["tracks"][ti].get("name")
                if tn:
                    name = f" ({sanitize_text(tn)[:24]})"
            print(f"  Trk {ti:2d}{name}:")
            if d["note_on"]:  print(f"    Notes:      {d['note_on']:,}")
            if d["cc"]:       print(f"    CC:         {d['cc']:,}")
            if d["pb"]:       print(f"    Pitch Bend: {d['pb']:,}")
            if d["at"]:       print(f"    Aftertouch: {d['at']:,}")
            if d["poly_at"]:  print(f"    Poly AT:    {d['poly_at']:,}")
            if d["sysex"]:    print(f"    SysEx:      {d['sysex']:,}")

    # ── Event totals ──────────────────────────────────────────────────────────
    print_subsection("Event Totals")
    t = stats["totals"]
    rows = [
        ("Note On",            t["note_on"]),
        ("Note Off",           t["note_off"]),
        ("Control Changes",    t["control_change"]),
        ("Pitch Bend",         t["pitch_bend"]),
        ("Channel Aftertouch", t["aftertouch"]),
        ("Poly Aftertouch",    t["poly_aftertouch"]),
        ("Program Changes",    t["program_change"]),
        ("SysEx",              t["sysex"]),
    ]
    for label, value in rows:
        if value > 0:
            print(f"  {label:<22} {value:>7,}")
    gp = stats.get("global_peak_polyphony", 0)
    if gp:
        print(f"  {'Global Peak Polyphony':<22} {gp:>7}")


def _karaoke_lyric_texts(text_events):
    """Return sanitized text strings from the karaoke lyrics track(s).

    Only includes events from tracks that contain at least one syllable with a
    \\ or / line-break prefix; filters out @-prefixed karaoke metadata lines.
    This avoids mixing in unrelated text events (e.g. sequencer credits) that
    happen to sit in non-karaoke tracks of the same file.
    """
    lyric_tracks = {
        e["track"] for e in text_events
        if sanitize_text(e["text"]).startswith("\\") or sanitize_text(e["text"]).startswith("/")
    }
    return [
        sanitize_text(e["text"]) for e in text_events
        if e["track"] in lyric_tracks and not sanitize_text(e["text"]).startswith("@")
    ]


def _assemble_karaoke_lines(raw_texts):
    """Assemble a list of raw karaoke syllable strings into (is_para, line) pairs.

    Syllables starting with \\ begin a new paragraph (blank line before the
    line they start); syllables starting with / begin a new line within the
    current paragraph (no blank line).

    The is_para flag is carried forward and attached to the line being
    *started*, not to the line being flushed, so blank lines appear in the
    right place.

    Returns a list of (is_paragraph_break, assembled_line) tuples, or an
    empty list if no line-break markers are present.
    """
    if not any(t.startswith("\\") or t.startswith("/") for t in raw_texts):
        return []
    lines = []
    current = ""
    next_is_para = False
    first = True
    for text in raw_texts:
        if text.startswith("\\") or text.startswith("/"):
            if current.strip() or not first:
                lines.append((next_is_para, current.rstrip()))
            next_is_para = text.startswith("\\")
            current = text[1:]
            first = False
        else:
            current += text
    if current.strip():
        lines.append((next_is_para, current.rstrip()))
    return lines


def _print_karaoke_lines(lines):
    """Print assembled karaoke lines, inserting blank lines before paragraphs."""
    for i, (is_para, line) in enumerate(lines):
        if is_para and i > 0:
            print()
        print(f"  {line}")


def _join_syllables(syllables):
    """Join syllables into a word/phrase, respecting continuation markers.

    A hyphen or underscore at the end of a syllable means the next syllable
    continues the same word (no space inserted).  If the syllable already
    carries its own leading/trailing space, that space is preserved.
    """
    if not syllables:
        return ""
    result = syllables[0]
    for syl in syllables[1:]:
        if result.endswith("-") or result.endswith("_"):
            result += syl
        elif result.endswith(" ") or syl.startswith(" "):
            result += syl
        else:
            result += " " + syl
    return result


def _assemble_lyrics_by_measure(lyrics, ppqn, time_sigs_abs):
    """Group lyric syllables by measure, returning one string per measure line.

    Syllables within the same measure are joined using _join_syllables so that
    word-continuation hyphens are respected and spaces are added between words.
    Returns a list of non-empty strings.
    """
    lines = []
    current_measure = None
    current_syllables = []
    for lyric in lyrics:
        measure, _, _ = ticks_to_measure_beat(lyric["abs_time"], ppqn, time_sigs_abs)
        text = sanitize_text(lyric["text"])
        if measure != current_measure:
            if current_syllables:
                joined = _join_syllables(current_syllables).strip()
                if joined:
                    lines.append(joined)
            current_measure = measure
            current_syllables = [text]
        else:
            current_syllables.append(text)
    if current_syllables:
        joined = _join_syllables(current_syllables).strip()
        if joined:
            lines.append(joined)
    return lines


def print_results(results):
    """Print the analysis results in a readable format."""

    # Warnings
    for warning in results.get("warnings", []):
        print(f"WARNING: {warning}")

    # File Information
    print_section("FILE INFORMATION")
    info = results["file_info"]
    print(f"  Filename:      {info['filename']}")
    try:
        size_bytes = os.path.getsize(info['filename'])
        if size_bytes < 1024:
            size_str = f"{size_bytes} bytes"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB ({size_bytes:,} bytes)"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB ({size_bytes:,} bytes)"
        print(f"  File Size:     {size_str}")
    except OSError:
        pass
    format_names = {0: "Single Track (Type 0)", 1: "Multi Track (Type 1)", 2: "Multi Song (Type 2)"}
    format_type = info['format']
    format_desc = format_names.get(format_type, f"Unknown ({format_type})")
    print(f"  Format:        {format_desc}")
    print(f"  Tracks:        {info['num_tracks']}")
    if info['length_seconds']:
        minutes = int(info['length_seconds'] // 60)
        seconds = info['length_seconds'] % 60
        print(f"  Length:        {minutes}:{seconds:05.2f}")
    standard = results.get("detected_standard")
    if standard:
        assumed = results.get("standard_assumed", False)
        upgraded_from = results.get("standard_upgraded_from")
        if assumed:
            reason = results.get("standard_assumed_reason") or "no reset SysEx found"
            suffix = f" (assumed — {reason})"
        elif upgraded_from:
            upgrade_reason = results.get("standard_upgrade_reason", "")
            suffix = f" ({upgraded_from} detected via SysEx; {upgrade_reason})"
        else:
            suffix = " (detected via SysEx)"
        print(f"  MIDI Standard: {_colorize_standard(standard + suffix, standard)}")
        if standard == "GS" and "gs_info" in results:
            gs = results["gs_info"]
            sc_line = f"  Roland SC Req:  {gs['minimum_sc_version']}"
            if gs.get("minimum_sc_reason"):
                sc_line += f" ({gs['minimum_sc_reason']})"
            print(sc_line)
            if gs["uses_cm64_pcm"]:
                print(f"  CM-64 PCM:      Yes (MSB 126)")
            if gs["uses_cm64_la"]:
                print(f"  CM-64 LA:       Yes (MSB 127)")
        if standard == "XG" and "xg_info" in results:
            xg = results["xg_info"]
            xg_line = f"  Yamaha XG Req:  {xg['minimum_xg_device']}"
            if xg.get("minimum_xg_reason"):
                xg_line += f" ({xg['minimum_xg_reason']})"
            print(xg_line)
    else:
        reason = results.get("standard_unknown_reason")
        if reason:
            print(f"  MIDI Standard: Unknown ({reason})")
    if results.get("karaoke"):
        kar = results["karaoke"]
        ver = f" v{kar['version']}" if kar.get("version") else ""
        print(f"  Karaoke:       Soft Karaoke (KAR) format{ver}")
        if kar["titles"]:
            print(f"  KAR Title:     {', '.join(kar['titles'])}")
        if kar["languages"]:
            print(f"  KAR Language:  {', '.join(kar['languages'])}")
        if kar["info"]:
            print(f"  KAR Info:      {'; '.join(kar['info'])}")
        if kar.get("keywords"):
            for kw in kar["keywords"]:
                print(f"  KAR Keywords:  {kw}")
        if kar.get("warnings"):
            for w in kar["warnings"]:
                print(f"  KAR Warning:   {w}")

    # Timing Information
    print_section("TIMING INFORMATION")
    timing = results["timing"]

    if timing["timing_type"] == "SMPTE":
        print(f"  Timing Type:   SMPTE")
        print(f"  SMPTE FPS:     {timing.get('smpte_fps', 'N/A')}")
        print(f"  Subframes:     {timing.get('smpte_subframes', 'N/A')}")
    else:
        print(f"  Timing Type:   PPQ (Pulses Per Quarter Note)")
        print(f"  PPQN:          {timing['ppqn']} ticks per quarter note")

    # Get timing info for measure/beat calculations
    ppqn = timing.get("ppqn", 480)
    time_sigs_abs = timing.get("time_signatures_abs", [])

    if "tempo" in timing and timing["tempo"]:
        print_subsection("Tempo Changes")
        for i, tempo in enumerate(timing["tempo"]):
            if i == 0:
                print(f"  Initial:       {tempo['bpm']} BPM ({tempo['microseconds_per_beat']} µs/beat)")
            else:
                pos = format_position(tempo['abs_time'], ppqn, time_sigs_abs)
                print(f"  Change {i}:      {tempo['bpm']} BPM at {pos}")

    if "time_signature" in timing and timing["time_signature"]:
        print_subsection("Time Signature(s)")
        for i, ts in enumerate(timing["time_signature"]):
            sig = f"{ts['numerator']}/{ts['denominator']}"
            if i == 0:
                print(f"  Initial:       {sig}")
            else:
                pos = format_position(ts['abs_time'], ppqn, time_sigs_abs)
                print(f"  Change {i}:      {sig} at {pos}")
            print(f"                 ({ts['clocks_per_click']} MIDI clocks/click, "
                  f"{ts['notated_32nd_notes_per_beat']} 32nd notes/beat)")

    if "smpte_offset" in timing:
        print_subsection("SMPTE Offset")
        print(f"  Offset:        {timing['smpte_offset']['formatted']}")

    # Metadata
    print_section("METADATA")
    meta = results["metadata"]

    if "sequence_name" in meta:
        print(f"  Song Title:    {sanitize_text(meta['sequence_name'])}")
    if "copyright" in meta:
        print(f"  Copyright:     {sanitize_text(meta['copyright'])}")
    if "key_signature" in meta:
        raw_key = meta['key_signature']['key']
        if raw_key.endswith('m'):
            display_key = f"{raw_key[:-1]} minor"
        else:
            display_key = f"{raw_key} major"
        print(f"  Key Signature: {display_key}")
    if "instruments" in meta:
        print_subsection("Instrument Names")
        for inst in meta["instruments"]:
            print(f"    Track {inst['track']}: {sanitize_text(inst['name'])}")

    if not any(key in meta for key in ["sequence_name", "copyright", "key_signature", "instruments"]):
        print("  (No metadata found)")

    # Track Information
    print_section("TRACK INFORMATION")
    for track in results["tracks"]:
        name = sanitize_text(track["name"]) if track["name"] else "(unnamed)"
        print(f"  Track {track['index']:2d}: {name} ({track['events']} events)")

    # Text Events
    if results["text_events"]:
        print_section("TEXT EVENTS")
        for evt in results["text_events"]:
            pos = format_position(evt['abs_time'], ppqn, time_sigs_abs)
            print(f"  Track {evt['track']}: \"{sanitize_text(evt['text'])}\" at {pos}")

    # Markers
    if results["markers"]:
        print_section("MARKERS")
        for marker in results["markers"]:
            pos = format_position(marker['abs_time'], ppqn, time_sigs_abs)
            print(f"  Track {marker['track']}: \"{sanitize_text(marker['marker'])}\" at {pos}")

    # Cue Points
    if results["cue_points"]:
        print_section("CUE POINTS")
        for cue in results["cue_points"]:
            pos = format_position(cue['abs_time'], ppqn, time_sigs_abs)
            print(f"  Track {cue['track']}: \"{sanitize_text(cue['cue'])}\" at {pos}")

    # Lyrics from MIDI lyrics events
    if "lyrics" in results["metadata"] and results["metadata"]["lyrics"]:
        print_section("LYRICS")
        raw_texts = [sanitize_text(l["text"]) for l in results["metadata"]["lyrics"]]
        lines = _assemble_karaoke_lines(raw_texts)
        if not lines:
            # Lyrics events lack break markers; try text events for assembly
            kar_texts = _karaoke_lyric_texts(results["text_events"])
            lines = _assemble_karaoke_lines(kar_texts)
        if lines:
            _print_karaoke_lines(lines)
        else:
            measure_lines = _assemble_lyrics_by_measure(
                results["metadata"]["lyrics"], ppqn, time_sigs_abs
            )
            for line in measure_lines:
                print(f"  {line}")

    # Lyrics assembled from text events (Soft Karaoke files that store lyrics
    # only as text events rather than MIDI lyrics events)
    elif results.get("karaoke"):
        kar_texts = _karaoke_lyric_texts(results["text_events"])
        lines = _assemble_karaoke_lines(kar_texts)
        if lines:
            print_section("LYRICS (FROM TEXT EVENTS)")
            _print_karaoke_lines(lines)

    # SysEx Messages
    print_section("SYSTEM EXCLUSIVE (SYSEX) MESSAGES")
    if results["sysex"]:
        # Categorize SysEx messages
        gm_messages = [s for s in results["sysex"] if s["type"] in ["GM", "GM2"]]
        gs_messages = [s for s in results["sysex"] if s["type"] == "GS"]
        xg_messages = [s for s in results["sysex"] if s["type"] == "XG"]
        other_messages = [s for s in results["sysex"] if s["type"] not in ["GM", "GM2", "GS", "XG"]]

        if gm_messages:
            print_subsection("General MIDI (GM/GM2)")
            for msg in gm_messages:
                print(f"  {msg['description']}")
                print(f"    Data: F0 {msg['data_hex']} F7")

        if gs_messages:
            print_subsection("Roland GS")
            for msg in gs_messages:
                print(f"  {msg['description']}")
                print(f"    Data: F0 {msg['data_hex']} F7")

        if xg_messages:
            print_subsection("Yamaha XG")
            for msg in xg_messages:
                print(f"  {msg['description']}")
                print(f"    Data: F0 {msg['data_hex']} F7")

        if other_messages:
            print_subsection("Other SysEx")
            for msg in other_messages:
                print(f"  Track {msg['track']}: {msg['description']}")
                print(f"    Data: F0 {msg['data_hex']} F7")

        # Summary
        print_subsection("SysEx Summary")
        print(f"  Total SysEx messages: {len(results['sysex'])}")
        print(f"  GM/GM2 detected:      {'Yes' if gm_messages else 'No'}")
        print(f"  Roland GS detected:   {'Yes' if gs_messages else 'No'}")
        print(f"  Yamaha XG detected:   {'Yes' if xg_messages else 'No'}")

    else:
        print("  (No SysEx messages found)")

    # Bank Select Messages
    print_section("BANK SELECT MESSAGES")
    if results["bank_selects"]:
        # Group by channel
        by_channel = defaultdict(list)
        for bs in results["bank_selects"]:
            by_channel[bs["channel"]].append(bs)

        for channel in sorted(by_channel.keys()):
            msgs = by_channel[channel]
            msb_vals = [m["value"] for m in msgs if m["type"] == "MSB"]
            lsb_vals = [m["value"] for m in msgs if m["type"] == "LSB"]
            print(f"  Channel {channel:2d}: MSB values: {set(msb_vals) if msb_vals else '{0}'}, "
                  f"LSB values: {set(lsb_vals) if lsb_vals else '{0}'}")
    else:
        print("  (No bank select messages found)")

    # Program Changes
    print_section("PROGRAM CHANGES")
    if results["program_changes"]:
        # Group by channel
        by_channel = defaultdict(list)
        for pc in results["program_changes"]:
            by_channel[pc["channel"]].append(pc)

        for channel in sorted(by_channel.keys()):
            changes = by_channel[channel]
            channel_label = f"Channel {channel}"
            if any(pc["is_percussion"] for pc in changes):
                channel_label += " (Percussion)"
            print(f"\n  {channel_label}:")
            seen = set()
            for pc in changes:
                key = (pc["program"], pc["bank_msb"], pc["bank_lsb"])
                if key not in seen:
                    seen.add(key)
                    bank_info = ""
                    if pc["bank_msb"] != 0 or pc["bank_lsb"] != 0:
                        bank_info = f" [Bank {pc['bank_msb']}:{pc['bank_lsb']}]"
                    assumed = " (assumed)" if pc.get("assumed") else ""
                    name = pc.get("program_name")
                    name_str = f": {name}" if name is not None else ""
                    print(f"    Program {pc['program']:3d}{name_str}{bank_info}{assumed}")
    else:
        print("  (No program changes found)")

    # Statistics
    _print_statistics(results)

    print("\n" + "=" * 60)
    print(" END OF ANALYSIS")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="MIDI File Examiner - Analyze MIDI files and display comprehensive information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s song.mid
  %(prog)s song1.mid song2.mid song3.mid
  %(prog)s -v song.mid
  %(prog)s --json song.mid > analysis.json
        """
    )
    parser.add_argument("midi_files", nargs='+',
                        help="Path(s) to MIDI file(s) or director(ies) to analyze")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show more detailed output")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # Expand directories into individual MIDI file paths.
    expanded_paths = []
    any_error = False
    for path in args.midi_files:
        if os.path.isdir(path):
            files, warnings = collect_midi_files(path)
            for w in warnings:
                print(f"Warning: {w}", file=sys.stderr)
            if not files:
                print(f"Warning: no MIDI files found in directory: {path}", file=sys.stderr)
            expanded_paths.extend(files)
        elif os.path.isfile(path):
            expanded_paths.append(path)
        else:
            print(f"Error: path not found: {path}", file=sys.stderr)
            any_error = True

    for i, filepath in enumerate(expanded_paths):
        if i > 0 and not args.json:
            print()
        try:
            results = analyze_midi_file(filepath)
        except IOError as e:
            print(e, file=sys.stderr)
            any_error = True
            continue
        if args.json:
            import json
            print(json.dumps(results, indent=2))
        else:
            print_results(results)

    if any_error:
        sys.exit(1)


if __name__ == "__main__":
    main()
