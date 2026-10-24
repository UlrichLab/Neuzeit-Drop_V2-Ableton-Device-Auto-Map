# Drop V2 - feste Hardware-Belegung des Neuzeit Drop auf Layer A.
#
# Abgeleitet aus "MENU > Project > DAW Init" (Firmware 2.01). Diese Datei ist die
# einzige Quelle der Belegung: das Remote Script liest sie, und
# tools/make_drop_project.py erzeugt daraus die passende Drop-Projektdatei.
#
# Kanaele sind 1-basiert wie im Drop-Menue. Das Skript rechnet intern auf 0-15 um.

KNOB_CHANNEL = 1        # Regler drehen: CC
KNOB_COLOR_CHANNEL = 9  # Regler-Farbe (LED-Stil "MIDI Col Line from left"): CC, nur Empfang
PUSH_CHANNEL = 2        # Regler druecken und die 8 Tasten: Noten
FADER_CHANNEL = 1       # Fader: CC
REMOTE_CHANNEL = 16     # Remote-Befehle (Drop: MENU > Remote > Receive und Send = Jam)

DEVICE_KNOBS = 24  # Reihe 1-3: Parameter des Geraets, so viele pro Seite
SEND_KNOBS = 8     # Reihe 4: Send A-H der ausgewaehlten Spur
KNOB_COLUMNS = 8

# CC der 32 Regler, Reihe fuer Reihe von oben, Spalte 1-8 (CC 6 und 32 laesst DAW Init aus).
KNOB_CCS = (
    1, 2, 3, 4, 5, 7, 8, 9,
    10, 11, 12, 13, 14, 15, 16, 17,
    18, 19, 20, 21, 22, 23, 24, 25,
    26, 27, 28, 29, 30, 31, 33, 34,
)

# Regler-Push sendet eine Note mit derselben Nummer wie der Regler-CC.
KNOB_PUSH_NOTES = KNOB_CCS

# Die 8 Tasten ueber den Fadern (Note 38 laesst DAW Init aus).
BUTTON_NOTES = (35, 36, 37, 39, 40, 41, 42, 43)
BUTTON_NAMES = (
    "< Track",
    "Track >",
    "Browser",
    "Session/Arrange",
    "Detail/Page",
    "View/Reset",
    "< Device",
    "Device >",
)
BTN_PREV_TRACK = 0
BTN_NEXT_TRACK = 1
BTN_BROWSER = 2  # Browser ein/aus
BTN_MAIN_VIEW = 3  # Session- / Arrangement-Ansicht
BTN_DETAIL_PAGE = 4  # kurz: Detailansicht ein/aus, 1 s halten: naechste Seite (reihum)
BTN_PROFILE_RESET = 5  # kurz: Clip-/Geraeteansicht wechseln, 3 s halten: Profil Reset
BTN_PREV_DEVICE = 6
BTN_NEXT_DEVICE = 7

# Fader 1 = Volume der ausgewaehlten Spur, Fader 2-8 ohne Funktion (Sends liegen auf Reihe 4).
# Namen stehen fest in der Projektdatei (hoechstens 15 Zeichen), der Drop nimmt keine per MIDI an.
FADER_CCS = (44, 45, 46, 47, 48, 49, 50, 51)
FADER_NAMES = ("Track Volume",) + tuple("%d none" % number for number in range(2, 9))
# Hoechster MIDI-Wert aller Volume-Fader: 108 = 0 dB in Live (Volume 0.85 von 0-1),
# naeher kommt ein 7-bit-CC nicht heran.
VOLUME_FADER_MAX = 108

# Layer B-E: Fader = Volume, Tasten = Mute (halten: Aufnahme scharf) fester Spuren,
# Layer B Spur 1-8, C 9-16, D 17-24, E 25-32. Kanaele und Nummern wie in DAW Init.
UPPER_FADER_CCS = (92, 93, 94, 95, 96, 99, 100, 101)   # Layer B und D
UPPER_BUTTON_NOTES = (84, 85, 86, 87, 88, 89, 90, 91)  # Layer B und D
TRACK_LAYERS = (
    {"layer": 1, "fader_channel": 1, "fader_ccs": UPPER_FADER_CCS,
     "button_channel": 2, "button_notes": UPPER_BUTTON_NOTES},
    {"layer": 2, "fader_channel": 3, "fader_ccs": FADER_CCS,
     "button_channel": 4, "button_notes": BUTTON_NOTES},
    {"layer": 3, "fader_channel": 3, "fader_ccs": UPPER_FADER_CCS,
     "button_channel": 4, "button_notes": UPPER_BUTTON_NOTES},
    {"layer": 4, "fader_channel": 5, "fader_ccs": FADER_CCS,
     "button_channel": 6, "button_notes": BUTTON_NOTES},
)
TRACK_LAYER_NAMES = ("Vol 1-8", "Vol 9-16", "Vol 17-24", "Vol 25-32")
TRACK_ARM_HOLD_SECONDS = 1.0


def track_fader_name(track_index):
    """Name am Drop, die Zahl zuerst: "1 Vol" ... "32 Vol"."""
    return "%d Vol" % (track_index + 1)


def track_button_name(track_index):
    return "%d Mute" % (track_index + 1)

# Remote-CCs des Drop (Handbuch v2.03, "MIDI table to control Drop remotely").
REMOTE_CC_BEATJUMP = 39
REMOTE_CC_LAYER = 40

# Ring-Tasten um das Display: Remote Send "Jam" meldet sie als CC 39 mit Wert 1-8,
# im Uhrzeigersinn. Sie loesen am Drop zugleich einen Beatjump aus und senden nur,
# solange die Wiedergabe laeuft.
RING_NEXT_TRACK = 2
RING_NEXT_DEVICE = 3
RING_PREV_DEVICE = 6
RING_PREV_TRACK = 7

# Farbwerte fuer "MIDI Col": 0 = keine Aenderung, 1-127 = Farbkreis
# Rot > Gelb > Gruen > Cyan > Blau > Magenta > Rot.
HUE_LEARNED = 43  # gruen: gelernt und gespeichert
HUE_AUTO = 85     # blau: automatisch belegt
HUE_SEND = 22     # gelb: Send der ausgewaehlten Spur
HUE_EMPTY = 1     # rot: frei

# --- Clip-Launcher im Grid-Modus des Drop ("DAW Grid Mode") ------------------------------
# Protokoll wie in Neuzeits Skript Drop_v01: Noten auf Kanal 16, LEDs per Velocity.
# Die Tastenmatrix hat 4 Spalten x 5 Reihen, obere Ebene Note 88-107, Shift-Ebene 108-127.
GRID_CHANNEL = 16
GRID_TRACKS = 4
GRID_SCENES = 4
GRID_STOP_ROW = 4        # Reihe 5 der oberen Ebene: Spur stoppen
GRID_REQUEST_NOTE = 83   # der Drop bittet um alle LEDs
GRID_LEFT_NOTE = 84      # blaue Tasten: Clip-Box verschieben
GRID_UP_NOTE = 85
GRID_DOWN_NOTE = 86
GRID_RIGHT_NOTE = 87
GRID_FIRST_NOTE = 88
GRID_LAST_NOTE = 127
GRID_STOP_ALL_NOTE = 127  # Shift-Ebene unten rechts

# LED-Velocity: Clipfarbe 2-15, dazu Statusbits
GRID_LED_EMPTY = 1
GRID_LED_STOP = 15
GRID_LED_TRIGGERED = 16
GRID_LED_RECORDING = 32
GRID_LED_PLAYING = 64
GRID_LED_SCENE_DROP = 2
GRID_LED_SCENE_LAUNCH = 7
GRID_LED_REQUEST = 100


def grid_note(column, row, shift=False):
    """Note der Matrix-Taste in Spalte 0-3, Reihe 0-4 (von oben)."""
    return GRID_FIRST_NOTE + (20 if shift else 0) + row * GRID_TRACKS + column


def knob_position(index):
    """Gibt (Spalte, Reihe) 0-basiert fuer Regler 0-31 zurueck."""
    return index % KNOB_COLUMNS, index // KNOB_COLUMNS


def knob_name(index):
    """Name des Reglers am Drop: Macro 1-24 in Reihe 1-3, Send 1-8 in Reihe 4."""
    if index < DEVICE_KNOBS:
        return "Macro %d" % (index + 1)
    return "Send %d" % (index - DEVICE_KNOBS + 1)


def knob_control_id(index, layer=0):
    """Control-ID im Drop-Projekt: <Layer><Spalte><Reihe>."""
    column, row = knob_position(index)
    return "%d%d%d" % (layer, column, row)
