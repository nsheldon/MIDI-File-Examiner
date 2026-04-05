#!/usr/bin/env python3
"""
MIDI File Examiner
A comprehensive MIDI file analysis tool that extracts and displays
metadata, timing information, and message details from MIDI files.
"""

import sys
import argparse
from collections import defaultdict

try:
    import mido
except ImportError:
    print("Error: mido library is required. Install it with: pip install mido")
    sys.exit(1)

__version__ = "1.0.1"

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


def decode_midi_text(text):
    """Decode a MIDI meta-message text string to properly-encoded Unicode.

    mido decodes all meta-message text as Latin-1.  Re-encode to the original
    bytes, then try encodings in order: pure ASCII (if no high bytes), UTF-8,
    CP932 (Windows Shift-JIS, common in Japanese MIDI files), EUC-JP.
    Falls back to the original Latin-1 string if nothing else works.
    """
    try:
        raw = text.encode('latin-1')
    except (UnicodeEncodeError, AttributeError):
        return text  # already properly decoded or not a string

    # Pure ASCII — no re-encoding needed
    if all(b < 0x80 for b in raw):
        return text

    for encoding in ('utf-8', 'cp932', 'euc-jp'):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue

    return text  # fall back to Latin-1 (original mido behaviour)


def _load_midi(filepath):
    """Load a MIDI file, retrying with workarounds for known mido parse errors.

    Returns (mid, clipped, smpte_fallback) where clipped indicates note values
    were clamped and smpte_fallback indicates an invalid SMPTE frame-rate code
    was ignored during parsing.
    Raises IOError with a descriptive message if the file cannot be read.
    """
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

    for clip in (False, True):
        try:
            return _try_load(clip), clip, False
        except KeyError:
            # Likely an unrecognised SMPTE frame-rate code — retry with patch.
            try:
                return _try_load_smpte_tolerant(clip), clip, True
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
    mid, clipped, smpte_fallback = _load_midi(filepath)

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

    # File info
    results["file_info"]["filename"] = filepath
    results["file_info"]["format"] = mid.type
    results["file_info"]["num_tracks"] = len(mid.tracks)
    results["file_info"]["length_seconds"] = mid.length

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
                results["timing"]["time_signature"].append({
                    "numerator": msg.numerator,
                    "denominator": msg.denominator,
                    "clocks_per_click": msg.clocks_per_click,
                    "notated_32nd_notes_per_beat": msg.notated_32nd_notes_per_beat,
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
    # in text events.  Collect @KV version, @T titles, @L language, @I info.
    kar_version = None
    kar_titles = []
    kar_languages = []
    kar_info = []
    is_karaoke = False
    for evt in results["text_events"]:
        t = evt["text"].strip()
        if t == "@KMIDI KARAOKE FILE":
            is_karaoke = True
        elif t.startswith("@KV"):
            kar_version = t[3:].strip()
        elif t.startswith("@T"):
            kar_titles.append(t[2:].strip())
        elif t.startswith("@L"):
            kar_languages.append(t[2:].strip())
        elif t.startswith("@I"):
            kar_info.append(t[2:].strip())
    results["karaoke"] = {
        "is_karaoke": is_karaoke,
        "version": kar_version,
        "titles": kar_titles,
        "languages": kar_languages,
        "info": kar_info,
    } if is_karaoke else None

    # Post-process program changes: fix cases where a bank select arrived
    # AFTER the program change on the same channel.  Some files send the
    # program change first, then CC0/CC32.  Only apply the bank retroactively
    # if NO note-on events on that channel occurred between the program change
    # and the bank select — if notes were played first, the bank select is a
    # new instrument selection, not a correction to the earlier program change.

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
        # First bank select strictly after this program change
        future = [(t, m, l) for (t, m, l) in channel_bs_timeline[ch] if t > pc_time]
        if not future:
            continue
        bs_time, new_msb, new_lsb = future[0]
        if new_msb == 0 and new_lsb == 0:
            continue
        # If any note-on on this channel falls between the program change and
        # the bank select, the bank select belongs to a new instrument selection.
        if any(pc_time < t <= bs_time for t in channel_note_ons[ch]):
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

    return results


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

    Syllables starting with \\ begin a new paragraph (blank line before);
    syllables starting with / begin a new line within a paragraph.
    Returns a list of (is_paragraph_break, assembled_line) tuples, or an
    empty list if no line-break markers are present.
    """
    if not any(t.startswith("\\") or t.startswith("/") for t in raw_texts):
        return []
    lines = []
    current = ""
    first = True
    for text in raw_texts:
        if text.startswith("\\") or text.startswith("/"):
            if current.strip() or not first:
                lines.append((text.startswith("\\"), current.rstrip()))
            current = text[1:]
            first = False
        else:
            current += text
    if current.strip():
        lines.append((False, current.rstrip()))
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
        print(f"  MIDI Standard: {standard}{suffix}")
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
        print(f"  Key Signature: {meta['key_signature']['key']}")
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
    parser.add_argument("midi_files", nargs='+', help="Path(s) to MIDI file(s) to analyze")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show more detailed output")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    any_error = False
    for i, filepath in enumerate(args.midi_files):
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
