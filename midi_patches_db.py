#!/usr/bin/env python3
"""
MIDI Patches Database Module

Provides SQLite-based storage and retrieval of MIDI patch names and
percussion sets across GM, GM2, GS, and XG standards.
"""

import sqlite3
import csv
import os

# Paths - same directory as this module
_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_MODULE_DIR, "midi_patches.db")
GS_INSTRUMENTS_CSV = os.path.join(_MODULE_DIR, "gs_instruments.csv")
GS_DRUMKITS_CSV = os.path.join(_MODULE_DIR, "gs_drumkits.csv")

# GM instrument names (0-127)
GM_INSTRUMENTS = [
    # Piano (0-7)
    ("Acoustic Grand Piano", "Piano"),
    ("Bright Acoustic Piano", "Piano"),
    ("Electric Grand Piano", "Piano"),
    ("Honky-tonk Piano", "Piano"),
    ("Electric Piano 1", "Piano"),
    ("Electric Piano 2", "Piano"),
    ("Harpsichord", "Piano"),
    ("Clavinet", "Piano"),
    # Chromatic Percussion (8-15)
    ("Celesta", "Chromatic Percussion"),
    ("Glockenspiel", "Chromatic Percussion"),
    ("Music Box", "Chromatic Percussion"),
    ("Vibraphone", "Chromatic Percussion"),
    ("Marimba", "Chromatic Percussion"),
    ("Xylophone", "Chromatic Percussion"),
    ("Tubular Bells", "Chromatic Percussion"),
    ("Dulcimer", "Chromatic Percussion"),
    # Organ (16-23)
    ("Drawbar Organ", "Organ"),
    ("Percussive Organ", "Organ"),
    ("Rock Organ", "Organ"),
    ("Church Organ", "Organ"),
    ("Reed Organ", "Organ"),
    ("Accordion", "Organ"),
    ("Harmonica", "Organ"),
    ("Tango Accordion", "Organ"),
    # Guitar (24-31)
    ("Acoustic Guitar (nylon)", "Guitar"),
    ("Acoustic Guitar (steel)", "Guitar"),
    ("Electric Guitar (jazz)", "Guitar"),
    ("Electric Guitar (clean)", "Guitar"),
    ("Electric Guitar (muted)", "Guitar"),
    ("Overdriven Guitar", "Guitar"),
    ("Distortion Guitar", "Guitar"),
    ("Guitar Harmonics", "Guitar"),
    # Bass (32-39)
    ("Acoustic Bass", "Bass"),
    ("Electric Bass (finger)", "Bass"),
    ("Electric Bass (pick)", "Bass"),
    ("Fretless Bass", "Bass"),
    ("Slap Bass 1", "Bass"),
    ("Slap Bass 2", "Bass"),
    ("Synth Bass 1", "Bass"),
    ("Synth Bass 2", "Bass"),
    # Strings (40-47)
    ("Violin", "Strings"),
    ("Viola", "Strings"),
    ("Cello", "Strings"),
    ("Contrabass", "Strings"),
    ("Tremolo Strings", "Strings"),
    ("Pizzicato Strings", "Strings"),
    ("Orchestral Harp", "Strings"),
    ("Timpani", "Strings"),
    # Ensemble (48-55)
    ("String Ensemble 1", "Ensemble"),
    ("String Ensemble 2", "Ensemble"),
    ("Synth Strings 1", "Ensemble"),
    ("Synth Strings 2", "Ensemble"),
    ("Choir Aahs", "Ensemble"),
    ("Voice Oohs", "Ensemble"),
    ("Synth Voice", "Ensemble"),
    ("Orchestra Hit", "Ensemble"),
    # Brass (56-63)
    ("Trumpet", "Brass"),
    ("Trombone", "Brass"),
    ("Tuba", "Brass"),
    ("Muted Trumpet", "Brass"),
    ("French Horn", "Brass"),
    ("Brass Section", "Brass"),
    ("Synth Brass 1", "Brass"),
    ("Synth Brass 2", "Brass"),
    # Reed (64-71)
    ("Soprano Sax", "Reed"),
    ("Alto Sax", "Reed"),
    ("Tenor Sax", "Reed"),
    ("Baritone Sax", "Reed"),
    ("Oboe", "Reed"),
    ("English Horn", "Reed"),
    ("Bassoon", "Reed"),
    ("Clarinet", "Reed"),
    # Pipe (72-79)
    ("Piccolo", "Pipe"),
    ("Flute", "Pipe"),
    ("Recorder", "Pipe"),
    ("Pan Flute", "Pipe"),
    ("Blown Bottle", "Pipe"),
    ("Shakuhachi", "Pipe"),
    ("Whistle", "Pipe"),
    ("Ocarina", "Pipe"),
    # Synth Lead (80-87)
    ("Lead 1 (square)", "Synth Lead"),
    ("Lead 2 (sawtooth)", "Synth Lead"),
    ("Lead 3 (calliope)", "Synth Lead"),
    ("Lead 4 (chiff)", "Synth Lead"),
    ("Lead 5 (charang)", "Synth Lead"),
    ("Lead 6 (voice)", "Synth Lead"),
    ("Lead 7 (fifths)", "Synth Lead"),
    ("Lead 8 (bass + lead)", "Synth Lead"),
    # Synth Pad (88-95)
    ("Pad 1 (new age)", "Synth Pad"),
    ("Pad 2 (warm)", "Synth Pad"),
    ("Pad 3 (polysynth)", "Synth Pad"),
    ("Pad 4 (choir)", "Synth Pad"),
    ("Pad 5 (bowed)", "Synth Pad"),
    ("Pad 6 (metallic)", "Synth Pad"),
    ("Pad 7 (halo)", "Synth Pad"),
    ("Pad 8 (sweep)", "Synth Pad"),
    # Synth Effects (96-103)
    ("FX 1 (rain)", "Synth Effects"),
    ("FX 2 (soundtrack)", "Synth Effects"),
    ("FX 3 (crystal)", "Synth Effects"),
    ("FX 4 (atmosphere)", "Synth Effects"),
    ("FX 5 (brightness)", "Synth Effects"),
    ("FX 6 (goblins)", "Synth Effects"),
    ("FX 7 (echoes)", "Synth Effects"),
    ("FX 8 (sci-fi)", "Synth Effects"),
    # Ethnic (104-111)
    ("Sitar", "Ethnic"),
    ("Banjo", "Ethnic"),
    ("Shamisen", "Ethnic"),
    ("Koto", "Ethnic"),
    ("Kalimba", "Ethnic"),
    ("Bagpipe", "Ethnic"),
    ("Fiddle", "Ethnic"),
    ("Shanai", "Ethnic"),
    # Percussive (112-119)
    ("Tinkle Bell", "Percussive"),
    ("Agogo", "Percussive"),
    ("Steel Drums", "Percussive"),
    ("Woodblock", "Percussive"),
    ("Taiko Drum", "Percussive"),
    ("Melodic Tom", "Percussive"),
    ("Synth Drum", "Percussive"),
    ("Reverse Cymbal", "Percussive"),
    # Sound Effects (120-127)
    ("Guitar Fret Noise", "Sound Effects"),
    ("Breath Noise", "Sound Effects"),
    ("Seashore", "Sound Effects"),
    ("Bird Tweet", "Sound Effects"),
    ("Telephone Ring", "Sound Effects"),
    ("Helicopter", "Sound Effects"),
    ("Applause", "Sound Effects"),
    ("Gunshot", "Sound Effects"),
]

# GM2 variation patches (Bank MSB=0, LSB=1+)
# Format: (program, lsb, name, category)
GM2_VARIATIONS = [
    # Piano variations
    (0, 1, "Wide Acoustic Grand", "Piano"),
    (0, 2, "Dark Acoustic Grand", "Piano"),
    (1, 1, "Wide Bright Acoustic", "Piano"),
    (2, 1, "Wide Electric Grand", "Piano"),
    (3, 1, "Wide Honky-tonk", "Piano"),
    (4, 1, "Detuned EP 1", "Piano"),
    (4, 2, "EP 1 Velocity Mix", "Piano"),
    (4, 3, "60's EP", "Piano"),
    (5, 1, "Detuned EP 2", "Piano"),
    (5, 2, "EP 2 Velocity Mix", "Piano"),
    (5, 3, "EP Legend", "Piano"),
    (5, 4, "EP Phase", "Piano"),
    (6, 1, "Coupled Harpsichord", "Piano"),
    (7, 1, "Pulse Clavinet", "Piano"),
    # Chromatic Percussion variations
    (8, 1, "Wet Celesta", "Chromatic Percussion"),
    (9, 1, "Wet Glockenspiel", "Chromatic Percussion"),
    (12, 1, "Wide Marimba", "Chromatic Percussion"),
    (14, 1, "Church Bells", "Chromatic Percussion"),
    (14, 2, "Carillon", "Chromatic Percussion"),
    # Organ variations
    (16, 1, "Detuned Drawbar Organ", "Organ"),
    (16, 2, "60's Drawbar Organ", "Organ"),
    (16, 3, "Drawbar Organ 2", "Organ"),
    (17, 1, "Detuned Perc Organ", "Organ"),
    (17, 2, "Perc Organ 2", "Organ"),
    (18, 1, "Rock Organ 2", "Organ"),
    (19, 1, "Church Organ 2", "Organ"),
    (19, 2, "Church Organ 3", "Organ"),
    (21, 1, "Italian Accordion", "Organ"),
    # Guitar variations
    (24, 1, "Ukulele", "Guitar"),
    (25, 1, "12-String Guitar", "Guitar"),
    (25, 2, "Mandolin", "Guitar"),
    (26, 1, "Hawaiian Guitar", "Guitar"),
    (28, 1, "Funk Guitar", "Guitar"),
    (28, 2, "Funk Guitar 2", "Guitar"),
    (30, 1, "Feedback Guitar", "Guitar"),
    (30, 2, "Distortion Rtm Guitar", "Guitar"),
    # Bass variations
    (32, 1, "Jazz Bass", "Bass"),
    (33, 1, "Jazz Bass 2", "Bass"),
    (36, 1, "Slap Bass 3", "Bass"),
    (38, 1, "Synth Bass 3", "Bass"),
    (38, 2, "Synth Bass 4", "Bass"),
    (38, 3, "Rubber Bass", "Bass"),
    (39, 1, "Attack Pulse", "Bass"),
    # Strings variations
    (40, 1, "Slow Violin", "Strings"),
    (44, 1, "Slow Tremolo", "Strings"),
    (48, 1, "Orchestra Strings", "Ensemble"),
    (48, 2, "Slow Strings", "Ensemble"),
    (50, 1, "Synth Strings 3", "Ensemble"),
    (52, 1, "Choir Aahs 2", "Ensemble"),
    # Brass variations
    (56, 1, "Dark Trumpet", "Brass"),
    (57, 1, "Trombone 2", "Brass"),
    (61, 1, "Brass 2", "Brass"),
    (62, 1, "Synth Brass 3", "Brass"),
    (62, 2, "Analog Brass 1", "Brass"),
    (63, 1, "Synth Brass 4", "Brass"),
    (63, 2, "Analog Brass 2", "Brass"),
    # Reed variations
    (64, 1, "Soprano Sax 2", "Reed"),
    (66, 1, "Tenor Sax 2", "Reed"),
    # Pipe variations
    (73, 1, "Flute 2", "Pipe"),
    # Synth Lead variations
    (80, 1, "Square 2", "Synth Lead"),
    (80, 2, "Sine Wave", "Synth Lead"),
    (81, 1, "Sawtooth 2", "Synth Lead"),
    (87, 1, "Big Lead", "Synth Lead"),
    # Synth Pad variations
    (88, 1, "New Age Pad 2", "Synth Pad"),
    (89, 1, "Warm Pad 2", "Synth Pad"),
    (89, 2, "Rotary Strings", "Synth Pad"),
    (91, 1, "Itopia", "Synth Pad"),
    # Ethnic variations
    (104, 1, "Sitar 2", "Ethnic"),
    # Sound Effects variations
    (122, 1, "Rain", "Sound Effects"),
    (122, 2, "Thunder", "Sound Effects"),
    (122, 3, "Wind", "Sound Effects"),
    (122, 4, "Stream", "Sound Effects"),
    (122, 5, "Bubble", "Sound Effects"),
    (123, 1, "Dog", "Sound Effects"),
    (123, 2, "Horse Gallop", "Sound Effects"),
    (123, 3, "Bird 2", "Sound Effects"),
    (124, 1, "Telephone 2", "Sound Effects"),
    (124, 2, "Door Creaking", "Sound Effects"),
    (124, 3, "Door Closing", "Sound Effects"),
    (124, 4, "Scratch", "Sound Effects"),
    (125, 1, "Rotor", "Sound Effects"),
    (125, 2, "Car Engine", "Sound Effects"),
    (125, 3, "Car Stop", "Sound Effects"),
    (125, 4, "Car Pass", "Sound Effects"),
    (125, 5, "Car Crash", "Sound Effects"),
    (125, 6, "Siren", "Sound Effects"),
    (125, 7, "Train", "Sound Effects"),
    (125, 8, "Jet Plane", "Sound Effects"),
    (125, 9, "Starship", "Sound Effects"),
    (125, 10, "Burst Noise", "Sound Effects"),
    (126, 1, "Laughing", "Sound Effects"),
    (126, 2, "Screaming", "Sound Effects"),
    (126, 3, "Punch", "Sound Effects"),
    (126, 4, "Heart Beat", "Sound Effects"),
    (126, 5, "Footsteps", "Sound Effects"),
    (127, 1, "Machine Gun", "Sound Effects"),
    (127, 2, "Laser Gun", "Sound Effects"),
    (127, 3, "Explosion", "Sound Effects"),
    (127, 4, "Firework", "Sound Effects"),
]

# GM/GM2 Drum Kits
# Format: (program, name)
GM_DRUM_KITS = [
    (0, "Standard Kit"),
]

# GM2 Drum Kits (Bank MSB=120)
GM2_DRUM_KITS = [
    (0, "Standard Kit"),
    (1, "Standard Kit 2"),
    (8, "Room Kit"),
    (16, "Power Kit"),
    (24, "Electronic Kit"),
    (25, "TR-808 Kit"),
    (26, "TR-909 Kit"),
    (32, "Jazz Kit"),
    (40, "Brush Kit"),
    (48, "Orchestra Kit"),
    (56, "Sound FX Kit"),
]


def get_connection():
    """Get a database connection."""
    return sqlite3.connect(DB_PATH)


def init_database():
    """Initialize the database schema and populate with data."""
    conn = get_connection()
    cursor = conn.cursor()

    # Create patches table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard TEXT NOT NULL,
            bank_msb INTEGER NOT NULL,
            bank_lsb INTEGER NOT NULL,
            program INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            UNIQUE(standard, bank_msb, bank_lsb, program)
        )
    """)

    # Create percussion_sets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS percussion_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard TEXT NOT NULL,
            bank_msb INTEGER NOT NULL,
            bank_lsb INTEGER NOT NULL,
            program INTEGER NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(standard, bank_msb, bank_lsb, program)
        )
    """)

    # Create indexes for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_patches_lookup
        ON patches(bank_msb, bank_lsb, program)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_percussion_lookup
        ON percussion_sets(bank_msb, bank_lsb, program)
    """)

    conn.commit()

    # Check if data already populated
    cursor.execute("SELECT COUNT(*) FROM patches")
    if cursor.fetchone()[0] == 0:
        _populate_gm_patches(conn)
        _populate_gm2_patches(conn)
        _populate_drum_kits(conn)
        _populate_gs_patches(conn)
        _populate_gs_drumkits(conn)

    conn.close()


def _populate_gm_patches(conn):
    """Populate GM patches (Bank 0:0)."""
    cursor = conn.cursor()
    for program, (name, category) in enumerate(GM_INSTRUMENTS):
        cursor.execute("""
            INSERT OR IGNORE INTO patches
            (standard, bank_msb, bank_lsb, program, name, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("GM", 0, 0, program, name, category))
    conn.commit()


def _populate_gm2_patches(conn):
    """Populate GM2 variation patches."""
    cursor = conn.cursor()

    # GM2 capital tones are same as GM (Bank 0:0), already added
    # Add GM2 variations (Bank MSB=0, LSB=1+)
    for program, lsb, name, category in GM2_VARIATIONS:
        cursor.execute("""
            INSERT OR IGNORE INTO patches
            (standard, bank_msb, bank_lsb, program, name, category)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("GM2", 0, lsb, program, name, category))
    conn.commit()


def _populate_drum_kits(conn):
    """Populate drum kit data."""
    cursor = conn.cursor()

    # GM Standard Kit (Bank 0:0, Program 0)
    for program, name in GM_DRUM_KITS:
        cursor.execute("""
            INSERT OR IGNORE INTO percussion_sets
            (standard, bank_msb, bank_lsb, program, name)
            VALUES (?, ?, ?, ?, ?)
        """, ("GM", 0, 0, program, name))

    # GM2 Drum Kits (Bank MSB=120, LSB=0)
    for program, name in GM2_DRUM_KITS:
        cursor.execute("""
            INSERT OR IGNORE INTO percussion_sets
            (standard, bank_msb, bank_lsb, program, name)
            VALUES (?, ?, ?, ?, ?)
        """, ("GM2", 120, 0, program, name))

    conn.commit()


def _populate_gs_patches(conn):
    """Populate GS patches from gs_instruments.csv.

    CSV columns: CC00, PC, CC32=4 (SC-8850), CC32=3 (SC-88Pro),
                 CC32=2 (SC-88), CC32=1 (SC-55/CM-64)
    bank_lsb encodes Sound Canvas generation: 4=SC-8850, 3=SC-88Pro,
    2=SC-88, 1=SC-55.
    """
    if not os.path.exists(GS_INSTRUMENTS_CSV):
        return

    cursor = conn.cursor()
    # CC32 values corresponding to columns 2-5 (index in row)
    cc32_values = [4, 3, 2, 1]

    last_valid_pc = 0  # Track last valid PC for correcting data errors

    with open(GS_INSTRUMENTS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header

        for row in reader:
            if len(row) < 6:
                continue

            msb = int(row[0])
            pc_raw = int(row[1])

            # Fix invalid PC values (>127) by using last valid PC
            if pc_raw > 127:
                pc = last_valid_pc
            else:
                pc = pc_raw
                last_valid_pc = pc

            # Insert for each non-empty Sound Canvas column
            for col_idx, cc32 in enumerate(cc32_values):
                cell = row[2 + col_idx].strip()
                if cell:
                    cursor.execute("""
                        INSERT OR IGNORE INTO patches
                        (standard, bank_msb, bank_lsb, program, name, category)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, ("GS", msb, cc32, pc, cell, None))

    conn.commit()


def _populate_gs_drumkits(conn):
    """Populate GS drum kits from gs_drumkits.csv.

    CSV columns: PC, CC32=4 (SC-8850), CC32=3 (SC-88Pro),
                 CC32=2 (SC-88), CC32=1 (SC-55)
    bank_msb is always 0 for GS drum kits.
    """
    if not os.path.exists(GS_DRUMKITS_CSV):
        return

    cursor = conn.cursor()
    cc32_values = [4, 3, 2, 1]

    with open(GS_DRUMKITS_CSV, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header

        for row in reader:
            if len(row) < 5:
                continue

            pc = int(row[0])

            for col_idx, cc32 in enumerate(cc32_values):
                cell = row[1 + col_idx].strip()
                if cell:
                    cursor.execute("""
                        INSERT OR IGNORE INTO percussion_sets
                        (standard, bank_msb, bank_lsb, program, name)
                        VALUES (?, ?, ?, ?, ?)
                    """, ("GS", 0, cc32, pc, cell))

    conn.commit()


def get_patch_name(bank_msb, bank_lsb, program, standard=None):
    """
    Look up patch name from database.

    Args:
        bank_msb: Bank Select MSB (CC 0), 0-127
        bank_lsb: Bank Select LSB (CC 32), 0-127
        program: Program Change, 0-127
        standard: Optional MIDI standard ('GM', 'GM2', 'GS', 'XG')

    Returns:
        Tuple of (name, category) or (None, None) if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    result = None

    # If standard specified, try exact match first
    if standard:
        cursor.execute("""
            SELECT name, category FROM patches
            WHERE standard = ? AND bank_msb = ? AND bank_lsb = ? AND program = ?
        """, (standard, bank_msb, bank_lsb, program))
        result = cursor.fetchone()

    # GS-specific fallback: try lower bank_lsb values (older SC generations)
    if not result and standard == "GS":
        for fallback_lsb in range(bank_lsb - 1, 0, -1):
            cursor.execute("""
                SELECT name, category FROM patches
                WHERE standard = 'GS' AND bank_msb = ? AND bank_lsb = ? AND program = ?
            """, (bank_msb, fallback_lsb, program))
            result = cursor.fetchone()
            if result:
                break

        # Fall back to base GS patch (MSB=0, LSB=1)
        if not result and (bank_msb != 0 or bank_lsb != 1):
            cursor.execute("""
                SELECT name, category FROM patches
                WHERE standard = 'GS' AND bank_msb = 0 AND bank_lsb = 1 AND program = ?
            """, (program,))
            result = cursor.fetchone()

    # If no match, try any standard with exact bank/program
    if not result:
        cursor.execute("""
            SELECT name, category FROM patches
            WHERE bank_msb = ? AND bank_lsb = ? AND program = ?
            ORDER BY CASE standard
                WHEN 'GM' THEN 1
                WHEN 'GM2' THEN 2
                WHEN 'GS' THEN 3
                WHEN 'XG' THEN 4
                ELSE 5
            END
            LIMIT 1
        """, (bank_msb, bank_lsb, program))
        result = cursor.fetchone()

    # Fall back to GM base patch (Bank 0:0)
    if not result and (bank_msb != 0 or bank_lsb != 0):
        cursor.execute("""
            SELECT name, category FROM patches
            WHERE standard = 'GM' AND bank_msb = 0 AND bank_lsb = 0 AND program = ?
        """, (program,))
        result = cursor.fetchone()

    conn.close()

    if result:
        return result[0], result[1]
    return None, None


def get_percussion_name(bank_msb, bank_lsb, program, standard=None):
    """
    Look up percussion set name from database.

    Args:
        bank_msb: Bank Select MSB (CC 0), 0-127
        bank_lsb: Bank Select LSB (CC 32), 0-127
        program: Program Change (drum kit number), 0-127
        standard: Optional MIDI standard ('GM', 'GM2', 'GS', 'XG')

    Returns:
        Percussion set name or None if not found
    """
    conn = get_connection()
    cursor = conn.cursor()

    result = None

    # If standard specified, try exact match first
    if standard:
        cursor.execute("""
            SELECT name FROM percussion_sets
            WHERE standard = ? AND bank_msb = ? AND bank_lsb = ? AND program = ?
        """, (standard, bank_msb, bank_lsb, program))
        result = cursor.fetchone()

    # GS-specific fallback: try lower bank_lsb values (older SC generations),
    # then SC-55 base kit (lsb=1) — covers the common case where no CC32 is
    # sent on the percussion channel (bank_lsb stays at 0).
    if not result and standard == "GS":
        for fallback_lsb in range(bank_lsb - 1, 0, -1):
            cursor.execute("""
                SELECT name FROM percussion_sets
                WHERE standard = 'GS' AND bank_msb = ? AND bank_lsb = ? AND program = ?
            """, (bank_msb, fallback_lsb, program))
            result = cursor.fetchone()
            if result:
                break
        # Final GS fallback: SC-55 base kit (lsb=1) when no CC32 was sent
        if not result:
            cursor.execute("""
                SELECT name FROM percussion_sets
                WHERE standard = 'GS' AND bank_msb = ? AND bank_lsb = 1 AND program = ?
            """, (bank_msb, program))
            result = cursor.fetchone()

    # If no match, try any standard with exact bank/program
    if not result:
        cursor.execute("""
            SELECT name FROM percussion_sets
            WHERE bank_msb = ? AND bank_lsb = ? AND program = ?
            ORDER BY CASE standard
                WHEN 'GM' THEN 1
                WHEN 'GM2' THEN 2
                WHEN 'GS' THEN 3
                WHEN 'XG' THEN 4
                ELSE 5
            END
            LIMIT 1
        """, (bank_msb, bank_lsb, program))
        result = cursor.fetchone()

    # For GM2, try with Bank MSB=120
    if not result and standard == "GM2":
        cursor.execute("""
            SELECT name FROM percussion_sets
            WHERE standard = 'GM2' AND bank_msb = 120 AND bank_lsb = 0 AND program = ?
        """, (program,))
        result = cursor.fetchone()

    # Fall back to GM Standard Kit
    if not result:
        cursor.execute("""
            SELECT name FROM percussion_sets
            WHERE standard = 'GM' AND bank_msb = 0 AND bank_lsb = 0 AND program = 0
        """)
        result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]
    return None


def get_instrument_name(program, channel=None, bank_msb=0, bank_lsb=0, standard=None):
    """
    Get instrument name from program number with bank and standard support.

    This is a convenience function that wraps get_patch_name and get_percussion_name.

    Args:
        program: Program Change, 0-127
        channel: MIDI channel (1-16, where 10 is percussion)
        bank_msb: Bank Select MSB, default 0
        bank_lsb: Bank Select LSB, default 0
        standard: Optional MIDI standard

    Returns:
        Instrument or drum kit name
    """
    # Channel 10 is the percussion channel in GM/GS/XG
    if channel == 10:
        name = get_percussion_name(bank_msb, bank_lsb, program, standard)
        if name:
            return name
        return f"Drum Kit {program}"

    name, _ = get_patch_name(bank_msb, bank_lsb, program, standard)
    if name:
        return name
    return f"Unknown ({program})"


def get_drum_kit_name(program, bank_msb=0, bank_lsb=0, standard=None):
    """
    Get drum kit name from program number.

    Args:
        program: Program Change (drum kit number), 0-127
        bank_msb: Bank Select MSB, default 0
        bank_lsb: Bank Select LSB, default 0
        standard: Optional MIDI standard

    Returns:
        Drum kit name
    """
    name = get_percussion_name(bank_msb, bank_lsb, program, standard)
    if name:
        return name
    return f"Drum Kit {program}"


# Initialize database on module import
if not os.path.exists(DB_PATH):
    init_database()
