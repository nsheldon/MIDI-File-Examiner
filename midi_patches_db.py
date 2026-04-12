#!/usr/bin/env python3
"""
MIDI Patches Database Module

Provides SQLite-based storage and retrieval of MIDI patch names and
percussion sets across GM, GM2, GS, and XG standards.
"""

import sqlite3
import os

# Database path - same directory as this module
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "midi_patches.db")

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


GS_INSTRUMENTS = [
    # Format: (msb, pc, sc8850_name, sc88pro_name, sc88_name, sc55_name)
    # Empty string means the patch does not exist on that generation.
    (0, 0, 'Piano 1', 'Piano 1', 'Piano 1', 'Piano 1'),
    (1, 0, 'UprightPiano', '', '', ''),
    (2, 0, 'Mild Piano', '', '', ''),
    (8, 0, 'Upright P w', 'Piano 1w', 'Piano 1w', 'Piano 1w'),
    (9, 0, 'Mild Piano w', '', '', ''),
    (16, 0, 'European Pf', 'European Pf', 'Piano 1d', 'Piano 1d'),
    (24, 0, 'Piano + Str.', 'Piano + Str.', '', ''),
    (25, 0, 'Piano + Str2', '', '', ''),
    (26, 0, 'Piano+Choir1', '', '', ''),
    (27, 0, 'Piano+Choir2', '', '', ''),
    (0, 1, 'Piano 2', 'Piano 2', 'Piano 2', 'Piano 2'),
    (1, 1, 'Pop Piano', '', '', ''),
    (2, 1, 'Rock Piano', '', '', ''),
    (8, 1, 'Pop Piano w', 'Piano 2w', 'Piano 2w', 'Piano 2w'),
    (9, 1, 'Rock Piano w', '', '', ''),
    (16, 1, 'Dance Piano', 'Dance Piano', '', ''),
    (0, 2, 'Piano 3', 'Piano 3', 'Piano 3', 'Piano 3'),
    (1, 2, 'EG+Rhodes 1', 'EG+Rhodes 1', 'EG+Rhodes 1', ''),
    (2, 2, 'EG+Rhodes 2', 'EG+Rhodes 2', 'EG+Rhodes 2', ''),
    (8, 2, 'Piano 3w', 'Piano 3w', 'Piano 3w', 'Piano 3w'),
    (0, 3, 'Honky-tonk', 'Honky-tonk', 'Honky-tonk', 'Honky-tonk'),
    (8, 3, 'Honky-tonk 2', 'Honky-tonk 2', 'Old Upright', 'HonkyTonk w'),
    (0, 4, 'E.Piano 1', 'E.Piano 1', 'E.Piano 1', 'E.Piano 1'),
    (8, 4, 'St.Soft EP', 'St.Soft EP', 'St.Soft EP', 'Detuned EP1'),
    (9, 4, 'Cho. E.Piano', 'Cho. E.Piano', '', ''),
    (10, 4, 'SilentRhodes', 'SilentRhodes', '', ''),
    (16, 4, 'FM+SA EP', 'FM+SA EP', 'FM+SA EP', 'E.Piano 1v'),
    (17, 4, 'Dist E.Piano', 'Dist E.Piano', '', ''),
    (24, 4, 'Wurly', 'Wurly', "60'sE.Piano", '60s E.Piano'),
    (25, 4, 'Hard Rhodes', 'Hard Rhodes', 'Hard Rhodes', ''),
    (26, 4, 'MellowRhodes', 'MellowRhodes', 'MellwRhodes', ''),
    (0, 5, 'E.Piano 2', 'E.Piano 2', 'E.Piano 2', 'E.Piano 2'),
    (1, 5, 'E.Piano 3', '', '', ''),
    (8, 5, 'Detuned EP 2', 'Detuned EP 2', 'Detuned EP2', 'Detuned EP2'),
    (9, 5, 'Detuned EP 3', '', '', ''),
    (10, 5, 'EP Legend', '', '', ''),
    (16, 5, 'St.FM EP', 'St.FM EP', 'St.FM EP', 'E.Piano 2v'),
    (24, 5, 'Hard FM EP', 'Hard FM EP', 'Hard FM EP', ''),
    (32, 5, 'EP Phase', '', '', ''),
    (0, 6, 'Harpsichord', 'Harpsichord', 'Harpsichord', 'Harpsichord'),
    (1, 6, 'Harpsichord2', 'Harpsichord2', '', ''),
    (2, 6, 'Harpsichord3', '', '', ''),
    (8, 6, 'Coupled Hps.', 'Coupled Hps.', 'Coupled Hps', 'Coupled Hps'),
    (16, 6, 'Harpsi.w', 'Harpsi.w', 'Harpsi.w', 'Harpsi.w'),
    (24, 6, 'Harpsi.o', 'Harpsi.o', 'Harpsi.o', 'Harpsi.o'),
    (32, 6, 'Synth Harpsi', 'Synth Harpsi', '', ''),
    (0, 7, 'Clav.', 'Clav.', 'Clav.', 'Clav.'),
    (1, 7, 'Clav. 2', '', '', ''),
    (2, 7, 'Atk Clav.1', '', '', ''),
    (3, 7, 'Atk Clav.2', '', '', ''),
    (8, 7, 'Comp Clav.', 'Comp Clav.', '', ''),
    (16, 7, 'Reso Clav.', 'Reso Clav.', '', ''),
    (17, 7, 'Phase Clav', '', '', ''),
    (24, 7, 'Clav.o', 'Clav.o', '', ''),
    (32, 7, 'Analog Clav.', 'Analog Clav.', '', ''),
    (33, 7, 'JP8 Clav. 1', 'JP8 Clav. 1', '', ''),
    (35, 7, 'JP8 Clav. 2', 'JP8 Clav. 2', '', ''),
    (36, 7, 'SynRingClav.', '', '', ''),
    (37, 7, 'SynDistClav.', '', '', ''),
    (38, 7, 'JP8000 Clav.', '', '', ''),
    (39, 7, 'Pulse Clav', '', '', ''),
    (0, 8, 'Celesta', 'Celesta', 'Celesta', 'Celesta'),
    (1, 8, 'Pop Celesta', 'Pop Celesta', '', ''),
    (0, 9, 'Glockenspiel', 'Glockenspiel', 'Glocknspiel', 'Glockenspl'),
    (0, 10, 'Music Box', 'Music Box', 'Music Box', 'Music Box'),
    (1, 10, 'Music Box 2', '', '', ''),
    (8, 10, 'St.Music Box', '', '', ''),
    (0, 11, 'Vibraphone', 'Vibraphone', 'Vibraphone', 'Vibraphone'),
    (1, 11, 'Pop Vibe.', 'Pop Vibe.', 'Hard Vibe', ''),
    (8, 11, 'Vibraphone w', 'Vibraphone w', 'Vib.w', 'Vib.w'),
    (9, 11, 'Vibraphones', 'Vibraphones', '', ''),
    (0, 12, 'Marimba', 'Marimba', 'Marimba', 'Marimba'),
    (8, 12, 'Marimba w', 'Marimba w', 'Marimba w', 'Marimba w'),
    (16, 12, 'Barafon', 'Barafon', 'Barafon', ''),
    (17, 12, 'Barafon 2', 'Barafon 2', 'Barafon 2', ''),
    (24, 12, 'Log drum', 'Log drum', 'Log drum', ''),
    (0, 13, 'Xylophone', 'Xylophone', 'Xylophone', 'Xylophone'),
    (8, 13, 'Xylophone w', '', '', ''),
    (0, 14, 'Tubular-bell', 'Tubular-bell', 'Tubularbell', 'Tubularbell'),
    (8, 14, 'Church Bell', 'Church Bell', 'Church Bell', 'Church Bell'),
    (9, 14, 'Carillon', 'Carillon', 'Carillon', 'Carillon'),
    (10, 14, 'Church Bell2', '', '', ''),
    (16, 14, 'Tubularbellw', '', '', ''),
    (0, 15, 'Santur', 'Santur', 'Santur', 'Santur'),
    (1, 15, 'Santur 2', 'Santur 2', 'Santur 2', ''),
    (2, 15, 'Santur 3', '', '', ''),
    (8, 15, 'Cimbalom', 'Cimbalom', 'Cimbalom', ''),
    (16, 15, 'Zither 1', 'Zither 1', '', ''),
    (17, 15, 'Zither 2', 'Zither 2', '', ''),
    (24, 15, 'Dulcimer', 'Dulcimer', '', ''),
    (0, 16, 'Organ 1', 'Organ 1', 'Organ 1', 'Organ 1'),
    (1, 16, 'Organ 101', 'Organ 101', 'Organ 101', ''),
    (2, 16, 'Ful Organ 1', '', '', ''),
    (3, 16, 'Ful Organ 2', '', '', ''),
    (4, 16, 'Ful Organ 3', '', '', ''),
    (5, 16, 'Ful Organ 4', '', '', ''),
    (6, 16, 'Ful Organ 5', '', '', ''),
    (7, 16, 'Ful Organ 6', '', '', ''),
    (8, 16, 'Trem. Organ', 'Trem. Organ', 'DetunedOr.1', 'Detuned Or1'),
    (9, 16, 'Organ o', 'Organ. o', 'Organ 109', ''),
    (10, 16, 'Ful Organ 7', '', '', ''),
    (11, 16, 'Ful Organ 8', '', '', ''),
    (12, 16, 'Ful Organ 9', '', '', ''),
    (16, 16, "60's Organ 1", "60's Organ 1", "60'sOrgan 1", "60's Organ1"),
    (17, 16, "60's Organ 2", "60's Organ 2", "60'sOrgan 2", ''),
    (18, 16, "60's Organ 3", "60's Organ 3", "60'sOrgan 3", ''),
    (19, 16, 'Farf Organ', 'Farf Organ', '', ''),
    (24, 16, 'Cheese Organ', 'Cheese Organ', 'CheeseOrgan', ''),
    (25, 16, 'D-50 Organ', 'D-50 Organ', '', ''),
    (26, 16, 'JUNO Organ', 'JUNO Organ', '', ''),
    (27, 16, 'Hybrid Organ', 'Hybrid Organ', '', ''),
    (28, 16, 'VS Organ', 'VS Organ', '', ''),
    (29, 16, 'Digi Church', 'Digi Church', '', ''),
    (30, 16, 'JX-8P Organ', '', '', ''),
    (31, 16, 'FM Organ', '', '', ''),
    (32, 16, "70's E.Organ", "70's E.Organ", 'Organ 4', 'Organ 4'),
    (33, 16, 'Even Bar', 'Even Bar', 'Even Bar', ''),
    (40, 16, 'Organ Bass', 'Organ Bass', 'Organ Bass', ''),
    (48, 16, '5th Organ', '5th Organ', '', ''),
    (0, 17, 'Organ 2', 'Organ 2', 'Organ 2', 'Organ 2'),
    (1, 17, 'Jazz Organ', 'Jazz Organ', 'Organ 201', ''),
    (2, 17, 'E.Organ 16+2', 'E.Organ 16+2', '', ''),
    (3, 17, 'Jazz Organ 2', '', '', ''),
    (4, 17, 'Jazz Organ 3', '', '', ''),
    (5, 17, 'Jazz Organ 4', '', '', ''),
    (6, 17, 'Jazz Organ 5', '', '', ''),
    (7, 17, 'Jazz Organ 6', '', '', ''),
    (8, 17, 'Chorus Or.2', 'Chorus Or.2', 'DetunedOr.2', 'Detuned Or2'),
    (9, 17, 'Octave Organ', 'Octave Organ', '', ''),
    (32, 17, 'Perc. Organ', 'Perc. Organ', 'Organ 5', 'Organ 5'),
    (33, 17, 'Perc.Organ 2', '', '', ''),
    (34, 17, 'Perc.Organ 3', '', '', ''),
    (35, 17, 'Perc.Organ 4', '', '', ''),
    (0, 18, 'Organ 3', 'Organ 3', 'Organ 3', 'Organ 3'),
    (8, 18, 'Rotary Org.', 'Rotary Org.', 'Rotary Org.', ''),
    (16, 18, 'Rotary Org.S', 'Rotary Org.S', 'RotaryOrg.S', ''),
    (17, 18, 'Rock Organ 1', 'Rock Organ 1', '', ''),
    (18, 18, 'Rock Organ 2', 'Rock Organ 2', '', ''),
    (24, 18, 'Rotary Org.F', 'Rotary Org.F', 'RotaryOrg.F', ''),
    (0, 19, 'Church Org.1', 'Church Org.1', 'ChurchOrg.1', 'Church Org1'),
    (8, 19, 'Church Org.2', 'Church Org.2', 'ChurchOrg.2', 'Church Org2'),
    (16, 19, 'Church Org.3', 'Church Org.3', 'ChurchOrg.3', 'Church Org3'),
    (24, 19, 'Organ Flute', 'Organ Flute', 'Organ Flute', ''),
    (32, 19, 'Trem.Flute', 'Trem.Flute', 'Trem.Flute', ''),
    (33, 19, 'Theater Org.', 'Theater Org.', '', ''),
    (0, 20, 'Reed Organ', 'Reed Organ', 'Reed Organ', 'Reed Organ'),
    (8, 20, 'Wind Organ', 'Wind Organ', '', ''),
    (16, 20, 'Puff Organ', '', '', ''),
    (0, 21, 'Accordion Fr', 'Accordion Fr', 'AccordionFr', 'Accordion F'),
    (8, 21, 'Accordion It', 'Accordion It', 'AccordionIt', 'Accordion I'),
    (9, 21, 'Dist. Accord', 'Dist. Accord', '', ''),
    (16, 21, 'Cho. Accord', 'Cho. Accord', '', ''),
    (24, 21, 'Hard Accord', 'Hard Accord', '', ''),
    (25, 21, 'Soft Accord', 'Soft Accord', '', ''),
    (0, 22, 'Harmonica', 'Harmonica', 'Harmonica', 'Harmonica'),
    (1, 22, 'Harmonica 2', 'Harmonica 2', 'Harmonica 2', ''),
    (8, 22, 'B.Harp Basic', '', '', ''),
    (9, 22, 'B.Harp Suppl', '', '', ''),
    (0, 23, 'Bandoneon', 'Bandoneon', 'Bandoneon', 'Bandoneon'),
    (8, 23, 'Bandoneon 2', 'Bandoneon 2', '', ''),
    (16, 23, 'Bandoneon 3', 'Bandoneon 3', '', ''),
    (0, 24, 'Nylon-str.Gt', 'Nylon-str.Gt', 'Nylonstr.Gt', 'Nylon Gt.'),
    (8, 24, 'Ukulele', 'Ukulele', 'Ukulele', 'Ukulele'),
    (16, 24, 'Nylon Gt.o', 'Nylon Gt.o', 'Nylon Gt.o', 'Nylon Gt.o'),
    (24, 24, 'Velo Harmnix', 'Velo Harmnix', 'VeloHarmnix', ''),
    (32, 24, 'Nylon Gt.2', 'Nylon Gt 2', 'Nylon Gt.2', 'Nylon Gt.2'),
    (40, 24, 'Lequint Gt.', 'Lequint Gt.', 'Lequint Gt.', ''),
    (0, 25, 'Steel-str.Gt', 'Steel-str.Gt', 'Steelstr.Gt', 'Steel Gt.'),
    (8, 25, '12-str.Gt', '12-str.Gt', '12-str.Gt', '12-str.Gt'),
    (9, 25, 'Nylon+Steel', 'Nylon+Steel', 'Nylon+Steel', ''),
    (10, 25, 'Atk Steel Gt', '', '', ''),
    (16, 25, 'Mandolin', 'Mandolin', 'Mandolin', 'Mandolin'),
    (17, 25, 'Mandolin 2', 'Mandolin 2', '', ''),
    (18, 25, 'MandolinTrem', 'MandolinTrem', '', ''),
    (32, 25, 'Steel Gt.2', 'Steel Gt.2', 'Steel Gt.2', ''),
    (33, 25, 'Steel + Body', '', '', ''),
    (0, 26, 'Jazz Gt.', 'Jazz Gt.', 'Jazz Gt.', 'Jazz Gt.'),
    (1, 26, 'Mellow Gt.', 'Mellow Gt.', 'Mellow Gt.', ''),
    (8, 26, 'Pedal Steel', 'Pedal Steel', 'Pedal Steel', 'Hawaiian Gt'),
    (0, 27, 'Clean Gt.', 'Clean Gt.', 'Clean Gt.', 'Clean Gt.'),
    (1, 27, 'Clean Half', 'Clean Half', '', ''),
    (2, 27, 'Open Hard 1', 'Open Hard 1', '', ''),
    (3, 27, 'Open Hard 2', 'Open Hard 2', '', ''),
    (4, 27, 'JC Clean Gt.', 'JC Clean Gt.', '', ''),
    (5, 27, 'Atk CleanGt.', '', '', ''),
    (8, 27, 'Chorus Gt.', 'Chorus Gt.', 'Chorus Gt.', 'Chorus Gt.'),
    (9, 27, 'JC Chorus Gt', 'JC Chorus Gt', '', ''),
    (16, 27, 'TC FrontPick', 'TC FrontPick', '', ''),
    (17, 27, 'TC Rear Pick', 'TC Rear Pick', '', ''),
    (18, 27, 'TC Clean ff', 'TC Clean ff', '', ''),
    (19, 27, 'TC Clean 2', 'TC Clean 2', '', ''),
    (20, 27, 'LP Rear Pick', '', '', ''),
    (21, 27, 'LP Rear 2', '', '', ''),
    (22, 27, 'LP RearAtack', '', '', ''),
    (23, 27, 'Mid Tone GTR', '', '', ''),
    (24, 27, 'Chung Ruan', '', '', ''),
    (25, 27, 'Chung Ruan 2', '', '', ''),
    (0, 28, 'Muted Gt.', 'Muted Gt.', 'Muted Gt.', 'Muted Gt.'),
    (1, 28, 'Muted Dis.Gt', 'Muted Dis.Gt', 'MutedDis.Gt', ''),
    (2, 28, 'TC Muted Gt.', 'TC Muted Gt.', '', ''),
    (8, 28, 'Funk Pop', 'Funk Pop', 'Funk Pop', 'Funk Gt.'),
    (16, 28, 'Funk Gt.2', 'Funk Gt.2', 'Funk Gt.2', 'Funk Gt.2'),
    (24, 28, 'Jazz Man', '', '', ''),
    (0, 29, 'Overdrive Gt', 'OverdriveGt', 'OverdriveGt', 'OverdriveGt'),
    (1, 29, 'Overdrive 2', 'Overdrive 2', '', ''),
    (2, 29, 'Overdrive 3', 'Overdrive 3', '', ''),
    (3, 29, 'More Drive', 'More Drive', '', ''),
    (4, 29, 'Guitar Pinch', '', '', ''),
    (5, 29, 'Attack Drive', '', '', ''),
    (8, 29, 'LP OverDrvGt', 'LP OverDrvGt', '', ''),
    (9, 29, 'LP OverDrv', 'LP OverDrv', '', ''),
    (10, 29, 'LP Half Drv', '', '', ''),
    (11, 29, 'LP Half Drv2', '', '', ''),
    (12, 29, 'LP Chorus', '', '', ''),
    (0, 30, 'DistortionGt', 'DistortionGt', 'DistortionGt', 'Dist.Gt.'),
    (1, 30, 'Dist. Gt2', 'Dist. Gt2', 'Dist. Gt2', ''),
    (2, 30, 'Dazed Guitar', 'Dazed Guitar', 'DazedGuitar', ''),
    (3, 30, 'Distortion', 'Distortion', '', ''),
    (4, 30, 'Dist.Fast', 'Dist.Fast', '', ''),
    (5, 30, 'Attack Dist', '', '', ''),
    (8, 30, 'Feedback Gt.', 'Feedback Gt.', 'FeedbackGt.', 'Feedback Gt'),
    (9, 30, 'Feedback Gt2', 'Feedback Gt2', 'FeedbackGt2', ''),
    (16, 30, 'Power Guitar', 'Power Guitar', 'PowerGuitar', ''),
    (17, 30, 'Power Gt.2', 'Power Gt.2', 'Power Gt.2', ''),
    (18, 30, '5th Dist.', '5th Dist.', '5th Dist.', ''),
    (24, 30, 'Rock Rhythm', 'Rock Rhythm', 'Rock Rhythm', ''),
    (25, 30, 'Rock Rhythm2', 'Rock Rhythm2', 'RockRhythm2', ''),
    (26, 30, 'Dist Rtm GTR', '', '', ''),
    (0, 31, 'Gt.Harmonics', 'Gt.Harmonics', 'Gt.Harmonix', 'Gt.Harmonix'),
    (8, 31, 'Gt. Feedback', 'Gt. Feedback', 'Gt.Feedback', 'Gt.Feedback'),
    (9, 31, 'Gt.Feedback2', 'Gt. Feedback2', '', ''),
    (16, 31, 'Ac.Gt.Harmnx', 'Ac.Gt.Harmnx', 'Ac.Gt.Harm.', ''),
    (24, 31, 'E.Bass Harm.', 'E.Bass Harm.', '', ''),
    (0, 32, 'Acoustic Bs.', 'Acoustic Bs.', 'AcousticBs.', 'Acoustic Bs'),
    (1, 32, 'Rockabilly', 'Rockabilly', '', ''),
    (8, 32, 'Wild A.Bass', 'Wild A.Bass', '', ''),
    (9, 32, 'Atk A.Bass', '', '', ''),
    (16, 32, 'Bass + OHH', 'Bass + OHH', '', ''),
    (0, 33, 'Fingered Bs.', 'Fingered Bs.', 'FingeredBs.', 'Fingered Bs'),
    (1, 33, 'Fingered Bs2', 'Fingered Bs2', 'FingeredBs2', ''),
    (2, 33, 'Jazz Bass', 'Jazz Bass', 'Jazz Bass', ''),
    (3, 33, 'Jazz Bass 2', 'Jazz Bass 2', '', ''),
    (4, 33, 'Rock Bass', 'Rock Bass', '', ''),
    (5, 33, 'Heart Bass', '', '', ''),
    (6, 33, 'AttackFinger', '', '', ''),
    (7, 33, 'Finger Slap', '', '', ''),
    (8, 33, 'ChorusJazzBs', 'ChorusJazzBs', '', ''),
    (16, 33, 'F.Bass/Harm.', 'F.Bass/Harm.', '', ''),
    (0, 34, 'Picked Bass', 'Picked Bass', 'Picked Bass', 'Picked Bass'),
    (1, 34, 'Picked Bass2', 'Picked Bass2', '', ''),
    (2, 34, 'Picked Bass3', 'Picked Bass3', '', ''),
    (3, 34, 'Picked Bass4', 'Picked Bass4', '', ''),
    (4, 34, 'Double Pick', '', '', ''),
    (8, 34, 'Muted PickBs', 'Muted PickBs', 'MutePickBs.', ''),
    (16, 34, 'P.Bass/Harm.', 'P.Bass/Harm.', '', ''),
    (0, 35, 'Fretless Bs.', 'Fretless Bs.', 'FretlessBs.', 'Fretless Bs'),
    (1, 35, 'Fretless Bs2', 'Fretless Bs2', 'FretlessBs2', ''),
    (2, 35, 'Fretless Bs3', 'Fretless Bs3', 'FretlessBs3', ''),
    (3, 35, 'Fretless Bs4', 'Fretless Bs4', 'FretlessBs4', ''),
    (4, 35, 'Syn Fretless', 'Syn Fretless', 'SynFretless', ''),
    (5, 35, 'Mr.Smooth', 'Mr.Smooth', 'Mr.Smooth', ''),
    (8, 35, 'Wood+FlessBs', 'Wood+FlessBs', '', ''),
    (0, 36, 'Slap Bass 1', 'Slap Bass 1', 'Slap Bass 1', 'Slap Bass 1'),
    (1, 36, 'Slap Pop', 'Slap Pop', '', ''),
    (8, 36, 'Reso Slap', 'Reso Slap', 'Reso Slap', ''),
    (9, 36, 'Unison Slap', 'Unison Slap', '', ''),
    (0, 37, 'Slap Bass 2', 'Slap Bass 2', 'Slap Bass 2', 'Slap Bass 2'),
    (1, 37, 'Slap Bass 3', '', '', ''),
    (8, 37, 'FM Slap', 'FM Slap', '', ''),
    (0, 38, 'Synth Bass 1', 'Synth Bass 1', 'SynthBass 1', 'Syn.Bass 1'),
    (1, 38, 'SynthBass101', 'SynthBass101', 'Syn.Bass101', 'Syn.Bass101'),
    (2, 38, 'CS Bass', 'CS Bass', '', ''),
    (3, 38, 'JP-4 Bass', 'JP-4 Bass', '', ''),
    (4, 38, 'JP-8 Bass', 'JP-8 Bass', '', ''),
    (5, 38, 'P5 Bass', 'P5 Bass', '', ''),
    (6, 38, 'JPMG Bass', 'JPMG Bass', '', ''),
    (8, 38, 'Acid Bass', 'Acid Bass', 'Acid Bass', 'Syn.Bass 3'),
    (9, 38, 'TB303 Bass', 'TB303 Bass', 'TB303 Bass', ''),
    (10, 38, 'Tekno Bass', 'Tekno Bass', 'Tekno Bass', ''),
    (11, 38, 'TB303 Bass 2', 'TB303 Bass 2', '', ''),
    (12, 38, 'Kicked TB303', 'Kicked TB303', '', ''),
    (13, 38, 'TB303 Saw Bs', 'TB303 Saw Bs', '', ''),
    (14, 38, 'Rubber303 Bs', 'Rubber303 Bs', '', ''),
    (15, 38, 'Reso 303 Bs', 'Reso 303 Bs', '', ''),
    (16, 38, 'Reso SH Bass', 'Reso SH Bass', 'Reso SHBass', ''),
    (17, 38, 'TB303 Sqr Bs', '303 Sqr Bs', '', ''),
    (18, 38, 'TB303 DistBs', 'TB303 DistBs', '', ''),
    (19, 38, 'Clavi Bass', '', '', ''),
    (20, 38, 'Hammer', '', '', ''),
    (21, 38, 'Jungle Bass', '', '', ''),
    (22, 38, 'Square Bass', '', '', ''),
    (23, 38, 'Square Bass2', '', '', ''),
    (24, 38, 'Arpeggio Bs', 'Arpeggio Bs', '', ''),
    (32, 38, 'Hit&Saw Bass', '', '', ''),
    (33, 38, 'Ring Bass', '', '', ''),
    (34, 38, 'AtkSineBass', '', '', ''),
    (35, 38, 'OB sine Bass', '', '', ''),
    (36, 38, 'Auxiliary Bs', '', '', ''),
    (40, 38, '303SqDistBs', '', '', ''),
    (41, 38, '303SqDistBs2', '', '', ''),
    (42, 38, '303SqDistBs3', '', '', ''),
    (43, 38, '303Sqr.Rev', '', '', ''),
    (44, 38, 'TeeBee', '', '', ''),
    (0, 39, 'Synth Bass 2', 'Synth Bass 2', 'SynthBass 2', 'Syn.Bass 2'),
    (1, 39, 'SynthBass201', 'SynthBass201', 'Syn.Bass201', ''),
    (2, 39, 'Modular Bass', 'Modular Bass', 'ModularBass', ''),
    (3, 39, 'Seq Bass', 'Seq Bass', 'Seq Bass', ''),
    (4, 39, 'MG Bass', 'MG Bass', '', ''),
    (5, 39, 'Mg Oct Bass1', 'Mg Oct Bass1', '', ''),
    (6, 39, 'MG Oct Bass2', 'MG Oct Bass2', '', ''),
    (7, 39, 'MG Blip Bs', 'MG Blip Bs', '', ''),
    (8, 39, 'Beef FM Bass', 'Beef FM Bass', 'Beef FMBass', 'Syn.Bass 4'),
    (9, 39, 'Dly Bass', 'Dly Bass', 'X Wire Bass', ''),
    (10, 39, 'X Wire Bass', 'X Wire Bass', '', ''),
    (11, 39, 'WireStr Bass', 'WireStr Bass', '', ''),
    (12, 39, 'Blip Bass', 'Blip Bass', '', ''),
    (13, 39, 'RubberBass 1', 'RubberBass 1', '', ''),
    (14, 39, 'Syn Bell Bs', '', '', ''),
    (15, 39, 'Odd Bass', '', '', ''),
    (16, 39, 'RubberBass 2', 'RubberBass 2', 'Rubber Bass', 'Rubber Bass'),
    (17, 39, 'SH101 Bass 1', 'SH101 Bass 1', 'SH101Bass 1', ''),
    (18, 39, 'SH101 Bass 2', 'SH101 Bass 2', 'SH101Bass 2', ''),
    (19, 39, 'Smooth Bass', 'Smooth Bass', 'Smooth Bass', ''),
    (20, 39, 'SH101 Bass 3', 'SH101 Bass 3', '', ''),
    (21, 39, 'Spike Bass', 'Spike Bass', '', ''),
    (22, 39, 'House Bass', 'House Bass', '', ''),
    (23, 39, 'KG Bass', 'KG Bass', '', ''),
    (24, 39, 'Sync Bass', 'Sync Bass', '', ''),
    (25, 39, 'MG 5th Bass', 'MG 5th Bass', '', ''),
    (26, 39, 'RND Bass', 'RND Bass', '', ''),
    (27, 39, 'WowMG Bass', 'WowMG Bass', '', ''),
    (28, 39, 'Bubble Bass', 'Bubble Bass', '', ''),
    (29, 39, 'Attack Pulse', '', '', ''),
    (30, 39, 'Sync Bass 2', '', '', ''),
    (31, 39, 'Pulse Mix Bs', '', '', ''),
    (32, 39, 'MG Dist Bass', '', '', ''),
    (33, 39, 'Seq Bass 2', '', '', ''),
    (34, 39, '3rd Bass', '', '', ''),
    (35, 39, 'MG Oct Bass', '', '', ''),
    (36, 39, 'SlowEnvBass', '', '', ''),
    (37, 39, 'Mild Bass', '', '', ''),
    (38, 39, 'DistEnvBass', '', '', ''),
    (39, 39, 'MG LightBass', '', '', ''),
    (40, 39, 'DistSynBass', '', '', ''),
    (41, 39, 'Rise Bass', '', '', ''),
    (42, 39, 'Cyber Bass', '', '', ''),
    (0, 40, 'Violin', 'Violin', 'Violin', 'Violin'),
    (1, 40, 'Violin Atk', 'Violin Atk', '', ''),
    (8, 40, 'Slow Violin', 'Slow Violin', 'Slow Violin', 'Slow Violin'),
    (0, 41, 'Viola', 'Viola', 'Viola', 'Viola'),
    (1, 41, 'Viola Atk.', 'Viola Atk.', '', ''),
    (0, 42, 'Cello', 'Cello', 'Cello', 'Cello'),
    (1, 42, 'Cello Atk.', 'Cello Atk.', '', ''),
    (0, 43, 'Contrabass', 'Contrabass', 'Contrabass', 'Contrabass'),
    (0, 44, 'Tremolo Str', 'Tremolo Str', 'Tremolo Str', 'Tremolo Str'),
    (2, 44, 'Trem Str.St.', '', '', ''),
    (8, 44, 'Slow Tremolo', 'Slow Tremolo', 'SlowTremolo', ''),
    (9, 44, 'Suspense Str', 'Suspense Str', 'SuspenseStr', ''),
    (10, 44, 'SuspenseStr2', '', '', ''),
    (0, 45, 'PizzicatoStr', 'PizzicatoStr', 'Pizz. Str.', 'Pizzicato'),
    (1, 45, 'Vcs&Cbs Pizz', 'Vcs&Cbs Pizz', '', ''),
    (2, 45, 'Chamber Pizz', 'Chamber Pizz', '', ''),
    (3, 45, 'St.Pizzicato', 'St. Pizzicato', '', ''),
    (8, 45, 'Solo Pizz.', 'Solo Pizz.', '', ''),
    (16, 45, 'Solo Spic.', 'Solo Spic.', '', ''),
    (17, 45, 'StringsSpic.', '', '', ''),
    (0, 46, 'Harp', 'Harp', 'Harp', 'Harp'),
    (1, 46, 'Harp&Strings', '', '', ''),
    (2, 46, 'Harp St.', '', '', ''),
    (8, 46, 'Uillean Harp', '', '', ''),
    (16, 46, 'Synth Harp', 'Synth Harp', '', ''),
    (24, 46, 'Yang Qin', '', '', ''),
    (25, 46, 'Yang Qin 2', '', '', ''),
    (26, 46, 'SynthYangQin', '', '', ''),
    (0, 47, 'Timpani', 'Timpani', 'Timpani', 'Timpani'),
    (0, 48, 'Strings', 'Strings', 'Strings', 'Strings'),
    (1, 48, 'Bright Str', 'Bright Str', 'Strings 2', ''),
    (2, 48, 'ChamberStr', 'ChamberStr', '', ''),
    (3, 48, 'Cello sect.', 'Cello sect.', '', ''),
    (4, 48, 'Bright Str.2', '', '', ''),
    (5, 48, 'Bright Str.3', '', '', ''),
    (6, 48, 'Quad Strings', '', '', ''),
    (7, 48, 'Mild Strings', '', '', ''),
    (8, 48, 'Orchestra', 'Orchestra', 'Orchestra', 'Orchestra'),
    (9, 48, 'Orchestra 2', 'Orchestra 2', 'Orchestra 2', ''),
    (10, 48, 'Tremolo Orch', 'Tremolo Orch', 'TremoloOrch', ''),
    (11, 48, 'Choir Str.', 'Choir Str.', 'Choir Str.', ''),
    (12, 48, 'Strings+Horn', 'Strings+Horn', '', ''),
    (13, 48, 'Str.+Flute', '', '', ''),
    (14, 48, 'Choir Str.2', '', '', ''),
    (15, 48, 'Choir Str.3', '', '', ''),
    (16, 48, 'St. Strings', 'St. Strings', 'St.Strings', ''),
    (17, 48, 'St.Strings 2', '', '', ''),
    (18, 48, 'St.Strings 3', '', '', ''),
    (19, 48, 'Orchestra 3', '', '', ''),
    (20, 48, 'Orchestra 4', '', '', ''),
    (24, 48, 'Velo Strings', 'Velo Strings', 'VeloStrings', ''),
    (32, 48, 'Oct Strings1', 'Oct Strings1', '', ''),
    (33, 48, 'Oct Strings2', 'Oct Strings2', '', ''),
    (34, 48, 'ContraBsSect', '', '', ''),
    (40, 48, '60s Strings', '', '', ''),
    (0, 49, 'Slow Strings', 'SlowStrings', 'SlowStrings', 'SlowStrings'),
    (1, 49, 'SlowStrings2', 'SlowStrings2', 'Slow Str. 2', ''),
    (2, 49, 'SlowStrings3', '', '', ''),
    (8, 49, 'Legato Str.', 'Legato Str.', 'Legato Str.', ''),
    (9, 49, 'Warm Strings', 'Warm Strings', 'WarmStrings', ''),
    (10, 49, 'St.Slow Str.', 'St.Slow Str.', 'St.SlowStr.', ''),
    (11, 49, 'St.Slow Str2', '', '', ''),
    (12, 49, 'S.Str+Choir', '', '', ''),
    (13, 49, 'S.Str+Choir2', '', '', ''),
    (0, 50, 'Syn.Strings1', 'Syn.Strings1', 'SynStrings1', 'SynStrings1'),
    (1, 50, 'OB Strings', 'OB Strings', 'OB Strings', ''),
    (2, 50, 'StackStrings', 'StackStrings', '', ''),
    (3, 50, 'JP Strings', 'JP Strings', '', ''),
    (4, 50, 'Chorus Str.', '', '', ''),
    (8, 50, 'Syn.Strings3', 'Syn.Strings3', 'SynStrings3', 'SynStrings3'),
    (9, 50, 'Syn.Strings4', 'Syn.Strings4', '', ''),
    (10, 50, 'Syn.Strings6', '', '', ''),
    (11, 50, 'Syn.Strings7', '', '', ''),
    (12, 50, 'LoFi Strings', '', '', ''),
    (16, 50, 'High Strings', 'High Strings', '', ''),
    (17, 50, 'Hybrid Str.', 'Hybrid Str.', '', ''),
    (24, 50, 'Tron Strings', 'Tron Strings', '', ''),
    (25, 50, 'Noiz Strings', 'Noiz Strings', '', ''),
    (0, 51, 'Syn.Strings2', 'Syn.Strings2', 'SynStrings2', 'SynStrings2'),
    (1, 51, 'Syn.Strings5', 'Syn.Strings5', '', ''),
    (2, 51, 'JUNO Strings', 'JUNO Strings', '', ''),
    (3, 51, 'FilteredOrch', '', '', ''),
    (4, 51, 'JP Saw Str.', '', '', ''),
    (5, 51, 'Hybrid Str.2', '', '', ''),
    (6, 51, 'DistStrings', '', '', ''),
    (7, 51, 'JUNOFullStr.', '', '', ''),
    (8, 51, 'Air Strings', 'Air Strings', '', ''),
    (9, 51, 'Atk Syn Str.', '', '', ''),
    (10, 51, 'StraightStr.', '', '', ''),
    (0, 52, 'Choir Aahs', 'Choir Aahs', 'Choir Aahs', 'Choir Aahs'),
    (8, 52, 'St.ChoirAahs', 'St.ChoirAahs', 'St.Choir', ''),
    (9, 52, 'Melted Choir', 'Melted Choir', 'Mello Choir', ''),
    (10, 52, 'Church Choir', 'Church Choir', '', ''),
    (11, 52, 'Boys Choir 1', '', '', ''),
    (12, 52, 'Boys Choir 2', '', '', ''),
    (13, 52, 'St.BoysChoir', '', '', ''),
    (14, 52, 'Rich Choir', '', '', ''),
    (16, 52, 'Choir Hahs', 'Choir Hahs', '', ''),
    (24, 52, 'Chorus Lahs', 'Chorus Lahs', '', ''),
    (32, 52, 'Chorus Aahs', 'Chorus Aahs', 'ChoirAahs 2', 'Choir Aahs2'),
    (33, 52, 'Male Aah+Str', 'Male Aah+Str', '', ''),
    (0, 53, 'Voice Oohs', 'Voice Oohs', 'Voice Oohs', 'Voice Oohs'),
    (1, 53, 'Chorus Oohs', '', '', ''),
    (2, 53, 'Voice Oohs 2', '', '', ''),
    (3, 53, 'Chorus Oohs2', '', '', ''),
    (4, 53, 'OohsCodeMaj7', '', '', ''),
    (5, 53, 'OohsCodeSus4', '', '', ''),
    (6, 53, 'Jazz Scat', '', '', ''),
    (8, 53, 'Voice Dahs', 'Voice Dahs', '', ''),
    (9, 53, 'JzVoice Dat', '', '', ''),
    (10, 53, 'JzVoice Bap', '', '', ''),
    (11, 53, 'JzVoice Dow', '', '', ''),
    (12, 53, 'JzVoice Thum', '', '', ''),
    (16, 53, 'VoiceLah Fem', '', '', ''),
    (17, 53, 'ChorusLahFem', '', '', ''),
    (18, 53, 'VoiceLuh Fem', '', '', ''),
    (19, 53, 'ChorusLuhFem', '', '', ''),
    (20, 53, 'VoiceLan Fem', '', '', ''),
    (21, 53, 'ChorusLanFem', '', '', ''),
    (22, 53, 'VoiceAah Fem', '', '', ''),
    (23, 53, 'VoiceUuh Fem', '', '', ''),
    (24, 53, 'Fem Lah&Lan', '', '', ''),
    (32, 53, 'VoiceWah Mal', '', '', ''),
    (33, 53, 'ChorusWahMal', '', '', ''),
    (34, 53, 'VoiceWoh Mal', '', '', ''),
    (35, 53, 'ChorusWohMal', '', '', ''),
    (36, 53, 'VoiceAah Mal', '', '', ''),
    (37, 53, 'VoiceOoh Mal', '', '', ''),
    (40, 53, 'Humming', '', '', ''),
    (0, 54, 'SynVox', 'SynVox', 'SynVox', 'SynVox'),
    (1, 54, 'SynVox 2', '', '', ''),
    (2, 54, 'SynVox 3', '', '', ''),
    (8, 54, 'Syn.Voice', 'Syn.Voice', 'Syn.Voice', ''),
    (9, 54, 'Silent Night', 'Silent Night', '', ''),
    (10, 54, 'Syn.Voice 2', '', '', ''),
    (16, 54, 'VP330 Choir', 'VP330 Choir', '', ''),
    (17, 54, 'Vinyl Choir', 'Vinyl Choir', '', ''),
    (18, 54, 'JX8P Vox', '', '', ''),
    (19, 54, 'Analog Voice', '', '', ''),
    (0, 55, 'OrchestraHit', 'OrchestraHit', 'Orch. Hit', 'Orchest.Hit'),
    (1, 55, 'Bass Hit', '', '', ''),
    (2, 55, '6th Hit', '', '', ''),
    (3, 55, 'Euro Hit', '', '', ''),
    (8, 55, 'Impact Hit', 'Impact Hit', 'Impact Hit', ''),
    (9, 55, 'Philly Hit', 'Philly Hit', 'Philly Hit', ''),
    (10, 55, 'Double Hit', 'Double Hit', 'Double Hit', ''),
    (11, 55, 'Perc. Hit', 'Perc. Hit', '', ''),
    (12, 55, 'Shock Wave', 'Shock Wave', '', ''),
    (13, 55, 'Bounce Hit', '', '', ''),
    (14, 55, 'Drill Hit', '', '', ''),
    (15, 55, 'Thrill Hit', '', '', ''),
    (16, 55, 'Lo Fi Rave', 'Lo Fi Rave', 'Lo Fi Rave', ''),
    (17, 55, 'Techno Hit', 'Techno Hit', '', ''),
    (18, 55, 'Dist. Hit', 'Dist. Hit', '', ''),
    (19, 55, 'Bam Hit', 'Bam Hit', '', ''),
    (20, 55, 'Bit Hit', 'Bit Hit', '', ''),
    (21, 55, 'Bim Hit', 'Bim Hit', '', ''),
    (22, 55, 'Technorg Hit', 'Technorg Hit', '', ''),
    (23, 55, 'Rave Hit', 'Rave Hit', '', ''),
    (24, 55, 'Strings Hit', 'Strings Hit', '', ''),
    (25, 55, 'Stack Hit', 'Stack Hit', '', ''),
    (26, 55, 'Industry Hit', '', '', ''),
    (27, 55, 'Clap Hit', '', '', ''),
    (0, 56, 'Trumpet', 'Trumpet', 'Trumpet', 'Trumpet'),
    (1, 56, 'Trumpet 2', 'Trumpet 2', 'Trumpet 2', ''),
    (2, 56, 'Trumpet', 'Trumpet', '', ''),
    (3, 56, 'Dark Trumpet', '', '', ''),
    (4, 56, 'Trumpet & Nz', '', '', ''),
    (8, 56, 'Flugel Horn', 'Flugel Horn', 'Flugel Horn', ''),
    (16, 56, '4th Trumpets', '4th Trumpets', '', ''),
    (24, 56, 'Bright Tp.', 'Bright Tp.', 'Bright Tp.', ''),
    (25, 56, 'Warm Tp.', 'Warm Tp.', 'Warm Tp.', ''),
    (26, 56, 'Warm Tp.2', '', '', ''),
    (27, 56, 'Twin Tp.', '', '', ''),
    (32, 56, 'Syn. Trumpet', 'Syn. Trumpet', '', ''),
    (0, 57, 'Trombone', 'Trombone', 'Trombone', 'Trombone'),
    (1, 57, 'Trombone 2', 'Trombone 2', 'Trombone 2', 'Trombone 2'),
    (2, 57, 'Twin bones', 'Twin bones', '', ''),
    (3, 57, 'Bones & Tuba', '', '', ''),
    (4, 57, 'Bright Tb', '', '', ''),
    (8, 57, 'Bs. Trombone', 'Bs. Trombone', '', ''),
    (16, 57, 'Euphonium', '', '', ''),
    (0, 58, 'Tuba', 'Tuba', 'Tuba', 'Tuba'),
    (1, 58, 'Tuba 2', 'Tuba 2', 'Tuba 2', ''),
    (8, 58, 'Tuba + Horn', '', '', ''),
    (0, 59, 'MutedTrumpet', 'MutedTrumpet', 'Muted Tp.', 'MuteTrumpet'),
    (1, 59, 'Cup Mute Tp', '', '', ''),
    (2, 59, 'MuteTrumpet2', '', '', ''),
    (3, 59, 'MuteTrumpet3', '', '', ''),
    (8, 59, 'Muted Horns', 'Muted Horns', '', ''),
    (0, 60, 'French Horns', 'French Horns', 'FrenchHorns', 'French Horn'),
    (1, 60, 'Fr.Horn 2', 'Fr.Horn 2', 'Fr.Horn 2', 'Fr.Horn 2'),
    (2, 60, 'Horn + Orche', 'Horn + Orche', '', ''),
    (3, 60, 'Wide FreHrns', 'Wide FreHrns', '', ''),
    (8, 60, 'F.Hrn Slow', 'F.Hrn Slow', 'Fr.HornSolo', ''),
    (9, 60, 'Dual Horns', 'Dual Horns', '', ''),
    (16, 60, 'Synth Horn', 'Synth Horn', 'Horn Orch', ''),
    (24, 60, 'F.Horn Rip', 'F.Horn Rip', '', ''),
    (0, 61, 'Brass 1', 'Brass 1', 'Brass 1', 'Brass 1'),
    (1, 61, 'Brass ff', 'Brass ff', '', ''),
    (2, 61, 'Bones Sect.', 'Bones Sect.', '', ''),
    (3, 61, 'St. Brass ff', '', '', ''),
    (4, 61, 'Quad Brass1', '', '', ''),
    (5, 61, 'Quad Brass2', '', '', ''),
    (8, 61, 'Brass 2', 'Brass 2', 'Brass 2', 'Brass 2'),
    (9, 61, 'Brass 3', 'Brass 3', '', ''),
    (10, 61, 'Brass sfz', 'Brass sfz', '', ''),
    (12, 61, 'Brass sfz 2', '', '', ''),
    (14, 61, 'FatPop Brass', '', '', ''),
    (16, 61, 'Brass Fall', 'Brass Fall', 'Brass Fall', ''),
    (17, 61, 'Trumpet Fall', 'Trumpet Fall', '', ''),
    (24, 61, 'Octave Brass', 'Octave Brass', '', ''),
    (25, 61, 'Brass + Reed', 'Brass + Reed', '', ''),
    (26, 61, 'Fat + Reed', '', '', ''),
    (32, 61, 'Orch Brass', '', '', ''),
    (33, 61, 'Orch Brass 2', '', '', ''),
    (35, 61, 'St.FatPopBrs', '', '', ''),
    (36, 61, 'St.Orch Brs', '', '', ''),
    (37, 61, 'St.Orch Brs2', '', '', ''),
    (38, 61, 'St.Orch Brs3', '', '', ''),
    (0, 62, 'Synth Brass1', 'SynthBrass1', 'SynthBrass1', 'Syn.Brass 1'),
    (1, 62, 'JUNO Brass', 'JUNO Brass', 'Poly Brass', ''),
    (2, 62, 'Stack Brass', 'StackBrass', '', ''),
    (3, 62, 'SH-5 Brass', 'SH-5 Brass', '', ''),
    (4, 62, 'MKS Brass', 'MKS Brass', '', ''),
    (5, 62, 'Jump Brass', '', '', ''),
    (8, 62, 'Pro Brass', 'Pro Brass', 'Syn.Brass 3', 'Syn.Brass 3'),
    (9, 62, 'P5 Brass', 'P5 Brass', 'Quack Brass', ''),
    (10, 62, 'OrchSynBrass', '', '', ''),
    (16, 62, 'Oct SynBrass', 'Oct SynBrass', 'OctaveBrass', 'Analog Brs1'),
    (17, 62, 'Hybrid Brass', 'Hybrid Brass', '', ''),
    (18, 62, 'OctSynBrass2', '', '', ''),
    (19, 62, 'BPF Brass', '', '', ''),
    (0, 63, 'Synth Brass2', 'Synth Brass 2', 'Syn.Brass 2', 'Syn.Brass 2'),
    (1, 63, 'Soft Brass', 'Soft Brass', 'Soft Brass', ''),
    (2, 63, 'Warm Brass', 'Warm Brass', '', ''),
    (3, 63, 'Synth Brass3', '', '', ''),
    (4, 63, 'Sync Brass', '', '', ''),
    (5, 63, 'Fat SynBrass', '', '', ''),
    (6, 63, 'DeepSynBrass', '', '', ''),
    (8, 63, 'SynBrass sfz', 'SynBrass sfz', 'Syn.Brass 4', 'Syn.Brass 4'),
    (9, 63, 'OB Brass', 'OB Brass', '', ''),
    (10, 63, 'Reso Brass', 'Reso Brass', '', ''),
    (11, 63, 'DistSqrBrass', '', '', ''),
    (12, 63, 'JP8000SawBrs', '', '', ''),
    (16, 63, 'Velo Brass 1', 'Velo Brass 1', 'VeloBrass 1', 'Analog Brs2'),
    (17, 63, 'Transbrass', 'Transbrass', 'VeloBrass 2', ''),
    (0, 64, 'Soprano Sax', 'Soprano Sax', 'Soprano Sax', 'Soprano Sax'),
    (8, 64, 'Soprano Exp.', 'Soprano Exp.', '', ''),
    (0, 65, 'Alto Sax', 'Alto Sax', 'Alto Sax', 'Alto Sax'),
    (8, 65, 'AltoSax Exp.', 'AltoSax Exp.', 'Hyper Alto', ''),
    (9, 65, 'Grow Sax', 'Grow Sax', '', ''),
    (16, 65, 'AltoSax + Tp', 'AltoSax + Tp', '', ''),
    (17, 65, 'Sax Section', '', '', ''),
    (0, 66, 'Tenor Sax', 'Tenor Sax', 'Tenor Sax', 'Tenor Sax'),
    (1, 66, 'Tenor Sax', 'Tenor Sax', '', ''),
    (8, 66, 'BreathyTn.', 'BreathyTn.', 'BreathyTnr.', ''),
    (9, 66, 'St.Tenor Sax', 'St. Tenor Sax', '', ''),
    (0, 67, 'Baritone Sax', 'Baritone Sax', 'BaritoneSax', 'BaritoneSax'),
    (1, 67, 'Bari. Sax', 'Bari. Sax', '', ''),
    (8, 67, 'Bari & Tenor', '', '', ''),
    (0, 68, 'Oboe', 'Oboe', 'Oboe', 'Oboe'),
    (8, 68, 'Oboe Exp.', 'Oboe Exp.', '', ''),
    (16, 68, 'Multi Reed', 'Multi Reed', '', ''),
    (0, 69, 'English Horn', 'English Horn', 'EnglishHorn', 'EnglishHorn'),
    (0, 70, 'Bassoon', 'Bassoon', 'Bassoon', 'Bassoon'),
    (0, 71, 'Clarinet', 'Clarinet', 'Clarinet', 'Clarinet'),
    (8, 71, 'Bs Clarinet', 'Bs Clarinet', 'Bs Clarinet', ''),
    (16, 71, 'Multi Wind', 'Multi Wind', '', ''),
    (17, 71, 'Quad Wind', '', '', ''),
    (0, 72, 'Piccolo', 'Piccolo', 'Piccolo', 'Piccolo'),
    (1, 72, 'Piccolo', 'Piccolo', '', ''),
    (8, 72, 'Nay', 'Nay', '', ''),
    (9, 72, 'Nay Tremolo', 'Nay Tremolo', '', ''),
    (16, 72, 'Di', 'Di', '', ''),
    (0, 73, 'Flute', 'Flute', 'Flute', 'Flute'),
    (1, 73, 'Flute 2', 'Flute 2', '', ''),
    (2, 73, 'Flute Exp.', 'Flute Exp.', '', ''),
    (3, 73, 'Flt Travelso', 'Flt Travelso', '', ''),
    (8, 73, 'Flute + Vln', 'Flute + Vln', '', ''),
    (9, 73, 'Pipe & Reed', '', '', ''),
    (16, 73, 'Tron Flute', 'Tron Flute', '', ''),
    (17, 73, 'Indian Flute', '', '', ''),
    (0, 74, 'Recorder', 'Recorder', 'Recorder', 'Recorder'),
    (0, 75, 'Pan Flute', 'Pan Flute', 'Pan Flute', 'Pan Flute'),
    (8, 75, 'Kawala', 'Kawala', 'Kawala', ''),
    (16, 75, 'Zampona', 'Zampona', '', ''),
    (17, 75, 'Zampona Atk', 'Zampona Atk', '', ''),
    (24, 75, 'Tin Whistle', '', '', ''),
    (25, 75, 'TinWhtsle Nm', '', '', ''),
    (26, 75, 'TinWhtsle Or', '', '', ''),
    (0, 76, 'Bottle Blow', 'Bottle Blow', 'Bottle Blow', 'Bottle Blow'),
    (0, 77, 'Shakuhachi', 'Shakuhachi', 'Shakuhachi', 'Shakuhachi'),
    (1, 77, 'Shakuhachi', 'Shakuhachi', '', ''),
    (0, 78, 'Whistle', 'Whistle', 'Whistle', 'Whistle'),
    (1, 78, 'Whistle 2', 'Whistle 2', '', ''),
    (0, 79, 'Ocarina', 'Ocarina', 'Ocarina', 'Ocarina'),
    (0, 80, 'Square Wave', 'Square Wave', 'Square Wave', 'Square Wave'),
    (1, 80, 'MG Square', 'MG Square', 'Square', 'Square'),
    (2, 80, 'Hollow Mini', 'Hollow Mini', 'Hollow Mini', ''),
    (3, 80, 'Mellow FM', 'Mellow FM', 'Mellow FM', ''),
    (4, 80, 'CC Solo', 'CC Solo', 'CC Solo', ''),
    (5, 80, 'Shmoog', 'Shmoog', 'Shmoog', ''),
    (6, 80, 'LM Square', 'LM Square', 'LM Square', ''),
    (7, 80, 'JP8000 TWM', '', '', ''),
    (8, 80, '2600 Sine', '2600 Sine', 'Sine Wave', 'Sine Wave'),
    (9, 80, 'Sine Lead', 'Sine Lead', '', ''),
    (10, 80, 'KG Lead', 'KG Lead', '', ''),
    (11, 80, 'Twin Sine', '', '', ''),
    (16, 80, 'P5 Square', 'P5 Square', '', ''),
    (17, 80, 'OB Square', 'OB Square', '', ''),
    (18, 80, 'JP-8 Square', 'JP-8 Square', '', ''),
    (19, 80, 'Dist Square', '', '', ''),
    (20, 80, '303SquarDst1', '', '', ''),
    (21, 80, '303SquarDst2', '', '', ''),
    (22, 80, 'Mix Sqr', '', '', ''),
    (23, 80, 'Dual Sqr&Saw', '', '', ''),
    (24, 80, 'Pulse Lead', 'Pulse Lead', '', ''),
    (25, 80, 'JP8 PulseLd1', 'JP8 PulseLd1', '', ''),
    (26, 80, 'JP8 PulseLd2', 'JP8 PulseLd2', '', ''),
    (27, 80, 'MG Reso. Pls', 'MG Reso. Pls', '', ''),
    (28, 80, 'JP8 PulseLd3', '', '', ''),
    (29, 80, '260RingLead', '', '', ''),
    (30, 80, '303DistLead', '', '', ''),
    (31, 80, 'JP8000DistLd', '', '', ''),
    (32, 80, 'HipHop SinLd', '', '', ''),
    (33, 80, 'HipHop SqrLd', '', '', ''),
    (34, 80, 'HipHop PlsLd', '', '', ''),
    (35, 80, 'Flux Pulse', '', '', ''),
    (0, 81, 'Saw Wave', 'Saw Wave', 'Saw Wave', 'Saw Wave'),
    (1, 81, 'OB2 Saw', 'OB2 Saw', 'Saw', 'Saw'),
    (2, 81, 'Pulse Saw', 'Pulse Saw', 'Pulse Saw', ''),
    (3, 81, 'Feline GR', 'Feline GR', 'Feline GR', ''),
    (4, 81, 'Big Lead', 'Big Lead', 'Big Lead', ''),
    (5, 81, 'Velo Lead', 'Velo Lead', 'Velo Lead', ''),
    (6, 81, 'GR-300', 'GR-300', 'GR-300', ''),
    (7, 81, 'LA Saw', 'LA Saw', 'LA Saw', ''),
    (8, 81, 'Doctor Solo', 'Doctor Solo', 'Doctor Solo', 'Doctor Solo'),
    (9, 81, 'Fat Saw Lead', 'Fat Saw Lead', '', ''),
    (10, 81, 'JP8000 Saw', '', '', ''),
    (11, 81, 'D-50 Fat Saw', 'D-50 Fat Saw', '', ''),
    (12, 81, 'OB DoubleSaw', '', '', ''),
    (13, 81, 'JP DoubleSaw', '', '', ''),
    (14, 81, 'FatSawLead 2', '', '', ''),
    (15, 81, 'JP SuperSaw', '', '', ''),
    (16, 81, 'Waspy Synth', 'Waspy Synth', 'Waspy Synth', ''),
    (17, 81, 'PM Lead', 'PM Lead', '', ''),
    (18, 81, 'CS Saw Lead', 'CS Saw Lead', '', ''),
    (24, 81, 'MG Saw 1', 'MG Saw 1', '', ''),
    (25, 81, 'MG Saw 2', 'MG Saw 2', '', ''),
    (26, 81, 'OB Saw 1', 'OB Saw 1', '', ''),
    (27, 81, 'OB Saw 2', 'OB Saw 2', '', ''),
    (28, 81, 'D-50 Saw', 'D-50 Saw', '', ''),
    (29, 81, 'SH-101 Saw', 'SH-101 Saw', '', ''),
    (30, 81, 'CS Saw', 'CS Saw', '', ''),
    (31, 81, 'MG Saw Lead', 'MG Saw Lead', '', ''),
    (32, 81, 'OB Saw Lead', 'OB Saw Lead', '', ''),
    (33, 81, 'P5 Saw Lead', 'P5 Saw Lead', '', ''),
    (34, 81, 'MG unison', 'MG unison', '', ''),
    (35, 81, 'Oct Saw Lead', 'Oct Saw Lead', '', ''),
    (36, 81, 'Natural Lead', '', '', ''),
    (40, 81, 'SequenceSaw1', 'SequenceSaw1', '', ''),
    (41, 81, 'SequenceSaw2', 'SequenceSaw2', '', ''),
    (42, 81, 'Reso Saw', 'Reso Saw', '', ''),
    (43, 81, 'Cheese Saw 1', 'Cheese Saw 1', '', ''),
    (44, 81, 'Cheese Saw 2', 'Cheese Saw 2', '', ''),
    (45, 81, 'Rhythmic Saw', 'Rhythmic Saw', '', ''),
    (46, 81, 'SequencedSaw', '', '', ''),
    (47, 81, 'Techno Saw', '', '', ''),
    (0, 82, 'Syn.Calliope', 'Syn.Calliope', 'SynCalliope', 'SynCalliope'),
    (1, 82, 'Vent Synth', 'Vent Synth', 'Vent Synth', ''),
    (2, 82, 'Pure PanLead', 'Pure PanLead', 'PurePanLead', ''),
    (8, 82, 'LM Pure Lead', '', '', ''),
    (9, 82, 'LM Blow Lead', '', '', ''),
    (0, 83, 'Chiffer Lead', 'Chiffer Lead', 'ChifferLead', 'ChifferLead'),
    (1, 83, 'TB Lead', 'TB Lead', '', ''),
    (2, 83, 'Hybrid Lead', '', '', ''),
    (3, 83, 'Unison SqrLd', '', '', ''),
    (4, 83, 'FatSolo Lead', '', '', ''),
    (5, 83, 'ForcefulLead', '', '', ''),
    (6, 83, 'Oct.UnisonLd', '', '', ''),
    (7, 83, 'Unison SawLd', '', '', ''),
    (8, 83, 'Mad Lead', 'Mad Lead', '', ''),
    (9, 83, 'CrowdingLead', '', '', ''),
    (10, 83, 'Double Sqr.', '', '', ''),
    (0, 84, 'Charang', 'Charang', 'Charang', 'Charang'),
    (1, 84, 'Wire Lead', '', '', ''),
    (2, 84, 'FB.Charang', '', '', ''),
    (3, 84, 'Fat GR Lead', '', '', ''),
    (4, 84, 'Windy GR Ld', '', '', ''),
    (5, 84, 'Mellow GR Ld', '', '', ''),
    (6, 84, 'GR & Pulse', '', '', ''),
    (8, 84, 'Dist.Lead', 'Dist.Lead', 'Dist.Lead', ''),
    (9, 84, 'Acid Guitar1', 'Acid Guitar1', '', ''),
    (10, 84, 'Acid Guitar2', 'Acid Guitar2', '', ''),
    (11, 84, 'Dance Dst.Gt', '', '', ''),
    (12, 84, 'DanceDst.Gt2', '', '', ''),
    (16, 84, 'P5 Sync Lead', 'P5 Sync Lead', '', ''),
    (17, 84, 'Fat SyncLead', 'Fat Sync Lead', '', ''),
    (18, 84, 'Rock Lead', 'Rock Lead', '', ''),
    (19, 84, '5th DecaSync', '5th DecaSync', '', ''),
    (20, 84, 'Dirty Sync', 'Dirty Sync', '', ''),
    (21, 84, 'DualSyncLead', '', '', ''),
    (22, 84, 'LA Brass Ld', '', '', ''),
    (24, 84, 'JUNO Sub Osc', 'JUNO Sub Osc', '', ''),
    (25, 84, '2600 Sub Osc', '', '', ''),
    (26, 84, 'JP8000Fd Osc', '', '', ''),
    (0, 85, 'Solo Vox', 'Solo Vox', 'Solo Vox', 'Solo Vox'),
    (1, 85, 'Solo Vox 2', '', '', ''),
    (8, 85, 'Vox Lead', 'Vox Lead', '', ''),
    (9, 85, 'LFO Vox', 'LFO Vox', '', ''),
    (10, 85, 'Vox Lead 2', '', '', ''),
    (0, 86, '5th Saw Wave', '5th Saw Wave', '5th Saw', '5th Saw'),
    (1, 86, 'Big Fives', 'Big Fives', 'Big Fives', ''),
    (2, 86, '5th Lead', '5th Lead', '', ''),
    (3, 86, '5th Ana.Clav', '5th Ana.Clav', '', ''),
    (4, 86, '5th Pulse', '', '', ''),
    (5, 86, 'JP 5th Saw', '', '', ''),
    (6, 86, 'JP8000 5thFB', '', '', ''),
    (8, 86, '4th Lead', '4th Lead', '', ''),
    (0, 87, 'Bass & Lead', 'Bass & Lead', 'Bass & Lead', 'Bass & Lead'),
    (1, 87, 'Big & Raw', 'Big & Raw', 'Big & Raw', ''),
    (2, 87, 'Fat & Perky', 'Fat & Perky', 'Fat & Perky', ''),
    (3, 87, 'JUNO Rave', 'JUNO Rave', '', ''),
    (4, 87, 'JP8 BsLead 1', 'JP8 BsLead 1', '', ''),
    (5, 87, 'JP8 BsLead 2', 'JP8 BsLead 2', '', ''),
    (6, 87, 'SH-5 Bs.Lead', 'SH-5 Bs.Lead', '', ''),
    (7, 87, 'Delayed Lead', '', '', ''),
    (0, 88, 'Fantasia', 'Fantasia', 'Fantasia', 'Fantasia'),
    (1, 88, 'Fantasia 2', 'Fantasia 2', 'Fantasia 2', ''),
    (2, 88, 'New Age Pad', 'New Age Pad', '', ''),
    (3, 88, 'Bell Heaven', 'Bell Heaven', '', ''),
    (4, 88, 'Fantasia 3', '', '', ''),
    (5, 88, 'Fantasia 4', '', '', ''),
    (6, 88, 'After D !', '', '', ''),
    (7, 88, '260HarmPad', '', '', ''),
    (0, 89, 'Warm Pad', 'Warm Pad', 'Warm Pad', 'Warm Pad'),
    (1, 89, 'Thick Matrix', 'Thick Matrix', 'Thick Pad', ''),
    (2, 89, 'Horn Pad', 'Horn Pad', 'Horn Pad', ''),
    (3, 89, 'Rotary Strng', 'Rotary Strng', 'RotaryStrng', ''),
    (4, 89, 'OB Soft Pad', 'OB Soft Pad', 'Soft Pad', ''),
    (5, 89, 'Sine Pad', '', '', ''),
    (6, 89, 'OB Soft Pad2', '', '', ''),
    (8, 89, 'Octave Pad', 'Octave Pad', '', ''),
    (9, 89, 'Stack Pad', 'Stack Pad', '', ''),
    (10, 89, 'Human Pad', '', '', ''),
    (11, 89, 'Sync Brs.Pad', '', '', ''),
    (12, 89, 'Oct.PWM Pad', '', '', ''),
    (13, 89, 'JP Soft Pad', '', '', ''),
    (0, 90, 'Polysynth', 'Polysynth', 'Polysynth', 'Polysynth'),
    (1, 90, "80's PolySyn", "80's PolySyn", "80'sPolySyn", ''),
    (2, 90, 'Polysynth 2', 'Polysynth 2', '', ''),
    (3, 90, 'Poly King', 'Poly King', '', ''),
    (4, 90, 'Super Poly', '', '', ''),
    (8, 90, 'Power Stack', 'Power Stack', '', ''),
    (9, 90, 'Octave Stack', 'Octave Stack', '', ''),
    (10, 90, 'Reso Stack', 'Reso Stack', '', ''),
    (11, 90, 'Techno Stack', 'Techno Stack', '', ''),
    (12, 90, 'Pulse Stack', '', '', ''),
    (13, 90, 'TwinOct.Rave', '', '', ''),
    (14, 90, 'Oct.Rave', '', '', ''),
    (15, 90, 'Happy Synth', '', '', ''),
    (16, 90, 'ForwardSweep', '', '', ''),
    (17, 90, 'ReverseSweep', '', '', ''),
    (24, 90, 'Minor Rave', '', '', ''),
    (0, 91, 'Space Voice', 'Space Voice', 'Space Voice', 'Space Voice'),
    (1, 91, 'Heaven II', 'Heaven II', 'Heaven II', ''),
    (2, 91, 'SC Heaven', 'SC Heaven', '', ''),
    (3, 91, 'Itopia', '', '', ''),
    (4, 91, 'Water Space', '', '', ''),
    (5, 91, 'Cold Space', '', '', ''),
    (6, 91, 'Noise Peaker', '', '', ''),
    (7, 91, 'Bamboo Hit', '', '', ''),
    (8, 91, 'Cosmic Voice', 'Cosmic Voice', '', ''),
    (9, 91, 'Auh Vox', 'Auh Vox', '', ''),
    (10, 91, 'AuhAuh', 'AuhAuh', '', ''),
    (11, 91, 'Vocorderman', 'Vocorderman', '', ''),
    (12, 91, 'Holy Voices', '', '', ''),
    (0, 92, 'Bowed Glass', 'Bowed Glass', 'Bowed Glass', 'Bowed Glass'),
    (1, 92, 'SoftBellPad', 'SoftBellPad', '', ''),
    (2, 92, 'JP8 Sqr Pad', 'JP8 Sqr Pad', '', ''),
    (3, 92, '7thBelPad', '7thBelPad', '', ''),
    (4, 92, 'Steel Glass', '', '', ''),
    (5, 92, 'Bottle Stack', '', '', ''),
    (0, 93, 'Metal Pad', 'Metal Pad', 'Metal Pad', 'Metal Pad'),
    (1, 93, 'Tine Pad', 'Tine Pad', 'Tine Pad', ''),
    (2, 93, 'Panner Pad', 'Panner Pad', 'Panner Pad', ''),
    (3, 93, 'Steel Pad', '', '', ''),
    (4, 93, 'Special Rave', '', '', ''),
    (5, 93, 'Metal Pad 2', '', '', ''),
    (0, 94, 'Halo Pad', 'Halo Pad', 'Halo Pad', 'Halo Pad'),
    (1, 94, 'Vox Pad', 'Vox Pad', '', ''),
    (2, 94, 'Vox Sweep', 'Vox Sweep', '', ''),
    (8, 94, 'Horror Pad', 'Horror Pad', '', ''),
    (9, 94, 'SynVox Pad', '', '', ''),
    (10, 94, 'SynVox Pad 2', '', '', ''),
    (11, 94, 'Breath&Rise', '', '', ''),
    (12, 94, 'Tears Voices', '', '', ''),
    (0, 95, 'Sweep Pad', 'Sweep Pad', 'Sweep Pad', 'Sweep Pad'),
    (1, 95, 'Polar Pad', 'Polar Pad', 'Polar Pad', ''),
    (2, 95, 'Ambient BPF', '', '', ''),
    (3, 95, 'Sync Pad', '', '', ''),
    (4, 95, 'Warriors', '', '', ''),
    (8, 95, 'Converge', 'Converge', 'Converge', ''),
    (9, 95, 'Shwimmer', 'Shwimmer', 'Shwimmer', ''),
    (10, 95, 'Celestial Pd', 'Celestial Pd', 'CelestialPd', ''),
    (11, 95, 'Bag Sweep', 'Bag Sweep', '', ''),
    (12, 95, 'Sweep Pipe', '', '', ''),
    (13, 95, 'Sweep Stack', '', '', ''),
    (14, 95, 'Deep Sweep', '', '', ''),
    (15, 95, 'Stray Pad', '', '', ''),
    (0, 96, 'Ice Rain', 'Ice Rain', 'Ice Rain', 'Ice Rain'),
    (1, 96, 'Harmo Rain', 'Harmo Rain', 'Harmo Rain', ''),
    (2, 96, 'African wood', 'African wood', 'AfricanWood', ''),
    (3, 96, 'Anklung Pad', 'Anklung Pad', '', ''),
    (4, 96, 'Rattle Pad', 'Rattle Pad', '', ''),
    (5, 96, 'Saw Impulse', '', '', ''),
    (6, 96, 'Strange Str.', '', '', ''),
    (7, 96, 'FastFWD Pad', '', '', ''),
    (8, 96, 'Clavi Pad', 'Clavi Pad', 'Clavi Pad', ''),
    (9, 96, 'EP Pad', '', '', ''),
    (10, 96, 'Tambra Pad', '', '', ''),
    (11, 96, 'CP Pad', '', '', ''),
    (0, 97, 'Soundtrack', 'Soundtrack', 'Soundtrack', 'Soundtrack'),
    (1, 97, 'Ancestral', 'Ancestral', 'Ancestral', ''),
    (2, 97, 'Prologue', 'Prologue', 'Prologue', ''),
    (3, 97, 'Prologue 2', 'Prologue 2', '', ''),
    (4, 97, 'Hols Strings', 'Hols Strings', '', ''),
    (5, 97, 'HistoryWave', '', '', ''),
    (8, 97, 'Rave', 'Rave', 'Rave', ''),
    (0, 98, 'Crystal', 'Crystal', 'Crystal', 'Crystal'),
    (1, 98, 'Syn Mallet', 'Syn Mallet', 'Syn Mallet', 'Syn Mallet'),
    (2, 98, 'Soft Crystal', 'Soft Crystal', 'SoftCrystal', ''),
    (3, 98, 'Round Glock', 'Round Glock', 'Round Glock', ''),
    (4, 98, 'Loud Glock', 'Loud Glock', 'Loud Glock', ''),
    (5, 98, 'GlockenChime', 'GlockenChime', 'GlocknChime', ''),
    (6, 98, 'Clear Bells', 'Clear Bells', 'Clear Bells', ''),
    (7, 98, 'ChristmasBel', 'ChristmasBel', "X'mas Bell", ''),
    (8, 98, 'Vibra Bells', 'Vibra Bells', 'Vibra Bells', ''),
    (9, 98, 'Digi Bells', 'Digi Bells', 'Digi Bells', ''),
    (10, 98, 'Music Bell', 'Music Bell', '', ''),
    (11, 98, 'Analog Bell', 'Analog Bell', '', ''),
    (12, 98, 'Blow Bell', '', '', ''),
    (13, 98, 'Hyper Bell', '', '', ''),
    (16, 98, 'Choral Bells', 'Choral Bells', 'ChoralBells', ''),
    (17, 98, 'Air Bells', 'Air Bells', 'Air Bells', ''),
    (18, 98, 'Bell Harp', 'Bell Harp', 'Bell Harp', ''),
    (19, 98, 'Gamelimba', 'Gamelimba', 'Gamelimba', ''),
    (20, 98, 'JUNO Bell', 'JUNO Bell', '', ''),
    (21, 98, 'JP Bell', '', '', ''),
    (22, 98, 'Pizz Bell', '', '', ''),
    (23, 98, 'Bottom Bell', '', '', ''),
    (0, 99, 'Atmosphere', 'Atmosphere', 'Atmosphere', 'Atmosphere'),
    (1, 99, 'Warm Atmos', 'Warm Atmos', 'Warm Atmos', ''),
    (2, 99, 'Nylon Harp', 'Nylon Harp', 'Nylon Harp', ''),
    (3, 99, 'Harpvox', 'Harpvox', 'Harpvox', ''),
    (4, 99, 'HollowReleas', 'HollowReleas', 'HollowRels.', ''),
    (5, 99, 'Nylon+Rhodes', 'Nylon+Rhodes', 'NylonRhodes', ''),
    (6, 99, 'Ambient Pad', 'Ambient Pad', 'Ambient Pad', ''),
    (7, 99, 'Invisible', 'Invisible', '', ''),
    (8, 99, 'Pulsey Key', 'Pulsey Key', '', ''),
    (9, 99, 'Noise Piano', 'Noise Piano', '', ''),
    (10, 99, 'Heaven Atmos', '', '', ''),
    (11, 99, 'Tambra Atmos', '', '', ''),
    (0, 100, 'Brightness', 'Brightness', 'Brightness', 'Brightness'),
    (1, 100, 'Shining Star', 'Shining Star', '', ''),
    (2, 100, 'OB Stab', 'OB Stab', '', ''),
    (3, 100, 'Brass Star', '', '', ''),
    (4, 100, 'Choir Stab', '', '', ''),
    (5, 100, 'D-50 Retour', '', '', ''),
    (6, 100, 'SouthernWind', '', '', ''),
    (7, 100, 'SymbolicBell', '', '', ''),
    (8, 100, 'Org Bell', 'Org Bell', '', ''),
    (0, 101, 'Goblin', 'Goblin', 'Goblin', 'Goblin'),
    (1, 101, 'Goblinson', 'Goblinson', 'Goblinson', ''),
    (2, 101, "50's Sci-Fi", "50's Sci-Fi", "50's Sci-Fi", ''),
    (3, 101, 'Abduction', 'Abduction', '', ''),
    (4, 101, 'Auhbient', 'Auhbient', '', ''),
    (5, 101, 'LFO Pad', 'LFO Pad', '', ''),
    (6, 101, 'Random Str', 'Random Str', '', ''),
    (7, 101, 'Random Pad', 'Random Pad', '', ''),
    (8, 101, 'LowBirds Pad', 'LowBirds Pad', '', ''),
    (9, 101, 'Falling Down', 'Falling Down', '', ''),
    (10, 101, 'LFO RAVE', 'LFO RAVE', '', ''),
    (11, 101, 'LFO Horror', 'LFO Horror', '', ''),
    (12, 101, 'LFO Techno', 'LFO Techno', '', ''),
    (13, 101, 'Alternative', 'Alternative', '', ''),
    (14, 101, 'UFO FX', 'UFO FX', '', ''),
    (15, 101, 'Gargle Man', 'Gargle Man', '', ''),
    (16, 101, 'Sweep FX', 'Sweep FX', '', ''),
    (17, 101, 'LM Has Come', '', '', ''),
    (18, 101, 'FallinInsect', '', '', ''),
    (19, 101, 'LFO Oct.Rave', '', '', ''),
    (20, 101, 'Just Before', '', '', ''),
    (21, 101, 'RND Fl.Chord', '', '', ''),
    (22, 101, 'RandomEnding', '', '', ''),
    (23, 101, 'Random Sine', '', '', ''),
    (24, 101, 'EatingFilter', '', '', ''),
    (25, 101, 'Noise&SawHit', '', '', ''),
    (26, 101, 'Pour Magic', '', '', ''),
    (27, 101, 'DancingDrill', '', '', ''),
    (28, 101, 'Dirty Stack', '', '', ''),
    (29, 101, 'Big Blue', '', '', ''),
    (30, 101, 'Static Hit', '', '', ''),
    (31, 101, 'Atl.Mod.FX', '', '', ''),
    (32, 101, 'Acid Copter', '', '', ''),
    (0, 102, 'Echo Drops', 'Echo Drops', 'Echo Drops', 'Echo Drops'),
    (1, 102, 'Echo Bell', 'Echo Bell', 'Echo Bell', 'Echo Bell'),
    (2, 102, 'Echo Pan', 'Echo Pan', 'Echo Pan', 'Echo Pan'),
    (3, 102, 'Echo Pan 2', 'Echo Pan 2', 'Echo Pan 2', ''),
    (4, 102, 'Big Panner', 'Big Panner', 'Big Panner', ''),
    (5, 102, 'Reso Panner', 'Reso Panner', 'Reso Panner', ''),
    (6, 102, 'Water Piano', 'Water Piano', 'Water Piano', ''),
    (7, 102, 'Echo SynBass', '', '', ''),
    (8, 102, 'Pan Sequence', 'Pan Sequence', '', ''),
    (9, 102, 'Aqua', 'Aqua', '', ''),
    (10, 102, 'Panning Lead', '', '', ''),
    (11, 102, 'PanningBrass', '', '', ''),
    (0, 103, 'Star Theme', 'Star Theme', 'Star Theme', 'Star Theme'),
    (1, 103, 'Star Theme 2', 'Star Theme 2', 'StarTheme 2', ''),
    (2, 103, 'Star Mind', '', '', ''),
    (3, 103, 'Star Dust', '', '', ''),
    (4, 103, 'Rep.Trance', '', '', ''),
    (5, 103, 'Etherality', '', '', ''),
    (6, 103, 'Mystic Pad', '', '', ''),
    (8, 103, 'Dream Pad', 'Dream Pad', '', ''),
    (9, 103, 'Silky Pad', 'Silky Pad', '', ''),
    (10, 103, 'Dream Pad 2', '', '', ''),
    (11, 103, 'Silky Pad 2', '', '', ''),
    (16, 103, 'New Century', 'New Century', '', ''),
    (17, 103, '7th Atmos.', '7th Atmos.', '', ''),
    (18, 103, 'Galaxy Way', 'Galaxy Way', '', ''),
    (19, 103, 'Rising OSC.', '', '', ''),
    (0, 104, 'Sitar', 'Sitar', 'Sitar', 'Sitar'),
    (1, 104, 'Sitar 2', 'Sitar 2', 'Sitar 2', 'Sitar 2'),
    (2, 104, 'Detune Sitar', 'Detune Sitar', 'DetuneSitar', ''),
    (3, 104, 'Sitar 3', 'Sitar 3', '', ''),
    (4, 104, 'Sitar/Drone', '', '', ''),
    (5, 104, 'Sitar 4', '', '', ''),
    (8, 104, 'Tambra', 'Tambra', 'Tambra', ''),
    (16, 104, 'Tamboura', 'Tamboura', 'Tamboura', ''),
    (0, 105, 'Banjo', 'Banjo', 'Banjo', 'Banjo'),
    (1, 105, 'Muted Banjo', 'Muted Banjo', 'Muted Banjo', ''),
    (8, 105, 'Rabab', 'Rabab', 'Rabab', ''),
    (9, 105, 'San Xian', 'San Xian', '', ''),
    (16, 105, 'Gopichant', 'Gopichant', 'Gopichant', ''),
    (24, 105, 'Oud', 'Oud', 'Oud', ''),
    (28, 105, 'Oud+Strings', 'Oud+Strings', '', ''),
    (32, 105, 'Pi Pa', 'Pi Pa', '', ''),
    (0, 106, 'Shamisen', 'Shamisen', 'Shamisen', 'Shamisen'),
    (1, 106, 'Tsugaru', 'Tsugaru', 'Tsugaru', ''),
    (8, 106, 'Syn Shamisen', 'Syn Shamisen', '', ''),
    (0, 107, 'Koto', 'Koto', 'Koto', 'Koto'),
    (1, 107, 'Gu Zheng', 'Gu Zheng', '', ''),
    (8, 107, 'Taisho Koto', 'Taisho Koto', 'Taisho Koto', 'Taisho Koto'),
    (16, 107, 'Kanoon', 'Kanoon', 'Kanoon', ''),
    (19, 107, 'Kanoon+Choir', 'Kanoon+Choir', '', ''),
    (24, 107, 'Oct Harp', 'Oct Harp', '', ''),
    (0, 108, 'Kalimba', 'Kalimba', 'Kalimba', 'Kalimba'),
    (8, 108, 'Sanza', 'Sanza', '', ''),
    (9, 108, 'Bodhran', '', '', ''),
    (10, 108, 'Bodhran Mute', '', '', ''),
    (0, 109, 'Bagpipe', 'Bagpipe', 'Bagpipe', 'Bagpipe'),
    (8, 109, 'Didgeridoo', 'Didgeridoo', '', ''),
    (9, 109, 'Uillean Pipe', '', '', ''),
    (10, 109, 'UillnPipe Nm', '', '', ''),
    (11, 109, 'UillnPipe Or', '', '', ''),
    (0, 110, 'Fiddle', 'Fiddle', 'Fiddle', 'Fiddle'),
    (8, 110, 'Er Hu', 'Er Hu', '', ''),
    (9, 110, 'Gao Hu', 'Gao Hu', '', ''),
    (0, 111, 'Shanai', 'Shanai', 'Shanai', 'Shanai'),
    (1, 111, 'Shanai 2', 'Shanai 2', 'Shanai 2', ''),
    (8, 111, 'Pungi', 'Pungi', 'Pungi', ''),
    (16, 111, 'Hichiriki', 'Hichiriki', 'Hichiriki', ''),
    (24, 111, 'Mizmar', 'Mizmar', '', ''),
    (32, 111, 'Suona 1', 'Suona 1', '', ''),
    (33, 111, 'Suona 2', 'Suona 2', '', ''),
    (0, 112, 'Tinkle Bell', 'Tinkle Bell', 'Tinkle Bell', 'Tinkle Bell'),
    (8, 112, 'Bonang', 'Bonang', 'Bonang', ''),
    (9, 112, 'Gender', 'Gender', 'Gender', ''),
    (10, 112, 'Gamelan Gong', 'Gamelan Gong', 'GamelanGong', ''),
    (11, 112, 'St.Gamelan', 'St.Gamelan', 'St.Gamelan', ''),
    (12, 112, 'Jang Gu', 'Jang-Gu', '', ''),
    (13, 112, 'Jegogan', '', '', ''),
    (14, 112, 'Jublag', '', '', ''),
    (15, 112, 'Pemade', '', '', ''),
    (16, 112, 'RAMA Cymbal', 'RAMA Cymbal', 'RAMA Cymbal', ''),
    (17, 112, 'Kajar', '', '', ''),
    (18, 112, 'Kelontuk', '', '', ''),
    (19, 112, 'Kelontuk Mt', '', '', ''),
    (20, 112, 'Kelontuk Sid', '', '', ''),
    (21, 112, 'Kopyak Op', '', '', ''),
    (22, 112, 'Kopyak Mt', '', '', ''),
    (23, 112, 'Ceng Ceng', '', '', ''),
    (24, 112, 'Reyoung', '', '', ''),
    (25, 112, 'Kempur', '', '', ''),
    (32, 112, 'Jngl Crash', '', '', ''),
    (40, 112, 'Crash Menu', '', '', ''),
    (41, 112, 'RideCym Menu', '', '', ''),
    (42, 112, 'RideBellMenu', '', '', ''),
    (0, 113, 'Agogo', 'Agogo', 'Agogo', 'Agogo'),
    (8, 113, 'Atarigane', 'Atarigane', 'Atarigane', ''),
    (16, 113, 'Tambourine', 'Tambourine', '', ''),
    (0, 114, 'Steel Drums', 'Steel Drums', 'Steel Drums', 'Steel Drums'),
    (1, 114, 'Island Mlt', 'Island Mlt', '', ''),
    (0, 115, 'Woodblock', 'Woodblock', 'Woodblock', 'Woodblock'),
    (8, 115, 'Castanets', 'Castanets', 'Castanets', 'Castanets'),
    (16, 115, 'Angklung', 'Angklung', '', ''),
    (17, 115, 'Angkl Rhythm', 'Angkl Rhythm', '', ''),
    (24, 115, 'Finger Snaps', 'Finger Snaps', '', ''),
    (32, 115, 'HandClap', '909 HandClap', '', ''),
    (40, 115, 'HandClapMenu', '', '', ''),
    (0, 116, 'Taiko', 'Taiko', 'Taiko', 'Taiko'),
    (1, 116, 'Small Taiko', 'Small Taiko', '', ''),
    (8, 116, 'Concert BD', 'Concert BD', 'Concert BD', 'Concert BD'),
    (9, 116, 'ConcertBD Mt', '', '', ''),
    (16, 116, 'Jungle BD', 'Jungle BD', '', ''),
    (17, 116, 'Techno BD', 'Techno BD', '', ''),
    (18, 116, 'Bounce', 'Bounce', '', ''),
    (24, 116, 'KendangWadon', '', '', ''),
    (25, 116, 'Bebarongan', '', '', ''),
    (26, 116, 'Pelegongan', '', '', ''),
    (27, 116, 'Dholak 1', '', '', ''),
    (28, 116, 'Dholak 2', '', '', ''),
    (32, 116, 'Jngl BD Roll', '', '', ''),
    (40, 116, 'Kick Menu 1', '', '', ''),
    (41, 116, 'Kick Menu 2', '', '', ''),
    (42, 116, 'Kick Menu 3', '', '', ''),
    (43, 116, 'Kick Menu 4', '', '', ''),
    (0, 117, 'Melo. Tom 1', 'Melo. Tom 1', 'Melo. Tom 1', 'Melo. Tom 1'),
    (1, 117, 'Real Tom', 'Real Tom', 'Real Tom', ''),
    (2, 117, 'Real Tom 2', '', '', ''),
    (3, 117, 'Jazz Tom', '', '', ''),
    (4, 117, 'Brush Tom', '', '', ''),
    (8, 117, 'Melo. Tom 2', 'Melo. Tom 2', 'Melo. Tom 2', 'Melo. Tom 2'),
    (9, 117, 'Rock Tom', 'Rock Tom', 'Rock Tom', ''),
    (16, 117, 'Rash SD', 'Rash SD', '', ''),
    (17, 117, 'House SD', 'House SD', '', ''),
    (18, 117, 'Jungle SD', 'Jungle SD', '', ''),
    (19, 117, '909 SD', '909 SD', '', ''),
    (24, 117, 'Jngl SD Roll', '', '', ''),
    (40, 117, 'SD Menu 1', '', '', ''),
    (41, 117, 'SD Menu 2', '', '', ''),
    (42, 117, 'SD Menu 3', '', '', ''),
    (43, 117, 'SD Menu 4', '', '', ''),
    (44, 117, 'SD Menu 5', '', '', ''),
    (0, 118, 'Synth Drum', 'Synth Drum', 'Synth Drum', 'Synth Drum'),
    (8, 118, '808 Tom', '808 Tom', '808 Tom', '808 Tom'),
    (9, 118, 'Elec Perc', 'Elec Perc', 'Elec Perc', 'Elec Perc'),
    (10, 118, 'Sine Perc.', 'Sine Perc.', '', ''),
    (11, 118, '606 Tom', '606 Tom', '', ''),
    (12, 118, '909 Tom', '909 Tom', '', ''),
    (13, 118, 'Dist.Tom', '', '', ''),
    (0, 119, 'Reverse Cym.', 'Reverse Cym.', 'Reverse Cym', 'Reverse Cym'),
    (1, 119, 'Reverse Cym2', 'Reverse Cym2', 'ReverseCym2', ''),
    (2, 119, 'Reverse Cym3', 'Reverse Cym3', '', ''),
    (3, 119, 'Reverse Cym4', '', '', ''),
    (8, 119, 'Rev.Snare 1', 'Rev.Snare 1', 'Rev.Snare 1', ''),
    (9, 119, 'Rev.Snare 2', 'Rev.Snare 2', 'Rev.Snare 2', ''),
    (16, 119, 'Rev.Kick 1', 'Rev.Kick 1', 'Rev.Kick 1', ''),
    (17, 119, 'Rev.ConBD', 'Rev.ConBD', 'Rev.ConBD', ''),
    (24, 119, 'Rev.Tom 1', 'Rev.Tom 1', 'Rev.Tom 1', ''),
    (25, 119, 'Rev.Tom 2', 'Rev.Tom 2', 'Rev.Tom 2', ''),
    (26, 119, 'Rev.Tom 3', '', '', ''),
    (27, 119, 'Rev.Tom 4', '', '', ''),
    (40, 119, 'Rev.SD Menu1', '', '', ''),
    (41, 119, 'Rev.SD Menu2', '', '', ''),
    (42, 119, 'Rev.SD Menu3', '', '', ''),
    (43, 119, 'Rev.BD Menu1', '', '', ''),
    (44, 119, 'Rev.BD Menu2', '', '', ''),
    (45, 119, 'Rev.BD Menu3', '', '', ''),
    (46, 119, 'Rev.ClapMenu', '', '', ''),
    (0, 120, 'Gt.FretNoise', 'Gt.FretNoise', 'Gt.FretNoiz', 'Gt.FretNoiz'),
    (1, 120, 'Gt.Cut Noise', 'Gt.Cut Noise', 'Gt.CutNoise', 'Gt.CutNoise'),
    (2, 120, 'String Slap', 'String Slap', 'String Slap', 'String Slap'),
    (3, 120, 'Gt.CutNoise2', 'Gt.CutNoise2', 'Gt.CutNz. 2', ''),
    (4, 120, 'Dist.CutNoiz', 'Dist.CutNoiz', 'Dist.CutNz.', ''),
    (5, 120, 'Bass Slide', 'Bass Slide', 'Bass Slide', ''),
    (6, 120, 'Pick Scrape', 'Pick Scrape', 'Pick Scrape', ''),
    (8, 120, 'Gt. FX Menu', 'Gt. FX Menu', '', ''),
    (9, 120, 'Bartok Pizz.', 'Bartok Pizz.', '', ''),
    (10, 120, 'Guitar Slap', 'Guitar Slap', '', ''),
    (11, 120, 'Chord Stroke', 'Chord Stroke', '', ''),
    (12, 120, 'Biwa Stroke', 'Biwa Stroke', '', ''),
    (13, 120, 'Biwa Tremolo', 'Biwa Tremolo', '', ''),
    (16, 120, 'A.Bs.Nz Menu', '', '', ''),
    (17, 120, 'D.Gt.Nz Menu', '', '', ''),
    (18, 120, 'E.Gt.NzMenu1', '', '', ''),
    (19, 120, 'E.Gt.NzMenu2', '', '', ''),
    (20, 120, 'G.StrokeMenu', '', '', ''),
    (21, 120, 'Gt.SlideMenu', '', '', ''),
    (22, 120, 'A.Bs.Mute Nz', '', '', ''),
    (23, 120, 'A.Bs.TouchNz', '', '', ''),
    (24, 120, 'A.Bs.AtackNz', '', '', ''),
    (25, 120, 'TC Up Nz', '', '', ''),
    (26, 120, 'TC DownMt.Nz', '', '', ''),
    (27, 120, 'TC UpMt.Nz', '', '', ''),
    (28, 120, 'TC Down Nz', '', '', ''),
    (29, 120, 'DstGT.Up Nz', '', '', ''),
    (30, 120, 'DstGT.DwnNz1', '', '', ''),
    (31, 120, 'DstGT.DwnNz2', '', '', ''),
    (32, 120, 'DstGT.MuteNz', '', '', ''),
    (34, 120, 'Gt.StrokeNz5', '', '', ''),
    (35, 120, 'StlGt.SldNz1', '', '', ''),
    (36, 120, 'StlGt.SldNz2', '', '', ''),
    (37, 120, 'StlGt.SldNz3', '', '', ''),
    (38, 120, 'StlGt.SldNz4', '', '', ''),
    (39, 120, 'Gt.StrokeNz1', '', '', ''),
    (40, 120, 'Gt.StrokeNz2', '', '', ''),
    (41, 120, 'Gt.StrokeNz3', '', '', ''),
    (42, 120, 'Gt.StrokeNz4', '', '', ''),
    (0, 121, 'Breath Noise', 'Breath Noise', 'BreathNoise', 'BreathNoise'),
    (1, 121, 'Fl.Key Click', 'Fl.Key Click', 'Fl.KeyClick', 'Fl.KeyClick'),
    (2, 121, 'Brth Nz Menu', '', '', ''),
    (3, 121, 'Fl.Breath 1', '', '', ''),
    (4, 121, 'Fl.Breath 2', '', '', ''),
    (5, 121, 'Fl.Breath 3', '', '', ''),
    (6, 121, 'Vox Breath 1', '', '', ''),
    (7, 121, 'Vox Breath 2', '', '', ''),
    (8, 121, 'Trombone Nz', '', '', ''),
    (9, 121, 'Trumpet Nz', '', '', ''),
    (0, 122, 'Seashore', 'Seashore', 'Seashore', 'Seashore'),
    (1, 122, 'Rain', 'Rain', 'Rain', 'Rain'),
    (2, 122, 'Thunder', 'Thunder', 'Thunder', 'Thunder'),
    (3, 122, 'Wind', 'Wind', 'Wind', 'Wind'),
    (4, 122, 'Stream', 'Stream', 'Stream', 'Stream'),
    (5, 122, 'Bubble', 'Bubble', 'Bubble', 'Bubble'),
    (6, 122, 'Wind 2', 'Wind 2', '', ''),
    (7, 122, 'Cricket', '', '', ''),
    (16, 122, 'Pink Noise', 'Pink Noise', '', ''),
    (17, 122, 'White Noise', 'White Noise', '', ''),
    (0, 123, 'Bird', 'Bird', 'Bird', 'Bird'),
    (1, 123, 'Dog', 'Dog', 'Dog', 'Dog'),
    (2, 123, 'Horse-Gallop', 'Horse-Gallop', 'HorseGallop', 'HorseGallop'),
    (3, 123, 'Bird 2', 'Bird 2', 'Bird 2', 'Bird 2'),
    (4, 123, 'Kitty', 'Kitty', 'Kitty', ''),
    (5, 123, 'Growl', 'Growl', 'Growl', ''),
    (6, 123, 'Growl 2', '', '', ''),
    (7, 123, 'Fancy Animal', '', '', ''),
    (8, 123, 'Seal', '', '', ''),
    (0, 124, 'Telephone 1', 'Telephone 1', 'Telephone 1', 'Telephone 1'),
    (1, 124, 'Telephone 2', 'Telephone 2', 'Telephone 2', 'Telephone 2'),
    (2, 124, 'DoorCreaking', 'DoorCreaking', 'Creaking', 'Creaking'),
    (3, 124, 'Door', 'Door', 'Door', 'Door'),
    (4, 124, 'Scratch', 'Scratch', 'Scratch', 'Scratch'),
    (5, 124, 'Wind Chimes', 'Wind Chimes', 'Wind Chimes', 'Wind Chimes'),
    (7, 124, 'Scratch 2', 'Scratch 2', 'Scratch 2', ''),
    (8, 124, 'ScratchKey', 'ScratchKey', '', ''),
    (9, 124, 'TapeRewind', 'TapeRewind', '', ''),
    (10, 124, 'Phono Noise', 'Phono Noise', '', ''),
    (11, 124, 'MC-500 Beep', 'MC-500 Beep', '', ''),
    (12, 124, 'Scratch 3', '', '', ''),
    (13, 124, 'Scratch 4', '', '', ''),
    (14, 124, 'Scratch 5', '', '', ''),
    (15, 124, 'Scratch 6', '', '', ''),
    (16, 124, 'Scratch 7', '', '', ''),
    (0, 125, 'Helicopter', 'Helicopter', 'Helicopter', 'Helicopter'),
    (1, 125, 'Car-Engine', 'Car-Engine', 'Car-Engine', 'Car-Engine'),
    (2, 125, 'Car-Stop', 'Car-Stop', 'Car-Stop', 'Car-Stop'),
    (3, 125, 'Car-Pass', 'Car-Pass', 'Car-Pass', 'Car-Pass'),
    (4, 125, 'Car-Crash', 'Car-Crash', 'Car-Crash', 'Car-Crash'),
    (5, 125, 'Siren', 'Siren', 'Siren', 'Siren'),
    (6, 125, 'Train', 'Train', 'Train', 'Train'),
    (7, 125, 'Jetplane', 'Jetplane', 'Jetplane', 'Jetplane'),
    (8, 125, 'Starship', 'Starship', 'Starship', 'Starship'),
    (9, 125, 'Burst Noise', 'Burst Noise', 'Burst Noise', 'Burst Noise'),
    (10, 125, 'Calculating', 'Calculating', '', ''),
    (11, 125, 'Perc. Bang', 'Perc. Bang', '', ''),
    (12, 125, 'Burner', '', '', ''),
    (13, 125, 'Glass & Glam', '', '', ''),
    (14, 125, 'Ice Ring', '', '', ''),
    (15, 125, 'Over Blow', '', '', ''),
    (16, 125, 'Crack Bottle', '', '', ''),
    (17, 125, 'Pour Bottle', '', '', ''),
    (18, 125, 'Soda', '', '', ''),
    (19, 125, 'Open CD Tray', '', '', ''),
    (20, 125, 'Audio Switch', '', '', ''),
    (21, 125, 'Key Typing', '', '', ''),
    (22, 125, 'SL 1', '', '', ''),
    (23, 125, 'SL 2', '', '', ''),
    (24, 125, 'Car Engine 2', '', '', ''),
    (25, 125, 'Car Horn', '', '', ''),
    (26, 125, 'Boeeeen', '', '', ''),
    (27, 125, 'R.Crossing', '', '', ''),
    (28, 125, 'Compresser', '', '', ''),
    (29, 125, 'Sword Boom!', '', '', ''),
    (30, 125, 'Sword Cross', '', '', ''),
    (31, 125, 'Stab! 1', '', '', ''),
    (32, 125, 'Stab! 2', '', '', ''),
    (0, 126, 'Applause', 'Applause', 'Applause', 'Applause'),
    (1, 126, 'Laughing', 'Laughing', 'Laughing', 'Laughing'),
    (2, 126, 'Screaming', 'Screaming', 'Screaming', 'Screaming'),
    (3, 126, 'Punch', 'Punch', 'Punch', 'Punch'),
    (4, 126, 'Heart Beat', 'Heart Beat', 'Heart Beat', 'Heart Beat'),
    (5, 126, 'Footsteps', 'Footsteps', 'Footsteps', 'Footsteps'),
    (6, 126, 'Applause 2', 'Applause 2', 'Applause 2', ''),
    (7, 126, 'Small Club', 'Small Club', '', ''),
    (8, 126, 'ApplauseWave', 'ApplauseWave', '', ''),
    (9, 126, 'BabyLaughing', '', '', ''),
    (16, 126, 'Voice One', 'Voice One', '', ''),
    (17, 126, 'Voice Two', 'Voice Two', '', ''),
    (18, 126, 'Voice Three', 'Voice Three', '', ''),
    (19, 126, 'Voice Tah', 'Voice Tah', '', ''),
    (20, 126, 'Voice Whey', 'Voice Whey', '', ''),
    (22, 126, 'Voice Kikit', '', '', ''),
    (23, 126, 'Voice ComeOn', '', '', ''),
    (24, 126, 'Voice Aou', '', '', ''),
    (25, 126, 'Voice Oou', '', '', ''),
    (26, 126, 'Voice Hie', '', '', ''),
    (0, 127, 'Gun Shot', 'Gun Shot', 'Gun Shot', 'Gun Shot'),
    (1, 127, 'Machine Gun', 'Machine Gun', 'Machine Gun', 'Machine Gun'),
    (2, 127, 'Lasergun', 'Lasergun', 'Lasergun', 'Lasergun'),
    (3, 127, 'Explosion', 'Explosion', 'Explosion', 'Explosion'),
    (4, 127, 'Eruption', 'Eruption', '', ''),
    (5, 127, 'Big Shot', 'Big Shot', '', ''),
    (6, 127, 'Explosion 2', '', '', ''),
    (126, 0, '', '', '', 'Piano 2'),
    (126, 1, '', '', '', 'Piano 2'),
    (126, 2, '', '', '', 'Piano 2'),
    (126, 3, '', '', '', 'Honky-tonk'),
    (126, 4, '', '', '', 'Piano 1'),
    (126, 5, '', '', '', 'Piano 2'),
    (126, 6, '', '', '', 'Piano 2'),
    (126, 7, '', '', '', 'E.Piano 1'),
    (126, 8, '', '', '', 'Detuned EP1'),
    (126, 9, '', '', '', 'E.Piano 2'),
    (126, 10, '', '', '', 'Steel Gt.'),
    (126, 11, '', '', '', 'Steel Gt.'),
    (126, 12, '', '', '', '12-str.Gt'),
    (126, 13, '', '', '', 'Funk Gt.'),
    (126, 14, '', '', '', 'Muted Gt.'),
    (126, 15, '', '', '', 'Slap Bass 1'),
    (126, 16, '', '', '', 'Slap Bass 1'),
    (126, 17, '', '', '', 'Slap Bass 1'),
    (126, 18, '', '', '', 'Slap Bass 1'),
    (126, 19, '', '', '', 'Slap Bass 2'),
    (126, 20, '', '', '', 'Slap Bass 2'),
    (126, 21, '', '', '', 'Slap Bass 2'),
    (126, 22, '', '', '', 'Slap Bass 2'),
    (126, 23, '', '', '', 'Fingered Bs'),
    (126, 24, '', '', '', 'Fingered Bs'),
    (126, 25, '', '', '', 'Picked Bass'),
    (126, 26, '', '', '', 'Picked Bass'),
    (126, 27, '', '', '', 'Fretless Bs'),
    (126, 28, '', '', '', 'Acoustic Bs'),
    (126, 29, '', '', '', 'Choir Aahs'),
    (126, 30, '', '', '', 'Choir Aahs'),
    (126, 31, '', '', '', 'Choir Aahs'),
    (126, 32, '', '', '', 'Choir Aahs'),
    (126, 33, '', '', '', 'SlowStrings'),
    (126, 34, '', '', '', 'Strings'),
    (126, 35, '', '', '', 'SynStrings3'),
    (126, 36, '', '', '', 'SynStrings3'),
    (126, 37, '', '', '', 'Organ 1'),
    (126, 38, '', '', '', 'Organ 1'),
    (126, 39, '', '', '', 'Organ 1'),
    (126, 40, '', '', '', 'Organ 2'),
    (126, 41, '', '', '', 'Organ 1'),
    (126, 42, '', '', '', 'Organ 1'),
    (126, 43, '', '', '', 'Organ 2'),
    (126, 44, '', '', '', 'Organ 2'),
    (126, 45, '', '', '', 'Organ 2'),
    (126, 46, '', '', '', 'Trumpet'),
    (126, 47, '', '', '', 'Trumpet'),
    (126, 48, '', '', '', 'Trombone'),
    (126, 49, '', '', '', 'Trombone'),
    (126, 50, '', '', '', 'Trombone'),
    (126, 51, '', '', '', 'Trombone'),
    (126, 52, '', '', '', 'Trombone'),
    (126, 53, '', '', '', 'Trombone'),
    (126, 54, '', '', '', 'Alto Sax'),
    (126, 55, '', '', '', 'Tenor Sax'),
    (126, 56, '', '', '', 'BaritoneSax'),
    (126, 57, '', '', '', 'Alto Sax'),
    (126, 58, '', '', '', 'Brass 1'),
    (126, 59, '', '', '', 'Brass 1'),
    (126, 60, '', '', '', 'Brass 2'),
    (126, 61, '', '', '', 'Brass 2'),
    (126, 62, '', '', '', 'Brass 1'),
    (126, 63, '', '', '', 'Orchest.Hit'),
    (127, 0, '', '', '', 'Acou Piano1'),
    (127, 1, '', '', '', 'Acou Piano2'),
    (127, 2, '', '', '', 'Acou Piano3'),
    (127, 3, '', '', '', 'Elec Piano1'),
    (127, 4, '', '', '', 'Elec Piano2'),
    (127, 5, '', '', '', 'Elec Piano3'),
    (127, 6, '', '', '', 'Elec Piano4'),
    (127, 7, '', '', '', 'Honkytonk'),
    (127, 8, '', '', '', 'Elec Org 1'),
    (127, 9, '', '', '', 'Elec Org 2'),
    (127, 10, '', '', '', 'Elec Org 3'),
    (127, 11, '', '', '', 'Elec Org 4'),
    (127, 12, '', '', '', 'Pipe Org 1'),
    (127, 13, '', '', '', 'Pipe Org 2'),
    (127, 14, '', '', '', 'Pipe Org 3'),
    (127, 15, '', '', '', 'Accordion'),
    (127, 16, '', '', '', 'Harpsi 1'),
    (127, 17, '', '', '', 'Harpsi 2'),
    (127, 18, '', '', '', 'Harpsi 3'),
    (127, 19, '', '', '', 'Clavi 1'),
    (127, 20, '', '', '', 'Clavi 2'),
    (127, 21, '', '', '', 'Clavi 3'),
    (127, 22, '', '', '', 'Celesta 1'),
    (127, 23, '', '', '', 'Celesta 2'),
    (127, 24, '', '', '', 'Syn Brass 1'),
    (127, 25, '', '', '', 'Syn Brass 2'),
    (127, 26, '', '', '', 'Syn Brass 3'),
    (127, 27, '', '', '', 'Syn Brass 4'),
    (127, 28, '', '', '', 'Syn Bass 1'),
    (127, 29, '', '', '', 'Syn Bass 2'),
    (127, 30, '', '', '', 'Syn Bass 3'),
    (127, 31, '', '', '', 'Syn Bass 4'),
    (127, 32, '', '', '', 'Fantasy'),
    (127, 33, '', '', '', 'Harmo Pan'),
    (127, 34, '', '', '', 'Chorale'),
    (127, 35, '', '', '', 'Glasses'),
    (127, 36, '', '', '', 'Soundtrack'),
    (127, 37, '', '', '', 'Atmosphere'),
    (127, 38, '', '', '', 'Warm Bell'),
    (127, 39, '', '', '', 'Funny Vox'),
    (127, 40, '', '', '', 'Echo Bell'),
    (127, 41, '', '', '', 'Ice Rain'),
    (127, 42, '', '', '', 'Oboe 2001'),
    (127, 43, '', '', '', 'Echo Pan'),
    (127, 44, '', '', '', 'Doctor Solo'),
    (127, 45, '', '', '', 'School Daze'),
    (127, 46, '', '', '', 'Bellsinger'),
    (127, 47, '', '', '', 'Square Wave'),
    (127, 48, '', '', '', 'Str Sect 1'),
    (127, 49, '', '', '', 'Str Sect 2'),
    (127, 50, '', '', '', 'Str Sect 3'),
    (127, 51, '', '', '', 'Pizzicato'),
    (127, 52, '', '', '', 'Violin 1'),
    (127, 53, '', '', '', 'Violin 2'),
    (127, 54, '', '', '', 'Cello 1'),
    (127, 55, '', '', '', 'Cello 2'),
    (127, 56, '', '', '', 'Contrabass'),
    (127, 57, '', '', '', 'Harp 1'),
    (127, 58, '', '', '', 'Harp 2'),
    (127, 59, '', '', '', 'Guitar 1'),
    (127, 60, '', '', '', 'Guitar 2'),
    (127, 61, '', '', '', 'Elec Gtr 1'),
    (127, 62, '', '', '', 'Elec Gtr 2'),
    (127, 63, '', '', '', 'Sitar'),
    (127, 64, '', '', '', 'Acou Bass 1'),
    (127, 65, '', '', '', 'Acou Bass 2'),
    (127, 66, '', '', '', 'Elec Bass 1'),
    (127, 67, '', '', '', 'Elec Bass 2'),
    (127, 68, '', '', '', 'Slap Bass 1'),
    (127, 69, '', '', '', 'Slap Bass 2'),
    (127, 70, '', '', '', 'Fretless 1'),
    (127, 71, '', '', '', 'Fretless 2'),
    (127, 72, '', '', '', 'Flute 1'),
    (127, 73, '', '', '', 'Flute 2'),
    (127, 74, '', '', '', 'Piccolo 1'),
    (127, 75, '', '', '', 'Piccolo 2'),
    (127, 76, '', '', '', 'Recorder'),
    (127, 77, '', '', '', 'Pan Pipes'),
    (127, 78, '', '', '', 'Sax 1'),
    (127, 79, '', '', '', 'Sax 2'),
    (127, 80, '', '', '', 'Sax 3'),
    (127, 81, '', '', '', 'Sax 4'),
    (127, 82, '', '', '', 'Clarinet 1'),
    (127, 83, '', '', '', 'Clarinet 2'),
    (127, 84, '', '', '', 'Oboe'),
    (127, 85, '', '', '', 'Engl Horn'),
    (127, 86, '', '', '', 'Bassoon'),
    (127, 87, '', '', '', 'Harmonica'),
    (127, 88, '', '', '', 'Trumpet 1'),
    (127, 89, '', '', '', 'Trumpet 2'),
    (127, 90, '', '', '', 'Trombone 1'),
    (127, 91, '', '', '', 'Trombone 2'),
    (127, 92, '', '', '', 'Fr Horn 1'),
    (127, 93, '', '', '', 'Fr Horn 2'),
    (127, 94, '', '', '', 'Tuba'),
    (127, 95, '', '', '', 'Brs Sect 1'),
    (127, 96, '', '', '', 'Brs Sect 2'),
    (127, 97, '', '', '', 'Vibe 1'),
    (127, 98, '', '', '', 'Vibe 2'),
    (127, 99, '', '', '', 'Syn Mallet'),
    (127, 100, '', '', '', 'Windbell'),
    (127, 101, '', '', '', 'Glock'),
    (127, 102, '', '', '', 'Tube Bell'),
    (127, 103, '', '', '', 'Xylophone'),
    (127, 104, '', '', '', 'Marimba'),
    (127, 105, '', '', '', 'Koto'),
    (127, 106, '', '', '', 'Sho'),
    (127, 107, '', '', '', 'Shakuhachi'),
    (127, 108, '', '', '', 'Whistle 1'),
    (127, 109, '', '', '', 'Whistle 2'),
    (127, 110, '', '', '', 'Bottleblow'),
    (127, 111, '', '', '', 'Breathpipe'),
    (127, 112, '', '', '', 'Timpani'),
    (127, 113, '', '', '', 'Melodic Tom'),
    (127, 114, '', '', '', 'Deep Snare'),
    (127, 115, '', '', '', 'Elec Perc 1'),
    (127, 116, '', '', '', 'Elec Perc 2'),
    (127, 117, '', '', '', 'Taiko'),
    (127, 118, '', '', '', 'Taiko Rim'),
    (127, 119, '', '', '', 'Cymbal'),
    (127, 120, '', '', '', 'Castanets'),
    (127, 121, '', '', '', 'Triangle'),
    (127, 122, '', '', '', 'Orche Hit'),
    (127, 123, '', '', '', 'Telephone'),
    (127, 124, '', '', '', 'Bird Tweet'),
    (127, 125, '', '', '', 'OneNote Jam'),
    (127, 126, '', '', '', 'Water Bell'),
    (127, 127, '', '', '', 'Jungle Tune'),
]
GS_DRUMKITS = [
    # Format: (pc, sc8850_name, sc88pro_name, sc88_name, sc55_name)
    # Empty string means the kit does not exist on that generation.
    (0, 'STANDARD 1', 'STANDARD 1', 'STANDARD 1', 'STANDARD'),
    (1, 'STANDARD 2', 'STANDARD 2', 'STANDARD 2', ''),
    (2, 'STANDARD L/R', 'STANDARD 3', '', ''),
    (8, 'ROOM', 'ROOM', 'ROOM', 'ROOM'),
    (9, 'HIP HOP', 'HIP HOP', '', ''),
    (10, 'JUNGLE', 'JUNGLE', '', ''),
    (11, 'TECHNO', 'TECHNO', '', ''),
    (12, 'ROOM L/R', '', '', ''),
    (13, 'HOUSE', '', '', ''),
    (16, 'POWER', 'POWER', 'POWER', 'POWER'),
    (24, 'ELECTRONIC', 'ELECTRONIC', 'ELECTRONIC', 'ELECTRONIC'),
    (25, 'TR-808', 'TR-808', 'TR-808/909', 'TR-808'),
    (26, 'DANCE', 'DANCE', 'DANCE', ''),
    (27, 'CR-78', 'CR-78', '', ''),
    (28, 'TR-606', 'TR-606', '', ''),
    (29, 'TR-707', 'TR-707', '', ''),
    (30, 'TR-909', 'TR-909', '', ''),
    (32, 'JAZZ', 'JAZZ', 'JAZZ', 'JAZZ'),
    (33, 'JAZZ L/R', '', '', ''),
    (40, 'BRUSH', 'BRUSH', 'BRUSH', 'BRUSH'),
    (41, 'BRUSH 2', '', '', ''),
    (42, 'BRUSH 2 L/R', '', '', ''),
    (48, 'ORCHESTRA', 'ORCHESTRA', 'ORCHESTRA', 'ORCHESTRA'),
    (49, 'ETHNIC', 'ETHNIC', 'ETHNIC', ''),
    (50, 'KICK & SNARE', 'KICK & SNARE', 'KICK & SNARE', ''),
    (51, 'KICK & SNARE 2', '', '', ''),
    (52, 'ASIA', 'ASIA', '', ''),
    (53, 'CYMBAL&CLAPS', 'CYMBAL&CLAPS', '', ''),
    (54, 'GAMELAN 1', '', '', ''),
    (55, 'GAMELAN 2', '', '', ''),
    (56, 'SFX', 'SFX', 'SFX', 'SFX'),
    (57, 'RHYTHM FX', 'RHYTHM FX', 'RHYTHM FX', ''),
    (58, 'RHYTHM FX 2', 'RHYTHM FX 2', '', ''),
    (59, 'RHYTHM FX 3', '', '', ''),
    (60, 'SFX 2', '', '', ''),
    (61, 'VOICE', '', '', ''),
    (62, 'CYM&CLAPS 2', '', '', ''),
    (127, '', '', '', 'CM-64/32L'),
]


# XG Basic Normal Voices (Bank MSB=0, LSB=0, Level 1)
# Format: (program, name, category)
XG_BASIC_INSTRUMENTS = [
    # Piano (0-7)
    (0, "GrandPno", "Piano"),
    (1, "BritePno", "Piano"),
    (2, "El.Grand", "Piano"),
    (3, "HnkyTonk", "Piano"),
    (4, "E.Piano1", "Piano"),
    (5, "E.Piano2", "Piano"),
    (6, "Harpsi.", "Piano"),
    (7, "Clavi", "Piano"),
    # Chromatic Percussion (8-15)
    (8, "Celesta", "Chromatic Percussion"),
    (9, "Glocken", "Chromatic Percussion"),
    (10, "MusicBox", "Chromatic Percussion"),
    (11, "Vibes", "Chromatic Percussion"),
    (12, "Marimba", "Chromatic Percussion"),
    (13, "Xylophon", "Chromatic Percussion"),
    (14, "TubulBel", "Chromatic Percussion"),
    (15, "Dulcimer", "Chromatic Percussion"),
    # Organ (16-23)
    (16, "DrawOrgn", "Organ"),
    (17, "PercOrgn", "Organ"),
    (18, "RockOrgn", "Organ"),
    (19, "ChrchOrg", "Organ"),
    (20, "ReedOrgn", "Organ"),
    (21, "Acordion", "Organ"),
    (22, "Harmnica", "Organ"),
    (23, "TangoAcd", "Organ"),
    # Guitar (24-31)
    (24, "NylonGtr", "Guitar"),
    (25, "SteelGtr", "Guitar"),
    (26, "Jazz Gtr", "Guitar"),
    (27, "CleanGtr", "Guitar"),
    (28, "Mute Gtr", "Guitar"),
    (29, "Ovrdrive", "Guitar"),
    (30, "Dist.Gtr", "Guitar"),
    (31, "GtrHarmo", "Guitar"),
    # Bass (32-39)
    (32, "Aco.Bass", "Bass"),
    (33, "FngrBass", "Bass"),
    (34, "PickBass", "Bass"),
    (35, "Fretless", "Bass"),
    (36, "SlapBas1", "Bass"),
    (37, "SlapBas2", "Bass"),
    (38, "SynBass1", "Bass"),
    (39, "SynBass2", "Bass"),
    # Strings (40-47)
    (40, "Violin", "Strings"),
    (41, "Viola", "Strings"),
    (42, "Cello", "Strings"),
    (43, "Contrabs", "Strings"),
    (44, "Trem.Str", "Strings"),
    (45, "Pizz.Str", "Strings"),
    (46, "Harp", "Strings"),
    (47, "Timpani", "Strings"),
    # Ensemble (48-55)
    (48, "Strings1", "Ensemble"),
    (49, "Strings2", "Ensemble"),
    (50, "Syn Str1", "Ensemble"),
    (51, "Syn Str2", "Ensemble"),
    (52, "ChoirAah", "Ensemble"),
    (53, "VoiceOoh", "Ensemble"),
    (54, "SynVoice", "Ensemble"),
    (55, "Orch.Hit", "Ensemble"),
    # Brass (56-63)
    (56, "Trumpet", "Brass"),
    (57, "Trombone", "Brass"),
    (58, "Tuba", "Brass"),
    (59, "Mute Trp", "Brass"),
    (60, "Fr. Horn", "Brass"),
    (61, "BrssSect", "Brass"),
    (62, "SynBrss1", "Brass"),
    (63, "SynBrss2", "Brass"),
    # Reed (64-71)
    (64, "SprnoSax", "Reed"),
    (65, "Alto Sax", "Reed"),
    (66, "TenorSax", "Reed"),
    (67, "Bari.Sax", "Reed"),
    (68, "Oboe", "Reed"),
    (69, "Eng.Horn", "Reed"),
    (70, "Bassoon", "Reed"),
    (71, "Clarinet", "Reed"),
    # Pipe (72-79)
    (72, "Piccolo", "Pipe"),
    (73, "Flute", "Pipe"),
    (74, "Recorder", "Pipe"),
    (75, "PanFlute", "Pipe"),
    (76, "Bottle", "Pipe"),
    (77, "Shakhchi", "Pipe"),
    (78, "Whistle", "Pipe"),
    (79, "Ocarina", "Pipe"),
    # Synth Lead (80-87)
    (80, "SquareLd", "Synth Lead"),
    (81, "Saw Ld", "Synth Lead"),
    (82, "CaliopLd", "Synth Lead"),
    (83, "Chiff Ld", "Synth Lead"),
    (84, "CharanLd", "Synth Lead"),
    (85, "Voice Ld", "Synth Lead"),
    (86, "Fifth Ld", "Synth Lead"),
    (87, "Bass&Ld", "Synth Lead"),
    # Synth Pad (88-95)
    (88, "NewAgePd", "Synth Pad"),
    (89, "Warm Pad", "Synth Pad"),
    (90, "PolySyPd", "Synth Pad"),
    (91, "ChoirPad", "Synth Pad"),
    (92, "BowedPad", "Synth Pad"),
    (93, "MetalPad", "Synth Pad"),
    (94, "Halo Pad", "Synth Pad"),
    (95, "SweepPad", "Synth Pad"),
    # Synth Effects (96-103)
    (96, "Rain", "Synth Effects"),
    (97, "SoundTrk", "Synth Effects"),
    (98, "Crystal", "Synth Effects"),
    (99, "Atmosphr", "Synth Effects"),
    (100, "Bright", "Synth Effects"),
    (101, "Goblins", "Synth Effects"),
    (102, "Echoes", "Synth Effects"),
    (103, "Sci-Fi", "Synth Effects"),
    # Ethnic (104-111)
    (104, "Sitar", "Ethnic"),
    (105, "Banjo", "Ethnic"),
    (106, "Shamisen", "Ethnic"),
    (107, "Koto", "Ethnic"),
    (108, "Kalimba", "Ethnic"),
    (109, "Bagpipe", "Ethnic"),
    (110, "Fiddle", "Ethnic"),
    (111, "Shanai", "Ethnic"),
    # Percussive (112-119)
    (112, "TnklBell", "Percussive"),
    (113, "Agogo", "Percussive"),
    (114, "SteelDrm", "Percussive"),
    (115, "Woodblok", "Percussive"),
    (116, "TaikoDrm", "Percussive"),
    (117, "MelodTom", "Percussive"),
    (118, "Syn Drum", "Percussive"),
    (119, "RevCymbl", "Percussive"),
    # Sound Effects (120-127)
    (120, "FretNoiz", "Sound Effects"),
    (121, "BrthNoiz", "Sound Effects"),
    (122, "Seashore", "Sound Effects"),
    (123, "Tweet", "Sound Effects"),
    (124, "Telphone", "Sound Effects"),
    (125, "Helicptr", "Sound Effects"),
    (126, "Applause", "Sound Effects"),
    (127, "Gunshot", "Sound Effects"),
]

# XG Extension Voices (non-basic banks)
# Format: (bank_msb, bank_lsb, program, name, category, minimum_level)
# minimum_level: 1=XG Level 1, 2=XG Level 2 (MU100+), 3=XG Level 3 (MU128 only)
# Source: MU100/MU128 manuals. † markers = Level 2, †† markers = Level 3.
# LSBs 64-127 ("Other Waves" and "Other Instrument" banks) are all Level 2+.
XG_EXTENSION_INSTRUMENTS = [
    # --- Violin variants (pgm=40) ---
    # LSBs 64-65: Level 2 (†)
    (0, 64, 40, "Cadenza", "Strings", 2),
    (0, 65, 40, "CadenzDk", "Strings", 2),
    # LSBs 66-68: Level 3 (††)
    (0, 66, 40, "Vln Sec", "Strings", 3),
    (0, 67, 40, "Hrd Vlns", "Strings", 3),
    (0, 68, 40, "Slw Vlns", "Strings", 3),
    # --- Viola variants (pgm=41) ---
    (0, 64, 41, "Sonata", "Strings", 2),
    (0, 65, 41, "Vla Sec", "Strings", 3),
    (0, 66, 41, "Hrd Vlas", "Strings", 3),
    (0, 67, 41, "Slw Vlas", "Strings", 3),
    # --- Cello variants (pgm=42) ---
    (0, 65, 42, "CelloSec", "Strings", 3),
    (0, 66, 42, "Hrd Vcs", "Strings", 3),
    (0, 67, 42, "Slw Vcs", "Strings", 3),
    # --- Contrabass variants (pgm=43) ---
    (0, 65, 43, "CB Sec", "Strings", 3),
    (0, 66, 43, "Hrd CBs", "Strings", 3),
    (0, 67, 43, "Slw CBs", "Strings", 3),
    # --- Pizzicato Strings variants (pgm=45) ---
    (0, 65, 45, "Collegno", "Strings", 3),
    # --- String Ensemble 1 variants (pgm=48) ---
    (0, 68, 48, "Stacc H", "Ensemble", 3),
    (0, 69, 48, "Stacc L", "Ensemble", 3),
    # --- Chinese wind instruments at LSB=96 (Other Instrument 1) ---
    # Piccolo slot (pgm=72): Bang Di (Chinese bamboo flute)
    (0, 96, 72, "Bang Di", "Pipe", 3),
    # Flute slot (pgm=73): Qu Di (Chinese transverse flute)
    (0, 96, 73, "Qu Di", "Pipe", 3),
    # Bagpipe slot (pgm=109): Sheng (Chinese mouth organ)
    (0, 96, 109, "Sheng", "Pipe", 3),
    # Fiddle slot (pgm=110): Er Hu (Chinese spike fiddle)
    (0, 96, 110, "Er Hu", "Strings", 3),
]

# XG Drum Kits
# Format: (bank_msb, bank_lsb, program, name, minimum_level)
# bank_msb=127: standard XG percussion channel designation
# bank_msb=126: XG SFX percussion channel designation
# program is 0-indexed MIDI program number (XG manual uses 1-indexed)
# Level markers: *** = MU90 (Level 1), **** = MU100 (Level 2), †† = MU128 (Level 3)
XG_DRUMKITS = [
    # MSB=127, LSB=0: Standard drum kits
    (127, 0, 0, "Standard Kit", 1),
    (127, 0, 1, "Standard Kit 2", 1),       # MU90 extension
    (127, 0, 2, "Dry Kit", 1),              # MU90
    (127, 0, 3, "Bright Kit", 1),           # MU90
    (127, 0, 4, "Skim Kit", 2),             # MU100 Level 2
    (127, 0, 5, "Slim Kit", 2),             # MU100 Level 2
    (127, 0, 6, "Rogue Kit", 2),            # MU100 Level 2
    (127, 0, 7, "Hob Kit", 2),              # MU100 Level 2
    (127, 0, 8, "Room Kit", 1),
    (127, 0, 9, "Dark Room Kit", 1),        # MU90
    (127, 0, 16, "Rock Kit", 1),
    (127, 0, 17, "Rock Kit 2", 1),          # MU90
    (127, 0, 24, "Electro Kit", 1),
    (127, 0, 25, "Analog Kit", 1),
    (127, 0, 26, "Analog Kit 2", 1),        # MU90
    (127, 0, 27, "Dance Kit", 1),           # MU90
    (127, 0, 28, "Hip Hop Kit", 1),         # MU90
    (127, 0, 29, "Jungle Kit", 1),          # MU90
    (127, 0, 30, "Apogee Kit", 2),          # MU100 Level 2
    (127, 0, 31, "Perigee Kit", 2),         # MU100 Level 2
    (127, 0, 32, "Jazz Kit", 1),
    (127, 0, 33, "Jazz Kit 2", 1),          # MU90
    (127, 0, 40, "Brush Kit", 1),
    (127, 0, 41, "Brush Kit 2", 2),         # MU100 Level 2
    (127, 0, 48, "Symphony Kit", 1),
    (127, 0, 64, "Tramp Kit", 2),           # MU100 Level 2
    (127, 0, 65, "Amber Kit", 2),           # MU100 Level 2
    (127, 0, 66, "Coffin Kit", 2),          # MU100 Level 2
    (127, 0, 126, "Standard Kit (MU100 Native)", 2),  # MU100 Level 2
    (127, 0, 127, "Standard Kit (MU Basic)", 1),
    # MSB=126, LSB=0: SFX kits
    (126, 0, 0, "SFX Kit 1", 1),
    (126, 0, 1, "SFX Kit 2", 1),
    (126, 0, 16, "Techno Kit K/S", 2),      # MU100 Level 2
    (126, 0, 17, "Techno Kit Hi", 2),       # MU100 Level 2
    (126, 0, 18, "Techno Kit Lo", 2),       # MU100 Level 2
    (126, 0, 32, "Sakura Kit", 2),          # MU100 Level 2
    (126, 0, 33, "Small Latin Kit", 2),     # MU100 Level 2
    (126, 0, 34, "China Kit", 3),           # MU128 Level 3
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

    # Add minimum_level column if it doesn't exist (migration for older databases)
    for table in ("patches", "percussion_sets"):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN minimum_level INTEGER NOT NULL DEFAULT 1")
        except Exception:
            pass  # Column already exists

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
        _populate_xg_patches(conn)
        _populate_xg_drumkits(conn)
    else:
        # Check if XG data exists; add it if not (migration for databases
        # created before XG support was added)
        cursor.execute("SELECT COUNT(*) FROM patches WHERE standard = 'XG'")
        if cursor.fetchone()[0] == 0:
            _populate_xg_patches(conn)
            _populate_xg_drumkits(conn)

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
    """Populate GS patches from GS_INSTRUMENTS data.

    Each entry: (msb, pc, sc8850_name, sc88pro_name, sc88_name, sc55_name)
    bank_lsb encodes Sound Canvas generation: 4=SC-8850, 3=SC-88Pro,
    2=SC-88, 1=SC-55. Empty name means the patch does not exist on that
    generation.
    """
    cursor = conn.cursor()
    cc32_values = [4, 3, 2, 1]  # Columns: SC-8850, SC-88Pro, SC-88, SC-55

    for row in GS_INSTRUMENTS:
        msb, pc = row[0], row[1]
        for col_idx, cc32 in enumerate(cc32_values):
            name = row[2 + col_idx]
            if name:
                cursor.execute("""
                    INSERT OR IGNORE INTO patches
                    (standard, bank_msb, bank_lsb, program, name, category)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ("GS", msb, cc32, pc, name, None))

    conn.commit()


def _populate_gs_drumkits(conn):
    """Populate GS drum kits from GS_DRUMKITS data.

    Each entry: (pc, sc8850_name, sc88pro_name, sc88_name, sc55_name)
    bank_msb is always 0 for GS drum kits. Empty name means the kit does
    not exist on that generation.
    """
    cursor = conn.cursor()
    cc32_values = [4, 3, 2, 1]  # Columns: SC-8850, SC-88Pro, SC-88, SC-55

    for row in GS_DRUMKITS:
        pc = row[0]
        for col_idx, cc32 in enumerate(cc32_values):
            name = row[1 + col_idx]
            if name:
                cursor.execute("""
                    INSERT OR IGNORE INTO percussion_sets
                    (standard, bank_msb, bank_lsb, program, name)
                    VALUES (?, ?, ?, ?, ?)
                """, ("GS", 0, cc32, pc, name))

    conn.commit()


def _populate_xg_patches(conn):
    """Populate XG patches.

    Adds Level 1 basic voices (Bank MSB=0, LSB=0) and Level 2/3 extension
    voices. minimum_level: 1=XG Level 1, 2=MU100+, 3=MU128 only.
    """
    cursor = conn.cursor()

    # Basic XG voices at (MSB=0, LSB=0) — all Level 1
    for program, name, category in XG_BASIC_INSTRUMENTS:
        cursor.execute("""
            INSERT OR IGNORE INTO patches
            (standard, bank_msb, bank_lsb, program, name, category, minimum_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("XG", 0, 0, program, name, category, 1))

    # Extension bank voices (Level 2 and Level 3)
    for bank_msb, bank_lsb, program, name, category, minimum_level in XG_EXTENSION_INSTRUMENTS:
        cursor.execute("""
            INSERT OR IGNORE INTO patches
            (standard, bank_msb, bank_lsb, program, name, category, minimum_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("XG", bank_msb, bank_lsb, program, name, category, minimum_level))

    conn.commit()


def _populate_xg_drumkits(conn):
    """Populate XG drum kits.

    Adds standard XG percussion kits (MSB=127) and SFX kits (MSB=126).
    minimum_level: 1=XG Level 1, 2=MU100+, 3=MU128 only.
    """
    cursor = conn.cursor()

    for bank_msb, bank_lsb, program, name, minimum_level in XG_DRUMKITS:
        cursor.execute("""
            INSERT OR IGNORE INTO percussion_sets
            (standard, bank_msb, bank_lsb, program, name, minimum_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("XG", bank_msb, bank_lsb, program, name, minimum_level))

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

        # When no CC32 was sent (bank_lsb=0), the SC generation is unknown.
        # Try the stated bank_msb with each SC generation LSB (1–4) so that
        # variation names (e.g. MSB=8 → "Brass 2") are resolved rather than
        # always falling back to the MSB=0 base patch.
        if not result and bank_lsb == 0:
            for gen_lsb in range(1, 5):
                cursor.execute("""
                    SELECT name, category FROM patches
                    WHERE standard = 'GS' AND bank_msb = ? AND bank_lsb = ? AND program = ?
                """, (bank_msb, gen_lsb, program))
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
        # Final GS fallback: try all SC generations (lsb 1–4) when no CC32 was sent
        # (bank_lsb=0 means no CC32; kits like "STANDARD 2" only exist at lsb≥2)
        if not result and bank_lsb == 0:
            for gen_lsb in range(1, 5):
                cursor.execute("""
                    SELECT name FROM percussion_sets
                    WHERE standard = 'GS' AND bank_msb = ? AND bank_lsb = ? AND program = ?
                """, (bank_msb, gen_lsb, program))
                result = cursor.fetchone()
                if result:
                    break
        elif not result:
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
