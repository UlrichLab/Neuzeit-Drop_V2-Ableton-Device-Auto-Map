"""Erzeugt die Drop-Projektdatei fuer Drop V2 aus dem DAW-Init-Projekt.

Aufruf:  python3 tools/make_drop_project.py [daw-init.json] [Ausgabe.json]

Aenderungen gegenueber DAW Init auf Layer A:
  - 32 Regler: LED-Stil "MIDI Col Line from left" (Bogen ab 0 wie in Live) + zweiter
    Slot "Feedback Only" fuer die Farbe; Namen Macro 1-24 und Send 1-8 (alle Namen am Drop englisch)
  - 32 Regler-Pushes: senden Noten (Verhalten "Temporary")
  - 8 Tasten und 8 Fader: Namen fuer ihre Drop-V2-Funktion; Fader 1 rot (Volume),
    Fader 2-8 weiss und ohne Funktion; Tastenfarben siehe BUTTON_COLORS
  - Fader "One per Layer", damit Layer B-E eigene Fader haben
Auf Layer B-E (Spur 1-8, 9-16, 17-24, 25-32):
  - Fader "1 Vol" ... rot, Tasten "1 Mute" ... gelb, Layer-Namen "Vol 1-8" ... "Vol 25-32"
Allgemein:
  - alle Volume-Fader senden hoechstens VOLUME_FADER_MAX statt 127
  - Remote Receive "Jam" auf Kanal 16, damit das Skript den Drop auf Layer A schalten kann
  - Remote Send "Jam" auf Kanal 16, damit das Skript Layer- und Ring-Tasten sieht
  - "Send on Load" aus
Layer F-H bleiben wie bei DAW Init und koennen weiter von Hand gemappt werden.

Zahlen behalten beim Schreiben ihre Originalschreibweise (z.B. "52.000"), weil die
Drop-Firmware ihre eigenen Dateien so schreibt.
"""

import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _load_layout():
    spec = importlib.util.spec_from_file_location("drop_layout", os.path.join(ROOT, "Drop_V2", "layout.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


L = _load_layout()

# Codes aus dropedit/docs/drop-format.md (an Firmware 2.01 verifiziert).
MSG_NOTE_ON = 2
MSG_CC = 3
BEHAV_DYNAMIC_POT = 1
BEHAV_TEMPORARY = 4
BEHAV_ONE_PER_LAYER = 11
FEEDB_MIDI_COL_LINE_LEFT = 34
FEEDB_DEFAULT_BUTTON = 28
CURVE_LINEAR = 0
CURVE_ON_OFF_50 = 9
CURVE_FEEDBACK_ONLY = 34
REMOTE_LEVEL_JAM = 1
DEVICE_DAW = 0
COLOR_GOLD = 1
COLOR_AQUA = 5
COLOR_VIOLET = 6
COLOR_MAGENTA = 7
COLOR_WHITE = 8
COLOR_RED = 9
# Tasten Layer A: Spur und Geraet links violett (1, 7), rechts magenta (2, 8),
# 3-6 (Browser, Session/Arrange, Detail/Page, View/Reset) blau wie Taste 6 in DAW Init
BUTTON_COLORS = (COLOR_VIOLET, COLOR_MAGENTA, COLOR_AQUA, COLOR_AQUA, COLOR_AQUA,
                 COLOR_AQUA, COLOR_VIOLET, COLOR_MAGENTA)
# Der Drop speichert Min/Max 14-bit: angezeigt = round(gespeichert / 16383 * 127)
VOLUME_MAX_OUT = round(L.VOLUME_FADER_MAX * 16383 / 127)


class RawNumber(str):
    """Zahl, die genau so in die Datei geschrieben wird."""


def _parse_float(text):
    return RawNumber(text)


def _dump(value, indent=0):
    tab = "\t"
    if isinstance(value, RawNumber):
        return str(value)
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, dict):
        if not value:
            return "{\n" + tab * indent + "}"
        items = [tab * (indent + 1) + json.dumps(k) + ": " + _dump(v, indent + 1) for k, v in value.items()]
        return "{\n" + ",\n".join(items) + "\n" + tab * indent + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_dump(v, indent + 1) for v in value) + "]"
    raise TypeError("Unbekannter Typ: %r" % (value,))


def _slot(msg_type, channel, number, curve):
    return {
        "inUse": 1,
        "target": DEVICE_DAW,
        "msgType": msg_type,
        "ch": channel,
        "csvRef": 0,
        "msgNr": RawNumber("%d.000" % number),
        "maxOut": 16383,
        "minOut": 0,
        "curveId": curve,
    }


def _expect(control, channel, number, what):
    slot = control.get("0") or {}
    found = (slot.get("ch"), int(float(slot.get("msgNr", -1))))
    if found != (channel, number):
        raise SystemExit("%s: DAW Init hat %r, layout.py erwartet %r" % (what, found, (channel, number)))


def build(project):
    rotary = project["map"]["rotary"]
    rotbut = project["map"]["rotbut"]
    mute = project["map"]["mute"]
    fader = project["map"]["fader"]

    for index, cc in enumerate(L.KNOB_CCS):
        cid = L.knob_control_id(index)
        knob = rotary[cid]
        _expect(knob, L.KNOB_CHANNEL, cc, "Regler " + cid)
        knob["name"] = L.knob_name(index)
        knob["behavId"] = BEHAV_DYNAMIC_POT
        knob["feedbSlotVis"] = 2  # Slot 2 empfaengt die Farbe
        knob["feedbId"] = FEEDB_MIDI_COL_LINE_LEFT
        knob["feedbSlot"] = 1     # Slot 1 empfaengt den Wert (LED-Ring folgt Live)
        knob["1"] = _slot(MSG_CC, L.KNOB_COLOR_CHANNEL, cc, CURVE_FEEDBACK_ONLY)

        push = rotbut[cid]
        push["name"] = "Push %02d" % (index + 1)
        push["behavId"] = BEHAV_TEMPORARY
        push["feedbSlot"] = 0
        push["0"] = _slot(MSG_NOTE_ON, L.PUSH_CHANNEL, L.KNOB_PUSH_NOTES[index], CURVE_ON_OFF_50)

    for index, note in enumerate(L.BUTTON_NOTES):
        button = mute["0%d" % index]
        _expect(button, L.PUSH_CHANNEL, note, "Taste %d" % (index + 1))
        button["name"] = L.BUTTON_NAMES[index]
        button["colId"] = BUTTON_COLORS[index]
        button["behavId"] = BEHAV_TEMPORARY
        button["feedbId"] = FEEDB_DEFAULT_BUTTON
        button["feedbSlot"] = 1

    for index, cc in enumerate(L.FADER_CCS):
        control = fader["0%d" % index]
        _expect(control, L.FADER_CHANNEL, cc, "Fader %d" % (index + 1))
        control["name"] = L.FADER_NAMES[index]
        control["behavId"] = BEHAV_ONE_PER_LAYER
        control["colId"] = COLOR_RED if index == 0 else COLOR_WHITE
    fader["00"]["0"]["maxOut"] = VOLUME_MAX_OUT

    track = 0
    for layer, name in zip(L.TRACK_LAYERS, L.TRACK_LAYER_NAMES):
        number = layer["layer"]
        project["layers"][str(number)]["name"] = name
        for index, (cc, note) in enumerate(zip(layer["fader_ccs"], layer["button_notes"])):
            cid = "%d%d" % (number, index)
            control = fader[cid]
            _expect(control, layer["fader_channel"], cc, "Fader " + cid)
            control["name"] = L.track_fader_name(track)
            control["behavId"] = BEHAV_ONE_PER_LAYER
            control["colId"] = COLOR_RED
            control["0"]["maxOut"] = VOLUME_MAX_OUT
            button = mute[cid]
            _expect(button, layer["button_channel"], note, "Taste " + cid)
            button["name"] = L.track_button_name(track)
            button["behavId"] = BEHAV_TEMPORARY
            button["colId"] = COLOR_GOLD
            button["feedbId"] = FEEDB_DEFAULT_BUTTON
            button["feedbSlot"] = 1
            track += 1

    remote = project["remote"]
    remote["levelRx"] = REMOTE_LEVEL_JAM
    remote["deviceRx"] = DEVICE_DAW
    remote["chanRx"] = L.REMOTE_CHANNEL
    # Layer- und Ring-Tasten melden sich so beim Skript (CC 40 / CC 39)
    remote["levelTx"] = REMOTE_LEVEL_JAM
    remote["deviceTx"] = DEVICE_DAW
    remote["chanTx"] = L.REMOTE_CHANNEL

    # Sonst sendet der Drop beim Laden alle gespeicherten Reglerwerte und verstellt
    # damit das gerade ausgewaehlte Geraet in Live.
    project["settings"]["sendOnLoad"] = 0

    project["layers"]["0"]["name"] = "Drop V2"
    return project


def main(argv):
    source = argv[1] if len(argv) > 1 else os.path.join(HERE, "daw-init.json")
    target = argv[2] if len(argv) > 2 else os.path.join(ROOT, "Drop_V2_Projekt.json")
    with open(source, encoding="utf-8") as handle:
        project = json.load(handle, parse_float=_parse_float)
    build(project)
    text = _dump(project) + "\n"
    json.loads(text)  # muss gueltiges JSON bleiben
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("geschrieben:", target)


if __name__ == "__main__":
    main(sys.argv)
