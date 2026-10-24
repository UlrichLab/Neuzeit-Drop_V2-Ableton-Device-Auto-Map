# Drop V2 – Geräte-Steuerung für den Neuzeit Drop in Ableton Live 12

Drop V2 legt die Parameter des ausgewählten Geräts automatisch auf die Regler-Reihen 1–3 von **Layer A**, Reihe 4 zeigt die Sends der Spur.
Auf **Layer B, C, D und E** regeln die Fader das Volume von Spur 1–8, 9–16, 17–24 und 25–32, die Tasten schalten diese Spuren stumm.
Belegungen, die du lernst, werden **pro Gerätetyp** gespeichert und gelten danach in jeder Spur und in jedem Live-Set.
Der Clip-Launcher für die Tastenmatrix (Grid-Modus) ist eingebaut. Neuzeits Skript `Drop_v01` wird nicht mehr gebraucht.

## Inhalt dieses Ordners

| Datei | Zweck |
|---|---|
| `Drop_V2/` | das Remote Script (ist schon in deine User Library kopiert) |
| `Drop_V2_Projekt.json` | Projektdatei für den Drop, einmal per SD-Karte laden |
| `tools/make_drop_project.py` | erzeugt die Projektdatei neu, falls `Drop_V2/layout.py` geändert wird |
| `tests/` | Ablauftests ohne Live: `python3 -I tests/test_dropv2.py` |

## 1. Drop vorbereiten (einmalig)

1. Dein aktuelles Projekt am Drop sichern (MENU → Project → Save), und zwar **unter einem anderen Namen**, z. B. `Drop_V2_alt`. Speicherst du unter `Drop_V2_Projekt`, überschreibt der Drop damit die neue Datei auf der SD-Karte.
2. `Drop_V2_Projekt.json` auf die SD-Karte in den Ordner **`/Projects`** kopieren und die alte Datei dabei ersetzen.
3. Am Drop laden: MENU → Project → Load → `Drop_V2_Projekt`.
4. Prüfen: Taste 3 drücken, im Display muss „Browser“ stehen.

Nötig ist Firmware **2.01 oder neuer** (wegen der MIDI-gesteuerten Reglerfarben).
Die Datei ist DAW Init mit diesen Änderungen:
- **Regler (Layer A):** LED-Stil „MIDI Col Line from left“ mit Farb-Slot. Der LED-Ring zeigt einen Bogen ab 0, wie die Regler in Live.
- **Regler-Push (Layer A):** sendet Noten.
- **Fader (Layer A):** Fader 1 rot („Track Volume“), Fader 2–8 weiß und ohne Funktion („2 none“ … „8 none“).
- **Tasten (Layer A):** „< Track“, „Track >“, „Browser“, „Session/Arrange“, „Detail/Page“, „View/Reset“, „< Device“, „Device >“. 1 und 7 violett, 2 und 8 magenta, 3–6 blau.
- **Layer B „Vol 1-8“, C „Vol 9-16“, D „Vol 17-24“ und E „Vol 25-32“:** Fader rot („1 Vol“ … „32 Vol“), Tasten gelb („1 Mute“ … „32 Mute“).
- **Alle Volume-Fader** senden oben höchstens MIDI-Wert 108 statt 127. Ganz oben steht die Spur in Live auf 0 dB.
- **Fader-Verhalten „One per Layer“:** Jeder Layer hat eigene Fader. Nach einem Layerwechsel greift ein Fader erst, wenn du ihn auf seinen gespeicherten Wert geschoben hast.
- **Namen:** Regler „Macro 1“–„Macro 24“ (Reihe 1–3) und „Send 1“–„Send 8“ (Reihe 4).
  Alle Namen am Drop sind englisch, damit du das Projekt auch mit englischsprachigen Leuten teilen kannst. Die Namen stehen fest in der Datei. Der Drop nimmt keine Namen per MIDI an, deshalb zeigt er weder Spurnamen noch, wie viele Sends es gibt.
- **Einstellungen:** Remote Receive und Remote Send stehen auf „Jam“ (Gerät DAW, Kanal 16), „Send on Load“ ist aus.

Layer F–H sind unverändert DAW Init. Dort kannst du weiter von Hand mit Cmd+M mappen.

## 2. Live einrichten (einmalig)

1. Live neu starten (das Skript liegt schon in `User Library/Remote Scripts/Drop_V2`).
2. Einstellungen → Link, Tempo & MIDI → Control Surface:
   - In einem freien Slot (bei dir **3 oder 7**) **Drop_V2** wählen, Input und Output: **DROP USB1**.
   - `Drop_v01` aus Slot 4 **entfernen** (auf „None“). Drop V2 enthält den Clip-Launcher. Liefen beide, würde jede Clip-Taste doppelt auslösen.
3. Bei den MIDI-Ports für DROP USB1 **Remote** bei Input und Output einschalten.
4. In alten Sets, in denen du Layer A, B oder C von Hand gemappt hast, diese Mappings entfernen, sonst kommen sie sich mit Drop V2 in die Quere:
   - Layer A: Kanal 1 CC 1–34 und 44–51, Kanal 2 Noten 1–43
   - Layer B: Kanal 1 CC 92–101, Kanal 2 Noten 84–91
   - Layer C: Kanal 3 CC 44–51, Kanal 4 Noten 35–43
   - Layer D: Kanal 3 CC 92–101, Kanal 4 Noten 84–91
   - Layer E: Kanal 5 CC 44–51, Kanal 6 Noten 35–43

## 3. Bedienung auf Layer A

| Element | Funktion |
|---|---|
| Regler Reihe 1–3 | Parameter des ausgewählten Geräts; der LED-Ring zeigt den Wert aus Live |
| Regler Reihe 4 | Send 1–8 (in Live Send A–H) der ausgewählten Spur, nur so viele, wie die Spur hat |
| Regler kurz drücken | Parameter auf Standardwert |
| Regler halten + Parameter in Live anklicken | Parameter auf diesen Regler **lernen** (gespeichert) |
| Regler 2 s halten, ohne Klick | Regler für dieses Gerät **freigeben** |
| Taste 1 / 2 | ◀ Spur / Spur ▶ |
| Taste 3 | Browser ein- und ausblenden |
| Taste 4 | zwischen Session- und Arrangement-Ansicht wechseln |
| Taste 5 kurz | Detailansicht (unten: Clip oder Gerät) ein- und ausblenden |
| Taste 5, 1 s halten | nächste Seite (bei mehr als 24 Parametern), nach der letzten wieder Seite 1 |
| Taste 6 kurz | zwischen Clip- und Geräteansicht wechseln |
| Taste 6, 3 s halten | Profil des Geräts löschen → wieder automatisch |
| Taste 7 / 8 | ◀ Gerät / Gerät ▶ (in der ausgewählten Spur) |
| Ring-Taste 7 / 2 | ◀ Spur / Spur ▶ (nur bei laufender Wiedergabe, siehe 6.) |
| Ring-Taste 6 / 3 | ◀ Gerät / Gerät ▶ (nur bei laufender Wiedergabe, siehe 6.) |
| Fader 1 | Volume der ausgewählten Spur; ganz oben = 0 dB (MIDI-Wert 108) |
| Fader 2–8 | keine Funktion, die Sends liegen auf Reihe 4 |

Die Tasten leuchten, wenn ihre Funktion gerade möglich ist. Taste 6 leuchtet, wenn das Gerät ein gelerntes Profil hat.
In Lives Statuszeile steht jeweils, welches Gerät und welche Seite gerade auf dem Drop liegen.

**Reglerfarben:** grün = gelernt · blau = automatisch belegt · gelb = Send · rot = frei

In Reihe 4 wird nichts gelernt, sie gehört immer den Sends. Kurz drücken setzt auch einen Send auf seinen Standardwert.

**Automatische Belegung**, solange nichts gelernt ist:
- **Racks:** Makro 1–8 in Reihe 1, Makro 9–16 in Reihe 2. Was auf den Makros liegt, speichert Live im Rack-Preset.
- **Live-Geräte:** Abletons eigene Parameterbänke (wie bei Push), eine Bank pro Reihe, drei Bänke pro Seite.
- **Max-for-Live-Geräte** (z. B. Shaper): lückenlos ab Regler 1, erst die Parameter der Hauptbank, dann die der übrigen Bänke, dann alle restlichen.
- Jeder Parameter liegt nur auf einem Regler. Bänke von Live-Geräten ohne einen einzigen Parameter fallen weg, damit die Belegung in Reihe 1 anfängt.
- **Plugins:** die Parameter der Reihe nach, 24 pro Seite.

## 4. Layer B bis E – Volume und Mute fester Spuren

| Layer | Fader 1–8 = Volume | Taste kurz = Mute an/aus, 1 s halten = Aufnahme scharf an/aus |
|---|---|---|
| B „Vol 1-8“ | Spur 1–8 („1 Vol“ … „8 Vol“) | Spur 1–8 („1 Mute“ … „8 Mute“) |
| C „Vol 9-16“ | Spur 9–16 | Spur 9–16 |
| D „Vol 17-24“ | Spur 17–24 | Spur 17–24 |
| E „Vol 25-32“ | Spur 25–32 | Spur 25–32 |

- Die Spurnummern sind die Nummern in Lives Spurköpfen. Gruppenspuren zählen mit, auch wenn die Gruppe zugeklappt ist.
- Die Auswahl in Live ändert an Layer B bis E nichts.
- Die Tasten leuchten wie Lives Spur-Aktivator: hell = Spur spielt, gedimmt = stumm. Ganz dunkel geht nicht, die Tasten des Drop kennen nur hell und gedimmt.
- Die Volume-Fader gehen wie Fader 1 auf Layer A ganz oben bis 0 dB.
- Fehlt eine Spur (z. B. Fader 6 bei nur 5 Spuren), tut der Fader nichts.
- Shift + Taste geht nicht: Die Shift-Taste des Drop schickt kein MIDI an Live. Deshalb Halten statt Shift.
- Ob eine Spur scharf ist, zeigt die Taste nicht (sie hat nur ein Licht). Lives Statuszeile meldet es beim Umschalten.

## 5. Lernen – so wird gespeichert

Ein Profil gehört zum **Gerätetyp**, nicht zur Spur und nicht zum Set:
- **Live-Geräte** (z. B. Auto Filter) zählen nur nach Typ. Ein umbenannter Auto Filter nutzt dasselbe Profil.
- **Racks, Plugins und Max-Geräte** zählen nach Typ **und Name**. Speichere deine Racks deshalb mit eigenem Namen. Alle Racks mit dem Standardnamen „Audio Effect Rack“ teilen sich ein Profil.

Beispiel: Du lernst „Mein FX Rack“ auf Spur 1. Legst du in einer neuen Spur oder einem neuen Set „Mein FX Rack“ als erstes Gerät an, liegt sofort dieselbe Belegung auf dem Drop.

Beim ersten Lernen übernimmt das Profil die automatische Belegung, und nur der gelernte Regler ändert sich.
Lag der Parameter schon auf einem anderen Regler, wandert er auf den neuen. Der Parameter, der vorher auf dem neuen Regler lag, fällt dabei weg.
Gespeichert wird sofort beim Lernen, einen Speichern-Knopf gibt es nicht.

**Reihenfolge ändern**, Beispiel: Beim Saturator soll Dry/Wet auf Regler 1, Drive liegt dort.
1. Regler 1 halten, in Live „Dry/Wet“ anklicken, loslassen. Dry/Wet wandert auf Regler 1, Drive ist erst einmal weg.
2. Den Regler halten, auf dem Drive landen soll, „Drive“ anklicken, loslassen.

Ab dann haben alle Saturator in jedem Set diese Reihenfolge. Ein Live-Preset musst du dafür nicht speichern.
Zurück zur automatischen Belegung: Taste 6 drei Sekunden halten.
Klickst du einen Parameter an, der schon ausgewählt war, meldet Live keine Änderung. Klick dann kurz einen anderen Parameter an und danach wieder den gewünschten.

Die Profile liegen in `~/Music/Ableton/User Library/Drop V2 Profile/profiles.json`. Sichere diese Datei mit deiner User Library.

## 6. Ring-Tasten und Takt

Die 8 Ring-Tasten um das Display werden im Uhrzeigersinn gezählt.
- **2 / 7:** Spur ▶ / ◀ Spur
- **3 / 6:** Gerät ▶ / ◀ Gerät
- **1, 4, 5, 8:** keine Funktion in Drop V2

Damit das funktioniert, muss am Drop unter MENU → Remote **Send** auf „Jam“, Gerät DAW, Kanal 16 stehen. In `Drop_V2_Projekt.json` ist das schon eingestellt.
**„JUMP by MIDI notes“** auf derselben Seite bleibt auf **Off**.

Die Ring-Tasten lösen am Drop immer auch einen Beatjump aus. Deshalb melden sie sich **nur bei laufender Wiedergabe**. Steht Live, nimmst du die Tasten 1, 2, 7 und 8.

**Takt:** Live gibt den Takt vor.
- **Live:** Beim Ausgang DROP USB1 Sync an (MIDI Clock, Typ „Song“), beim Eingang Sync aus.
- **Drop:** Unter Shift + clock die Source auf „Ext MIDI“ stellen.

So verschiebt ein Beatjump nie Lives Abspielposition.

Die Layer-A/B-Tasten sind noch im Test. Meldet sich eine davon, steht in Lives Statuszeile `Drop V2 Test: Layer-Taste (CC 40) Wert …`.

## 7. Clip-Launcher (Grid-Modus)

Die Tastenmatrix des Drop startet Clips, wenn der Drop im **Grid-Modus** ist (GRID-Taste, Modus DAW, Gerät DAW).
Das läuft unabhängig vom Layer: Auf Layer A steuerst du weiter Geräte, die Matrix startet Clips.
In Live zeigt ein roter Rahmen, welche 4 Spuren × 4 Szenen gerade auf der Matrix liegen.

| Taste | Funktion |
|---|---|
| obere 4×4 Tasten | Clip starten; die Taste zeigt Clipfarbe und ob er spielt, aufnimmt oder gleich startet |
| weiße Reihe darunter | Spur stoppen |
| blaue Tasten | Rahmen nach links, oben, unten, rechts |
| Shift + rechte Spalte | Szene starten |
| Shift + linke Spalte (rot) | Szene als Drop: startet die Szene erst, wenn die Abspielmarke des Drop oben ankommt und ein DROP passiert |
| Shift + unten rechts | alle Clips stoppen |

Shift + rechte Spalte startet die Szene sofort, also mit Lives Quantisierung. Bei „Szene als Drop“ plant der Drop den Start selbst (so steht es im Drop-Handbuch).

**Snapshots:** Ein Snapshot speichert die Stellungen der Regler und Fader am Drop, nicht Parameter in Live.
Bei den Reglern sind das die Werte, die gerade in Live stehen, weil der LED-Ring Live folgt. Bei den Fadern ist es ihre Stellung.
Beim Abrufen schickt der Drop diese Werte, und Drop V2 legt sie auf das, was in dem Moment auf den Reglern liegt: das ausgewählte Gerät (Reihe 1–3), die Sends (Reihe 4) und das Volume (Fader 1).
Die Fader auf Layer B bis E gehören immer zu festen Spuren. Ein Snapshot mit ihnen setzt also immer dieselben Spur-Volumes.
Wähle vor dem Abrufen also dasselbe Gerät und dieselbe Spur wie beim Speichern. Sonst landen die Werte auf einem anderen Gerät.

## 8. Fehlersuche

- Lives Log: `~/Library/Preferences/Ableton/Live 12.x.y/Log.txt` im Ordner der neuesten Live-Version, Einträge mit `(DropV2)`.
- **Ringe zeigen keine Werte:** Am Drop muss das Gerät „DAW“ USB1 als MIDI-Eingang haben (MENU → Devices).
- **Farben ändern sich nicht:** Am Drop einen Regler in MENU → Mapping öffnen. Der LED-Stil muss „MIDI Col Line from left“ sein, mit Slot 2 als Farb-Eingang. Der Drop zeigt dort eine Warnung, falls etwas nicht passt.
- **Nach Änderungen am Skript:** Live neu starten. Erst dann lädt Live die neue Version.
- **Ein Gerät wird nicht belegt:** Im Log steht bei jedem Gerätewechsel `Geraet <Name> (<Typ>): <Anzahl> von <Gesamt> Parametern belegt`. Fehlt die Zeile, steht darunter meist ein `RemoteScriptError`.
- **Ein Gerät braucht beim Anwählen lange:** Drop V2 schreibt ins Log, was länger als 50 ms dauert:
  - `Belegung von <Name> dauerte <Zeit> ms`: Drop V2 selbst war langsam.
  - `Anwahl von <Name> dauerte <Zeit> ms`: Live hat so lange gebraucht, das Gerät anzuwählen.
  - `Neuaufbau der MIDI-Zuordnung dauerte <Zeit> ms`: Live hat die Zuordnung der Drop-Regler neu aufgebaut.
  - `Live hat <Zeit> ms nicht reagiert`: Live war in der Zeit ganz beschäftigt und hat auch keine Tasten angenommen.
  Zum Vergleich das Gerät mit der Maus anklicken: Ist es dann genauso langsam, liegt es am Gerät (oft Max-for-Live-Geräte mit großer Oberfläche).
- **`RuntimeError` aus `MxDCore`** im Log stammt von Max-for-Live-Geräten, nicht von Drop V2.
