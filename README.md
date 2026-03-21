# MIDI File Examiner

A command-line tool for analyzing MIDI files. It extracts and displays comprehensive information about a file's structure, timing, metadata, and instrument usage, with support for GM, GM2, Roland GS, and Yamaha XG standards.

## Features

- Detects the MIDI standard in use (GM, GM2, GS, XG) via SysEx messages, or assumes GM when files use only base GM banks
- Resolves program change numbers to instrument and drum kit names using an embedded patch database
- For Roland GS files, identifies the minimum Sound Canvas version required (SC-55, SC-88, SC-88Pro, or SC-8850) and flags CM-64 PCM/LA patch usage
- Reports tempo and time signature changes with measure/beat positions
- Lists SysEx, bank select, program change, text, marker, cue point, and lyric events
- Outputs results as human-readable text or JSON

## Requirements

- Python 3.6+
- [mido](https://mido.readthedocs.io/) (`pip install mido`)

## Installation

```bash
git clone https://github.com/nsheldon/MIDI-File-Examiner.git
cd MIDI-File-Examiner
pip install -r requirements.txt
```

## Usage

```bash
python midi_examiner.py <midi_file>
python midi_examiner.py --json <midi_file>
python midi_examiner.py --json <midi_file> > analysis.json
```

### Options

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
