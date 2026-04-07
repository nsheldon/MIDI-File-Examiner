# Changelog

### 1.1.0
- **Statistics section:** A new STATISTICS section at the end of the output provides per-channel and per-track analysis of MIDI data. Per-channel stats include note count, velocity range and average, note duration range and average (in ms), peak polyphony, control change message counts grouped by CC number and name, pitch bend message count and value range, channel aftertouch count and value range, and polyphonic aftertouch count. Per-track stats include total event count broken down by message type (note on/off, control change, pitch bend, program change, channel/poly aftertouch, SysEx, meta).
- **Fix: corrupt oversized delta times inflating song length:** MIDI files containing a single delta time larger than the MIDI spec maximum VLQ (0x0FFFFFFF = 268,435,455 ticks) — as seen in certain Descent 2 MIDI files — now report a correct song length. Tracks containing oversized deltas are excluded from the end-tick calculation; clean tracks determine the authoritative duration. A warning is displayed when oversized deltas are detected.
- **Fix: trailing bytes after End of Track causing load failure:** MIDI files with extra bytes appended inside a track chunk after the `FF 2F 00` End of Track marker — as seen in 7th Guest MIDI files — now load successfully. The extra bytes are stripped in memory before parsing, and a warning is displayed.

### 1.0.3
- **Directory scanning (CLI and GUI):** Accepts directories as input in addition to individual files. Directories are scanned recursively up to 3 levels deep for `.mid`/`.midi` files; a warning is generated if MIDI files exist beyond that depth. CLI accepts directory paths alongside file paths. GUI adds an **Open Folder…** button next to the existing Open button, an **Open Folder…** menu item, and accepts dragged folders — opening a folder replaces the current sidebar list. Sidebar entries from directory scans are visually indented with a `›` indicator relative to their depth from the scan root.
- **GUI sidebar `[KAR]` tag:** Files identified as Soft Karaoke format show a `[KAR]` tag in the sidebar after analysis.
- **File size in File Info:** A File Size line is displayed below the filename in the File Info section, showing KB (with raw byte count) or MB for larger files.
- **Fix: Soft Karaoke detection with variant markers:** The `@KMIDI KARAOKE FILE` marker is now matched with `startswith` rather than exact equality, handling files that append a suffix (e.g. `tm`). The version tag is correctly parsed from `@V` (not `@KV`).
- **Fix: KAR lyrics paragraph spacing:** Blank lines between paragraphs now appear after the last line of a phrase rather than before the first line, matching the intended `\` (new paragraph) / `/` (new line) semantics.
- **Fix: truncated multibyte track name decoding:** Track names whose raw bytes end with an incomplete Shift-JIS (CP932) or EUC-JP lead byte — common in fixed-width MIDI name fields — now decode correctly instead of falling back to garbled Latin-1.

### 1.0.2
- **GUI sidebar standard tags:** Each file in the sidebar is colour-coded by MIDI standard after analysis — forest green for GM, lighter forest green for GM2, Roland orange for GS, Yamaha purple for XG. A `[GM]`/`[GM2]`/`[GS]`/`[XG]` tag is appended to the filename. Files with an assumed standard (detected via bank/program messages rather than SysEx) show a `[?]` tag; files with warnings show a `[!]` tag.
- **GUI sidebar Clear button:** A Clear button at the bottom of the sidebar removes all files from the list and resets the view. The button is disabled when the list is empty.
- **CLI colour-coded MIDI Standard:** The MIDI Standard value in CLI output is colour-coded using ANSI escape codes when running in a colour-capable terminal. Supports true-color (24-bit RGB), 256-colour (nearest xterm-256 index), and basic 16-colour tiers; output is plain when piped or redirected.
- **Fix: invalid `notated_32nd_notes_per_beat` value of 0:** Files containing a time signature meta event with `notated_32nd_notes_per_beat = 0` (an invalid value per the MIDI spec) are now handled gracefully — the value is defaulted to 8 and a warning is displayed.

### 1.0.1
- **Multi-file support (CLI):** `midi_examiner.py` now accepts multiple file paths; each file is analyzed in sequence with a blank line separator between outputs. Exits with code 1 if any file failed, but continues analyzing remaining files.
- **Multi-file support (GUI):** Opening multiple files (via the file dialog, drag and drop, or command-line arguments) now adds each file to a sidebar list. Clicking a filename in the sidebar switches to that file's analysis. Files are analyzed in a queue — the next starts as soon as the previous finishes.

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
