# MIDI File Examiner

A tool for analyzing MIDI files, available as a macOS GUI app and a command-line utility. It extracts and displays comprehensive information about a file's structure, timing, metadata, and instrument usage, with support for GM, GM2, Roland GS, and Yamaha XG standards.

## Features

- **macOS GUI app** with tabbed sections for each analysis category, drag-and-drop file loading, and automatic Light/Dark mode support
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
  Tracks:        5
  Length:        3:42.00
  MIDI Standard: GS (detected via SysEx)

============================================================
 PROGRAM CHANGES
============================================================

  Channel  1:
    Program  25: Steel-str.Gt [Bank 0:0]

  Channel 10 (Percussion):
    Program   0: STANDARD
```

## Changelog

### 1.0.0
- **Unknown MIDI standard detection:** Files with no SysEx reset, no bank select messages, and no program change messages are now reported as `Unknown` rather than being incorrectly assumed to be GM
- **Program name suppression for unknown standard:** When the MIDI standard cannot be determined, the Program Changes section lists program numbers without resolving them against the patch database
- **Measure-grouped lyrics display:** Non-karaoke MIDI files with lyrics events (but no KMIDI line-break markers) now display lyrics grouped by measure — syllables within the same measure are joined into a single line with hyphens respected as word-continuation markers
- **Tolerant SMPTE Offset parsing:** Files containing a SMPTE Offset meta event (0xFF 0x54) with an out-of-spec frame-rate code (e.g. code 6) are now parsed successfully; a warning is displayed noting that the frame rate was unrecognised and defaulted to 24 fps
- **Improved error handling:** File open errors are now reported with descriptive messages; the GUI displays errors in an Error tab rather than terminating the process

### 1.0.0-beta.13
- **Soft Karaoke (KAR) detection:** Identifies files using the Soft Karaoke format via the `@KMIDI KARAOKE FILE` text event marker; displays format name, version (`@KV`), title (`@T`), language (`@L`), and info (`@I`) lines in the File Info section
- **Assembled lyrics display:** The Lyrics section now assembles raw syllables into readable lines using KMIDI `\` (paragraph break) and `/` (line break) conventions rather than listing each syllable individually; all lyrics are shown with no entry limit
- **Lyrics from text events:** Karaoke files that store lyrics exclusively as text events (rather than MIDI lyrics events) now produce a `LYRICS (FROM TEXT EVENTS)` section with the same assembled display; non-lyric text events from other tracks are excluded
- **GM/GM2 assumed program:** Channels with note-on activity but no program change message are shown in the Program Changes section as using Program 0, marked `(assumed)`, for GM and GM2 files
- **GM2 upgrade detection reason:** When a file uses a GM SysEx reset but is upgraded to GM2 due to GM2-only percussion programs, the MIDI Standard line now reads `GM2 (GM detected via SysEx; GM2-only percussion program on channel 10: N)` instead of the misleading `detected via SysEx`
- **XG bank/program reason formatting:** Voice names in the Yamaha XG Req reason string now use `Bank MSB:LSB Pgm N` format, consistent with the Program Changes section

### 1.0.0-beta.12
- Added Yamaha XG Level detection: identifies minimum required XG hardware (Level 1 / MU50/MU80/MU90, Level 2 / MU100, Level 3 / MU128) based on voices and drum kits used
- Added XG voice database: 150 melodic patches and 38 drum kits with per-voice minimum level (1–3) sourced from the XG Format Guide, MU100, and MU128 voice lists
- Added `Yamaha XG Req:` line in File Info section for XG files, showing the minimum required device and the voices that triggered the requirement

### 1.0.0-beta.11
- Bumped version

### 1.0.0-beta.10
- Bumped version

### 1.0.0-beta.9
- Fixed bank select applied after program change showing wrong instrument name

### 1.0.0-beta.8 and earlier
- See git history

## License

MIT — see [LICENSE](LICENSE).
