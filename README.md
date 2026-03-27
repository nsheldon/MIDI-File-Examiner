# MIDI File Examiner

A tool for analyzing MIDI files, available as a macOS GUI app and a command-line utility. It extracts and displays comprehensive information about a file's structure, timing, metadata, and instrument usage, with support for GM, GM2, Roland GS, and Yamaha XG standards.

## Features

- **macOS GUI app** with tabbed sections for each analysis category, drag-and-drop file loading, and automatic Light/Dark mode support
- Detects the MIDI standard in use (GM, GM2, GS, XG) via SysEx messages, or assumes GM when files use only base GM banks
- Resolves program change numbers to instrument and drum kit names using an embedded patch database
- For Roland GS files, identifies the minimum Sound Canvas version required (SC-55, SC-88, SC-88Pro, or SC-8850) and flags CM-64 PCM/LA patch usage
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

## License

MIT — see [LICENSE](LICENSE).
