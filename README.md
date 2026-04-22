# MIDI File Examiner

A tool for analyzing MIDI files, available as a macOS GUI app and a command-line utility. It extracts and displays comprehensive information about a file's structure, timing, metadata, and instrument usage, with support for GM, GM2, Roland GS, and Yamaha XG standards.

## Features

- **macOS GUI app** with tabbed sections for each analysis category, drag-and-drop support for multiple files and folders, a color-coded sidebar file list with depth indentation for directory scans, a filter panel to show or hide files by standard and tag, and automatic Light/Dark mode support
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
- **Basic filtering:** filter results by MIDI standard, karaoke format, assumed-standard status, or warnings — both in the GUI sidebar and on the command line via `--filter` and `--exclude`
- **Advanced filtering:** filter on any combination of duration, MIDI format, track count, note range, velocity range, peak polyphony, key signature, timing type, time signature, tempo range, CC usage, aftertouch, text search, SysEx pattern, Roland SC version, and Yamaha XG level — GUI dialog or CLI flags
- **GUI progress bar:** status bar shows a file count progress bar during multi-file analysis

## Requirements

- Python 3.8+
- [mido](https://mido.readthedocs.io/) (`pip install mido`)
- [PyQt6](https://pypi.org/project/PyQt6/) (`pip install PyQt6`) — GUI only

## Installation

```bash
git clone https://github.com/nsheldon/MIDI-File-Examiner.git
cd MIDI-File-Examiner
python3 -m pip install -e .
```

This project now includes a `pyproject.toml`, so the folder can be installed as a standard Python project in editable mode during development.

## Usage

### GUI — macOS App Bundle

For the most convenient experience, build the native macOS app bundle once after cloning:

```bash
python3 create_app.py
midi-file-examiner-build-app
```

This generates **MIDI File Examiner.app** in the project folder. You can then:

- **Double-click** the icon in Finder to launch it
- **Drag it to the Dock** for quick access
- **Drag a `.mid` or `.midi` file onto the Dock icon** to open it directly
- **Right-click (or Control-click) any `.mid`/`.midi` file** and choose *Open With → MIDI File Examiner* from the context menu

The app automatically matches the macOS Light or Dark appearance and updates if you switch while it is running.

> **Rebuilding:** If you upgrade Python or reinstall PyQt6, run `python3 create_app.py` again to regenerate the launcher with the correct interpreter path.

### GUI — Command Line

```bash
python3 midi_examiner_gui.py
python3 midi_examiner_gui.py song.mid   # open a file directly on launch
midi-file-examiner-gui
```

Drag and drop `.mid` or `.midi` files and folders onto the window to analyze them.

The **Filter** panel above the sidebar lets you narrow the file list without reloading:

- **Standard checkboxes** (GM, GM2, GS, XG, Unknown) — check any combination to show files matching any of those standards (OR logic); leave all unchecked to show every standard.
- **Modifier checkboxes** ([?], [!], KAR) — tri-state: one click = show only files with that tag; a second click = hide files with that tag (shown as –); a third click = off.
- **Reset button** — clears all standard checkboxes, modifier checkboxes, and advanced filters in one click.
- **Advanced… button** — opens the Advanced Filter dialog. The button label shows a dot (●) when advanced filters are active.

#### Advanced Filter dialog

The dialog is organized into four sections:

| Section | Controls |
|---------|----------|
| **File Info** | Min/max duration, MIDI format type (Type 0/1/2), min/max track count, Roland SC version requirement (SC-55/SC-88/SC-88Pro/SC-8850), Yamaha XG level (Level 1/2/3) |
| **Notes & Velocity** | Min/max note range, min/max velocity range, min/max peak polyphony, key signature (multi-select, OR logic) |
| **Timing & Events** | Timing type (PPQ/SMPTE), time signature, min/max tempo, CC numbers (all must be present), polyphonic aftertouch, channel aftertouch |
| **Search** | Case-insensitive text substring (searches all text events, track names, instrument names, patch names, metadata), SysEx hex pattern |

Selecting a Roland SC version automatically checks the GS standard checkbox; selecting an XG level automatically checks XG. Unchecking GS or XG clears the corresponding sub-filters. Leave all fields at their default (—) to apply no constraint for that property.

### Command Line

```bash
python midi_examiner.py <midi_file>
python midi_examiner.py --json <midi_file>
python midi_examiner.py --json <midi_file> > analysis.json
midi-file-examiner <midi_file>
```

### Command-Line Options

| Option | Description |
|--------|-------------|
| `midi_file` | Path to the MIDI file(s) or folder(s) to analyze |
| `-v`, `--verbose` | Show more detailed output |
| `--json` | Output results as JSON instead of formatted text |
| `--filter TAG` | Show only files matching this tag (repeatable). Standard tags — `GM`, `GM2`, `GS`, `XG`, `unknown` — are OR'd together; modifier tags — `KAR`, `assumed`, `warnings` — are AND'd. |
| `--exclude TAG` | Hide files matching this tag (repeatable). Valid tags are the same as `--filter`. |
| `--paths-only` | Print only matching file paths, one per line — useful for piping to other tools. Cannot be combined with `--json`. |
| `--version` | Show the version number and exit |

**Advanced filter options:**

| Option | Description |
|--------|-------------|
| `--min-duration S` | Show only files at least S seconds long (M:SS and H:MM:SS also accepted) |
| `--max-duration S` | Show only files at most S seconds long |
| `--format TYPE` | Show only files of MIDI format type 0, 1, or 2 |
| `--timing-type TYPE` | Show only files using `PPQ` or `SMPTE` timing |
| `--time-sig N/D` | Show only files containing this time signature (e.g. `4/4`, `6/8`) |
| `--key-sig KEY` | Show only files with this key signature (e.g. `C`, `Am`, `F#m`); may be repeated for OR logic |
| `--min-tracks N` | Show only files with at least N tracks |
| `--max-tracks N` | Show only files with at most N tracks |
| `--min-note NOTE` | Show only files whose lowest note >= NOTE (MIDI 0–127 or name, e.g. `C4`) |
| `--max-note NOTE` | Show only files whose highest note <= NOTE |
| `--min-velocity N` | Show only files whose minimum note velocity >= N (1–127) |
| `--max-velocity N` | Show only files whose maximum note velocity <= N |
| `--min-polyphony N` | Show only files with peak polyphony >= N |
| `--max-polyphony N` | Show only files with peak polyphony <= N |
| `--min-tempo BPM` | Show only files whose tempo range reaches at least BPM |
| `--max-tempo BPM` | Show only files whose tempo range includes at most BPM |
| `--has-cc CC` | Show only files that use CC number CC (0–127); may be repeated — all listed CCs must be present |
| `--has-poly-aftertouch` | Show only files that use polyphonic aftertouch |
| `--no-poly-aftertouch` | Show only files that do NOT use polyphonic aftertouch |
| `--has-channel-aftertouch` | Show only files that use channel aftertouch |
| `--no-channel-aftertouch` | Show only files that do NOT use channel aftertouch |
| `--search TEXT` | Show only files containing TEXT in any text event, track name, instrument name, patch name, or metadata (case-insensitive substring) |
| `--has-sysex HEX` | Show only files containing a SysEx message that includes these bytes (space-separated hex, e.g. `F0 41 10`) |
| `--sc-version VERSION` | Show only GS files requiring this minimum SC version; may be repeated for OR logic (choices: `SC-55`, `SC-88`, `SC-88Pro`, `SC-8850`) |
| `--xg-level LEVEL` | Show only XG files requiring this minimum XG level; may be repeated for OR logic (choices: `1`, `2`, `3`) |

**Filter examples:**

```bash
# Show only GS files
python midi_examiner.py --filter GS /path/to/folder/

# Show GM or GS files (OR logic for standard tags)
python midi_examiner.py --filter GM --filter GS /path/to/folder/

# Show GS files that also have an assumed standard (AND logic for modifier tags)
python midi_examiner.py --filter GS --filter assumed /path/to/folder/

# Hide files with assumed standard or warnings
python midi_examiner.py --exclude assumed --exclude warnings /path/to/folder/

# Pipe matching paths to another tool
python midi_examiner.py --filter GS --paths-only /path/to/folder/ | xargs some_tool

# Show only files longer than 3 minutes in 3/4 time
python midi_examiner.py --min-duration 3:00 --time-sig 3/4 /path/to/folder/

# Show GS files requiring at least SC-88
python midi_examiner.py --filter GS --sc-version SC-88 --sc-version SC-88Pro --sc-version SC-8850 /path/to/folder/

# Show files in C major or A minor that use CC 64 (sustain pedal)
python midi_examiner.py --key-sig C --key-sig Am --has-cc 64 /path/to/folder/
```

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
