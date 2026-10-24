"""Zeichnet die Belegungsgrafiken fuer die README (docs/*.svg).

Aufruf:  python3 tools/make_layout_svgs.py [Zielordner]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(HERE), "docs")
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"
INK = "#1d2330"
MUTED = "#5b6475"
PANEL = "#f4f5f7"
LINE = "#c9ced8"

BLUE = ("#dbe7ff", "#2f6fdb")
YELLOW = ("#fff1bf", "#c99a00")
VIOLET = "#7b3fe4"
MAGENTA = "#c934c9"
AQUA = "#1e88e5"
GOLD = "#d9a400"
RED = "#e5322d"

COLS = [150 + i * 96 for i in range(8)]


def text(x, y, s, size=14, weight="normal", fill=INK, anchor="middle"):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return ('<text x="%g" y="%g" font-family="%s" font-size="%d" font-weight="%s" fill="%s" '
            'text-anchor="%s">%s</text>' % (x, y, FONT, size, weight, fill, anchor, s))


def svg(width, height, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">\n'
            '<rect width="100%%" height="100%%" fill="#ffffff"/>\n%s\n</svg>\n'
            % (width, height, width, height, "\n".join(body)))


def knob(x, y, label, colors):
    fill, stroke = colors
    return ['<circle cx="%g" cy="%g" r="25" fill="%s" stroke="%s" stroke-width="4"/>' % (x, y, fill, stroke),
            text(x, y + 5, label, 13, "bold")]


def button(x, y, color, lines):
    out = ['<rect x="%g" y="%g" width="72" height="34" rx="7" fill="%s"/>' % (x - 36, y, color)]
    for i, line in enumerate(lines):
        out.append(text(x, y + 56 + i * 16, line, 13, "bold" if i == 0 else "normal"))
    return out


def fader(x, y, cap, label, sub=None):
    out = ['<rect x="%g" y="%g" width="10" height="130" rx="5" fill="%s"/>' % (x - 5, y, LINE),
           '<rect x="%g" y="%g" width="46" height="22" rx="4" fill="%s" stroke="%s" stroke-width="2"/>'
           % (x - 23, y + 18, cap, INK if cap == "#ffffff" else cap),
           text(x, y + 158, label, 13, "bold")]
    if sub:
        out.append(text(x, y + 174, sub, 12, fill=MUTED))
    return out


def legend(x, y, rows):
    out = []
    for i, (swatch, label) in enumerate(rows):
        yy = y + i * 28
        out.append('<circle cx="%g" cy="%g" r="8" fill="%s" stroke="%s" stroke-width="3"/>' % (x, yy - 5, swatch[0], swatch[1]))
        out.append(text(x + 18, yy, label, 15, anchor="start"))
    return out


def layer_a():
    body = [text(40, 48, "Neuzeit Drop V2 – Layer A (device control)", 24, "bold", anchor="start"),
            text(40, 74, "Select a device in Live: its parameters land on knob rows 1–3, the track's sends on row 4.",
                 14, fill=MUTED, anchor="start"),
            '<rect x="24" y="96" width="852" height="700" rx="18" fill="%s"/>' % PANEL]
    rows_y = [150, 222, 294, 366]
    for row, y in enumerate(rows_y):
        body.append(text(64, y + 5, "Row %d" % (row + 1), 13, "bold", MUTED))
        for col, x in enumerate(COLS):
            if row < 3:
                body += knob(x, y, str(row * 8 + col + 1), BLUE)
            else:
                body += knob(x, y, "S%d" % (col + 1), YELLOW)
    body.append(text(450, 418, "Rows 1–3: Macro 1–24 of the selected device · Row 4: Send 1–8 of the selected track",
                     13, fill=MUTED))

    buttons = [(VIOLET, ["< Track"]), (MAGENTA, ["Track >"]), (AQUA, ["Browser", "show/hide"]),
               (AQUA, ["Session/", "Arrange"]), (AQUA, ["Detail/Page", "hold 1 s: page"]),
               (AQUA, ["View/Reset", "hold 3 s: reset"]), (VIOLET, ["< Device"]), (MAGENTA, ["Device >"])]
    body.append(text(64, 470, "Buttons", 13, "bold", MUTED))
    for x, (color, lines) in zip(COLS, buttons):
        body += button(x, 452, color, lines)

    body.append(text(64, 620, "Faders", 13, "bold", MUTED))
    body += fader(COLS[0], 580, RED, "Volume", "max 0 dB")
    for x in COLS[1:]:
        body += fader(x, 580, "#ffffff", "–")

    side = 910
    body.append(text(side, 130, "Knob colours", 17, "bold", anchor="start"))
    body += legend(side + 8, 162, [(BLUE, "blue: auto mapped"), (("#d7f5d7", "#2e9e3e"), "green: learned"),
                                   (YELLOW, "yellow: send"), (("#ffdcdc", RED), "red: empty")])
    body.append(text(side, 290, "Knob push", 17, "bold", anchor="start"))
    for i, line in enumerate(["short: back to default",
                              "hold + click a parameter",
                              "in Live: learn it (saved)",
                              "hold 2 s: clear the knob"]):
        body.append(text(side, 320 + i * 24, line, 15, anchor="start"))
    body.append(text(side, 440, "Buttons", 17, "bold", anchor="start"))
    for i, line in enumerate(["lit: function possible now",
                              "dimmed: e.g. last device",
                              "on the track"]):
        body.append(text(side, 470 + i * 24, line, 15, anchor="start"))
    body.append(text(side, 560, "Learned layouts", 17, "bold", anchor="start"))
    for i, line in enumerate(["are saved per device type", "and come back in every set"]):
        body.append(text(side, 590 + i * 24, line, 15, anchor="start"))
    return svg(1200, 820, body)


def layers_b_e():
    body = [text(40, 48, "Neuzeit Drop V2 – Layers B–E (mixer)", 24, "bold", anchor="start"),
            text(40, 74, "Fixed tracks: B = tracks 1–8, C = 9–16, D = 17–24, E = 25–32", 14, fill=MUTED, anchor="start"),
            '<rect x="24" y="96" width="852" height="400" rx="18" fill="%s"/>' % PANEL,
            text(64, 160, "Buttons", 13, "bold", MUTED)]
    for i, x in enumerate(COLS):
        body += button(x, 142, GOLD, ["%d Mute" % (i + 1)])
    body.append(text(64, 290, "Faders", 13, "bold", MUTED))
    for i, x in enumerate(COLS):
        body += fader(x, 250, RED, "%d Vol" % (i + 1), "max 0 dB" if i == 0 else None)
    body.append(text(450, 478, "Layer B shown. Layer C reads 9 Mute / 9 Vol … 16, D 17 … 24, E 25 … 32.", 13, fill=MUTED))
    side = 910
    body.append(text(side, 130, "Mute buttons", 17, "bold", anchor="start"))
    for i, line in enumerate(["short: mute on/off", "hold 1 s: record arm", "lit: track playing", "dimmed: track muted"]):
        body.append(text(side, 160 + i * 24, line, 15, anchor="start"))
    body.append(text(side, 280, "Faders", 17, "bold", anchor="start"))
    for i, line in enumerate(["volume, top = 0 dB", "each layer has its own faders:", "after switching, move a", "fader to its value first"]):
        body.append(text(side, 310 + i * 24, line, 15, anchor="start"))
    return svg(1200, 520, body)


os.makedirs(OUT, exist_ok=True)
for name, content in (("layout-layer-a.svg", layer_a()), ("layout-layers-b-e.svg", layers_b_e())):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as handle:
        handle.write(content)
    print("written", name)
