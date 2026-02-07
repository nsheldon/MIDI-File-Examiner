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


def analyze_midi_file(filepath):
    """Analyze a MIDI file and return structured data."""
    try:
        mid = mido.MidiFile(filepath)
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
    }

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

    # Track detected MIDI standard (GM, GM2, GS, XG)
    detected_standard = None

    # Process each track
    for track_idx, track in enumerate(mid.tracks):
        track_info = {
            "index": track_idx,
            "name": None,
            "events": 0
        }

        for msg in track:
            track_info["events"] += 1

            # Meta messages
            if msg.type == 'track_name':
                track_info["name"] = msg.name
                if track_idx == 0:
                    results["metadata"]["sequence_name"] = msg.name

            elif msg.type == 'copyright':
                results["metadata"]["copyright"] = msg.text

            elif msg.type == 'text':
                results["text_events"].append({
                    "track": track_idx,
                    "text": msg.text,
                    "time": msg.time
                })

            elif msg.type == 'marker':
                results["markers"].append({
                    "track": track_idx,
                    "marker": msg.text,
                    "time": msg.time
                })

            elif msg.type == 'cue_marker':
                results["cue_points"].append({
                    "track": track_idx,
                    "cue": msg.text,
                    "time": msg.time
                })

            elif msg.type == 'set_tempo':
                if "tempo" not in results["timing"]:
                    results["timing"]["tempo"] = []
                bpm = mido.tempo2bpm(msg.tempo)
                results["timing"]["tempo"].append({
                    "microseconds_per_beat": msg.tempo,
                    "bpm": round(bpm, 2),
                    "time": msg.time
                })

            elif msg.type == 'time_signature':
                if "time_signature" not in results["timing"]:
                    results["timing"]["time_signature"] = []
                results["timing"]["time_signature"].append({
                    "numerator": msg.numerator,
                    "denominator": msg.denominator,
                    "clocks_per_click": msg.clocks_per_click,
                    "notated_32nd_notes_per_beat": msg.notated_32nd_notes_per_beat,
                    "time": msg.time
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
                    "name": msg.name
                })

            elif msg.type == 'lyrics':
                if "lyrics" not in results["metadata"]:
                    results["metadata"]["lyrics"] = []
                results["metadata"]["lyrics"].append({
                    "track": track_idx,
                    "text": msg.text,
                    "time": msg.time
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

            # Control changes (Bank Select)
            elif msg.type == 'control_change':
                if msg.control == 0:  # Bank Select MSB
                    channel_banks[msg.channel]["msb"] = msg.value
                    results["bank_selects"].append({
                        "track": track_idx,
                        "channel": msg.channel + 1,
                        "type": "MSB",
                        "value": msg.value,
                        "time": msg.time
                    })
                elif msg.control == 32:  # Bank Select LSB
                    channel_banks[msg.channel]["lsb"] = msg.value
                    results["bank_selects"].append({
                        "track": track_idx,
                        "channel": msg.channel + 1,
                        "type": "LSB",
                        "value": msg.value,
                        "time": msg.time
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
                    "time": msg.time
                })

        results["tracks"].append(track_info)

    # Store detected MIDI standard
    results["detected_standard"] = detected_standard

    return results


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

    if "tempo" in timing and timing["tempo"]:
        print_subsection("Tempo Changes")
        for i, tempo in enumerate(timing["tempo"]):
            if i == 0:
                print(f"  Initial:       {tempo['bpm']} BPM ({tempo['microseconds_per_beat']} \u00b5s/beat)")
            else:
                print(f"  Change {i}:      {tempo['bpm']} BPM at tick {tempo['time']}")

    if "time_signature" in timing and timing["time_signature"]:
        print_subsection("Time Signature(s)")
        for i, ts in enumerate(timing["time_signature"]):
            sig = f"{ts['numerator']}/{ts['denominator']}"
            if i == 0:
                print(f"  Initial:       {sig}")
            else:
                print(f"  Change {i}:      {sig} at tick {ts['time']}")
            print(f"                 ({ts['clocks_per_click']} MIDI clocks/click, "
                  f"{ts['notated_32nd_notes_per_beat']} 32nd notes/beat)")

    if "smpte_offset" in timing:
        print_subsection("SMPTE Offset")
        print(f"  Offset:        {timing['smpte_offset']['formatted']}")

    # Metadata
    print_section("METADATA")
    meta = results["metadata"]

    if "sequence_name" in meta:
        print(f"  Song Title:    {meta['sequence_name']}")
    if "copyright" in meta:
        print(f"  Copyright:     {meta['copyright']}")
    if "key_signature" in meta:
        print(f"  Key Signature: {meta['key_signature']['key']}")
    if "instruments" in meta:
        print_subsection("Instrument Names")
        for inst in meta["instruments"]:
            print(f"    Track {inst['track']}: {inst['name']}")

    if not any(key in meta for key in ["sequence_name", "copyright", "key_signature", "instruments"]):
        print("  (No metadata found)")

    # Track Information
    print_section("TRACK INFORMATION")
    for track in results["tracks"]:
        name = track["name"] if track["name"] else "(unnamed)"
        print(f"  Track {track['index']:2d}: {name} ({track['events']} events)")

    # Text Events
    if results["text_events"]:
        print_section("TEXT EVENTS")
        for evt in results["text_events"][:20]:  # Limit to first 20
            print(f"  Track {evt['track']}: \"{evt['text']}\"")
        if len(results["text_events"]) > 20:
            print(f"  ... and {len(results['text_events']) - 20} more text events")

    # Markers
    if results["markers"]:
        print_section("MARKERS")
        for marker in results["markers"]:
            print(f"  Track {marker['track']}: \"{marker['marker']}\" (tick {marker['time']})")

    # Cue Points
    if results["cue_points"]:
        print_section("CUE POINTS")
        for cue in results["cue_points"]:
            print(f"  Track {cue['track']}: \"{cue['cue']}\" (tick {cue['time']})")

    # Lyrics
    if "lyrics" in results["metadata"] and results["metadata"]["lyrics"]:
        print_section("LYRICS")
        for lyric in results["metadata"]["lyrics"][:20]:
            print(f"  \"{lyric['text']}\"")
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
            for msg in other_messages[:10]:
                print(f"  Track {msg['track']}: {msg['description']}")
                print(f"    Data: F0 {msg['data_hex']} F7")
            if len(other_messages) > 10:
                print(f"  ... and {len(other_messages) - 10} more SysEx messages")

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
            # Label channel 10 as percussion
            channel_label = f"Channel {channel}"
            if channel == 10:
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
