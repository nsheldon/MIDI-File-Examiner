# MIDI File Examiner

A tool for analyzing MIDI files, available as a macOS GUI app and a command-line utility. It extracts and displays comprehensive information about a file's structure, timing, metadata, and instrument usage, with support for GM, GM2, Roland GS, and Yamaha XG standards.

## Features

- **macOS GUI app** with tabbed sections for each analysis category, drag-and-drop support for multiple files and folders, a colour-coded sidebar file list with depth indentation for directory scans, and automatic Light/Dark mode support
- Detects the MIDI standard in use (GM, GM2, GS, XG) via SysEx messages, assumes GM when files use only base GM banks or program changes, or reports Unknown when no standard evidence is present
- Resolves program change numbers to instrument and drum kit names using an embedded patch database
- For Roland GS files, identifies the minimum Sound Canvas version required (SC-55, SC-88, SC-88Pro, or SC-8850) and flags CM-64 PCM/LA patch usage
- For Yamaha XG files, identifies the minimum XG level required (Level 1 / MU50/MU80/MU90, Level 2 / MU100, or Level 3 / MU128)
- Detects **Soft Karaoke (KAR) format** files and displays title, language, version, and info metadata in the File Info section
- Assembles karaoke lyrics into readable lines using KMIDI `\` / `/` line-break conventions, whether lyrics are stored as MIDI lyrics events or text events; groups non-karaoke lyrics by measure for readability
- For GM/GM2 files, shows channels with note activity but no program change as using Program 0 (marked "assumed")
- Reports tempo and time signature changes with measure/beat positions
- Lists SysEx, bank select, program change, text, marker, cue point, and lyric events
- Outputs results as human-readable text or JSON (command-line)

## Requirements

- Python 3.6+
- [mido](https://mido.readthedocs.io/) (`pip install mido`)
- [PyQt6](https://pypi.org/project/PyQt6/) (`pip install PyQt6`) — GUI only

## Installation

```bash
git clone https://github.com/nsheldon/MIDI-File-Examiner.git
cd MIDI-File-Examiner
pip install -r requirements.txt
```

## Usage

### GUI — macOS App Bundle

For the most convenient experience, build the native macOS app bundle once after cloning:

```bash
python3 create_app.py
```

This generates **MIDI File Examiner.app** in the project folder. You can then:

- **Double-click** the icon in Finder to launch it
- **Drag it to the Dock** for quick access
- **Drag a `.mid` or `.midi` file onto the Dock icon** to open it directly
- **Double-click any `.mid`/`.midi` file** and choose *Open With → MIDI File Examiner* from the context menu

The app automatically matches the macOS Light or Dark appearance and updates if you switch while it is running.

> **Rebuilding:** If you upgrade Python or reinstall PyQt6, run `python3 create_app.py` again to regenerate the launcher with the correct interpreter path.

### GUI — Command Line

```bash
python3 midi_examiner_gui.py
python3 midi_examiner_gui.py song.mid   # open a file directly on launch
```

Drag and drop a `.mid` or `.midi` file onto the window to analyze it.

### Command Line

```bash
python midi_examiner.py <midi_file>
python midi_examiner.py --json <midi_file>
python midi_examiner.py --json <midi_file> > analysis.json
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `midi_file` | Path to the MIDI file to analyze |
| `-v`, `--verbose` | Show more detailed output |
| `--json` | Output results as JSON instead of formatted text |
| `--version` | Show the version number and exit |

## Example Output

```
============================================================
 FILE INFORMATION
============================================================
  Filename:      song.mid
  Format:        Multi Track (Type 1)
  Tracks:        20
  Length:        4:02.44
  MIDI Standard: GS (detected via SysEx)
  Roland SC Req:  SC-8850 (uses SC-8850-exclusive patch(es): Ambient BPF, Dist Rtm GTR, Double Pick (+1 more))

============================================================
 TIMING INFORMATION
============================================================
  Timing Type:   PPQ (Pulses Per Quarter Note)
  PPQN:          48 ticks per quarter note

--- Tempo Changes ---
  Initial:       126.0 BPM (476190 µs/beat)

--- Time Signature(s) ---
  Initial:       4/4
                 (24 MIDI clocks/click, 8 32nd notes/beat)

============================================================
 METADATA
============================================================
  Song Title:    Song Title Here
  Copyright:     Original Composer (Arranger)
  Key Signature: Em

============================================================
 TRACK INFORMATION
============================================================
  Track  0: Song Title Here (72 events)
  Track  1: Lead Guitar (2409 events)
  Track  2: Rhythm Guitar (1575 events)
  ...

============================================================
 TEXT EVENTS
============================================================
  Track 0: "Arranged for Roland SC-8850" at measure 1, beat 1 (tick 0)
  Track 0: "Start of Setup" at measure 1, beat 1.24 (tick 24)
  Track 0: "End of Setup" at measure 2, beat 1.22 (tick 214)

============================================================
 SYSTEM EXCLUSIVE (SYSEX) MESSAGES
============================================================

--- Roland GS ---
  GS SysEx
    Data: F0 41 10 42 12 00 00 7F 00 01 F7
  GS SysEx
    Data: F0 41 10 42 12 40 01 30 03 0C F7
  ...

--- SysEx Summary ---
  Total SysEx messages: 52
  GM/GM2 detected:      No
  Roland GS detected:   Yes
  Yamaha XG detected:   No

============================================================
 BANK SELECT MESSAGES
============================================================
  Channel  1: MSB values: {1}, LSB values: {4}
  Channel  2: MSB values: {26}, LSB values: {4}
  Channel  3: MSB values: {16}, LSB values: {0}
  ...

============================================================
 PROGRAM CHANGES
============================================================

  Channel 1:
    Program  30: Dist. Gt2 [Bank 1:4]

  Channel 2:
    Program  30: Dist Rtm GTR [Bank 26:4]

  Channel 3:
    Program  30: PowerGuitar [Bank 16:0]

  Channel 10 (Percussion):
    Program   0: STANDARD 1 [Bank 0:4]

  ...

============================================================
 END OF ANALYSIS
============================================================
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## License

MIT — see [LICENSE](LICENSE).
