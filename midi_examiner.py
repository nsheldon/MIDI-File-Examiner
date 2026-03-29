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

__version__ = "1.0.0-beta.9"

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
            # Find the minimum bank_lsb that has this drum kit
            cursor.execute("""
                SELECT MIN(bank_lsb) FROM percussion_sets
                WHERE standard = 'GS' AND bank_msb = 0 AND program = ?
            """, (program,))
        else:
            # Find the minimum bank_lsb that has this (msb, program) combo
            cursor.execute("""
                SELECT MIN(bank_lsb) FROM patches
                WHERE standard = 'GS' AND bank_msb = ? AND program = ?
            """, (msb, program))

        row = cursor.fetchone()
        if row and row[0] is not None:
            min_lsb = row[0]
            if min_lsb > max_generation:
                max_generation = min_lsb

    conn.close()

    return {
        "minimum_sc_version": SC_GENERATIONS.get(max_generation, f"Unknown ({max_generation})"),
        "minimum_sc_generation": max_generation,
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


def analyze_midi_file(filepath):
    """Analyze a MIDI file and return structured data."""
    clipped = False
    try:
        mid = mido.MidiFile(filepath)
    except Exception:
        try:
            mid = mido.MidiFile(filepath, clip=True)
            clipped = True
        except Exception as e:
            print(f"Error opening MIDI file: {e}")
            sys.exit(1)

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
    if detected_standard is None:
        all_gm_banks = all(
            bs["value"] == 0
            for bs in results["bank_selects"]
        )
        if all_gm_banks:  # True even when bank_selects is empty
            detected_standard = "GM"
            standard_assumed = True
            standard_assumed_reason = "no reset SysEx found; all bank selects use GM values"
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
            detected_standard = "GM2"
            # Collect the non-GM percussion programs that triggered the upgrade
            non_gm_kits = sorted({
                pc["program"]
                for pc in results["program_changes"]
                if pc["is_percussion"] and pc["program"] != 0
            })
            kit_list = ", ".join(str(p) for p in non_gm_kits)
            noun = "program" if len(non_gm_kits) == 1 else "programs"
            standard_assumed_reason = (
                f"no reset SysEx found; non-GM percussion {noun} on channel 10: {kit_list}"
            )

    # Store detected MIDI standard
    results["detected_standard"] = detected_standard
    results["standard_assumed"] = standard_assumed
    results["standard_assumed_reason"] = standard_assumed_reason
    results["standard_unknown_reason"] = standard_unknown_reason

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
    for pc in results["program_changes"]:
        pc["program_name"] = get_instrument_name(
            pc["program"], pc["channel"],
            pc["bank_msb"], pc["bank_lsb"],
            detected_standard
        )

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
        if assumed:
            reason = results.get("standard_assumed_reason") or "no reset SysEx found"
            suffix = f" (assumed — {reason})"
        else:
            suffix = " (detected via SysEx)"
        print(f"  MIDI Standard: {standard}{suffix}")
    else:
        reason = results.get("standard_unknown_reason")
        if reason:
            print(f"  MIDI Standard: Unknown ({reason})")

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

    # Lyrics
    if "lyrics" in results["metadata"] and results["metadata"]["lyrics"]:
        print_section("LYRICS")
        for lyric in results["metadata"]["lyrics"][:20]:
            print(f"  \"{sanitize_text(lyric['text'])}\"")
        if len(results["metadata"]["lyrics"]) > 20:
            print(f"  ... and {len(results['metadata']['lyrics']) - 20} more lyrics")

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

        # GS version requirements
        if "gs_info" in results:
            gs = results["gs_info"]
            print_subsection("Roland GS Requirements")
            print(f"  Minimum SC version:   {gs['minimum_sc_version']}")
            if gs["uses_cm64_pcm"]:
                print(f"  CM-64 PCM patches:    Yes (MSB 126)")
            if gs["uses_cm64_la"]:
                print(f"  CM-64 LA patches:     Yes (MSB 127)")
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
                    print(f"    Program {pc['program']:3d}: {pc['program_name']}{bank_info}")
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
  %(prog)s -v song.mid
  %(prog)s --json song.mid > analysis.json
        """
    )
    parser.add_argument("midi_file", help="Path to the MIDI file to analyze")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show more detailed output")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    # Analyze the file
    results = analyze_midi_file(args.midi_file)

    # Output results
    if args.json:
        import json
        print(json.dumps(results, indent=2))
    else:
        print_results(results)


if __name__ == "__main__":
    main()
