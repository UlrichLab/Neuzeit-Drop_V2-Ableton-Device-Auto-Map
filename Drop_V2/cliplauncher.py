# Clip-Launcher fuer den Grid-Modus des Drop, nachgebaut nach Neuzeits Skript Drop_v01,
# damit alles in einem Control-Surface-Slot laeuft.
#
#   obere Ebene   Reihe 1-4: Clips der 4x4-Box starten, Reihe 5: Spur stoppen
#   Shift-Ebene   Spalte 4: Szene starten, unten rechts: alle Clips stoppen,
#                 Spalte 1 "Szene als Drop": den Start schickt der Drop selbst zum Drop-Zeitpunkt
#   blaue Tasten  Box nach links / oben / unten / rechts
#
# update() vergleicht die LEDs mit dem zuletzt gesendeten Stand und schickt nur Aenderungen.
# Drop V2 ruft es ueber update_display() auf, also etwa zehnmal pro Sekunde.

from . import layout as L

NOTE_ON = 0x90
STOP_TRIGGERED = -2  # Track.fired_slot_index: Stopp-Taste der Spur wurde ausgeloest


def _clamp(value, maximum):
    return max(0, min(value, maximum))


def _item(items, index):
    return items[index] if 0 <= index < len(items) else None


def _shift_led(column, row):
    if row < L.GRID_SCENES and column == 0:
        return L.GRID_LED_SCENE_DROP
    if row < L.GRID_SCENES and column == L.GRID_TRACKS - 1:
        return L.GRID_LED_SCENE_LAUNCH
    if row == L.GRID_STOP_ROW and column == L.GRID_TRACKS - 1:
        return L.GRID_LED_STOP
    return L.GRID_LED_EMPTY


class ClipLauncher(object):

    def __init__(self, song, send_midi, show_box):
        self._song = song
        self._send_midi = send_midi
        self._show_box = show_box
        self._status = NOTE_ON | (L.GRID_CHANNEL - 1)
        self._sent = {}
        self.track_offset = 0
        self.scene_offset = 0
        self._show_box(self.track_offset, self.scene_offset, L.GRID_TRACKS, L.GRID_SCENES)

    def _tracks(self):
        return self._song.visible_tracks

    def _scenes(self):
        return self._song.scenes

    # --- Tasten ------------------------------------------------------------------------

    def press(self, note):
        """Eine Grid-Taste wurde gedrueckt."""
        if note == L.GRID_REQUEST_NOTE:
            self.invalidate()
        elif note == L.GRID_LEFT_NOTE:
            self._move(-1, 0)
        elif note == L.GRID_RIGHT_NOTE:
            self._move(1, 0)
        elif note == L.GRID_UP_NOTE:
            self._move(0, -1)
        elif note == L.GRID_DOWN_NOTE:
            self._move(0, 1)
        elif note == L.GRID_STOP_ALL_NOTE:
            self._song.stop_all_clips()
        elif note >= L.GRID_FIRST_NOTE:
            index = note - L.GRID_FIRST_NOTE
            shift, index = divmod(index, 20)
            row, column = divmod(index, L.GRID_TRACKS)
            if shift:
                self._press_shift(column, row)
            else:
                self._press_main(column, row)

    def _press_main(self, column, row):
        track = _item(self._tracks(), self.track_offset + column)
        if track is None:
            return
        if row == L.GRID_STOP_ROW:
            track.stop_all_clips()
            return
        slot = _item(track.clip_slots, self.scene_offset + row)
        if slot is not None:
            slot.fire()

    def _press_shift(self, column, row):
        if column == L.GRID_TRACKS - 1 and row < L.GRID_SCENES:
            scene = _item(self._scenes(), self.scene_offset + row)
            if scene is not None:
                scene.fire()

    def _move(self, tracks, scenes):
        self.track_offset += tracks
        self.scene_offset += scenes
        self._clamp_offsets(force_box=True)

    def _clamp_offsets(self, force_box=False):
        track_offset = _clamp(self.track_offset, len(self._tracks()) - L.GRID_TRACKS)
        scene_offset = _clamp(self.scene_offset, len(self._scenes()) - L.GRID_SCENES)
        changed = (track_offset, scene_offset) != (self.track_offset, self.scene_offset)
        self.track_offset, self.scene_offset = track_offset, scene_offset
        if changed or force_box:
            self._show_box(self.track_offset, self.scene_offset, L.GRID_TRACKS, L.GRID_SCENES)

    # --- LEDs --------------------------------------------------------------------------

    def invalidate(self):
        """Beim naechsten update() alle LEDs neu schicken."""
        self._sent = {}

    def update(self):
        self._clamp_offsets()
        for note, velocity in self._led_states():
            if self._sent.get(note) != velocity:
                self._sent[note] = velocity
                self._send_midi((self._status, note, velocity))

    def _led_states(self):
        tracks = self._song.visible_tracks
        states = [(L.GRID_REQUEST_NOTE, L.GRID_LED_REQUEST)]
        for column in range(L.GRID_TRACKS):
            track = _item(tracks, self.track_offset + column)
            slots = track.clip_slots if track is not None else ()
            for row in range(L.GRID_SCENES):
                slot = _item(slots, self.scene_offset + row)
                states.append((L.grid_note(column, row), self._slot_led(slot)))
            stop = L.GRID_LED_STOP
            if track is not None and track.fired_slot_index == STOP_TRIGGERED:
                stop += L.GRID_LED_TRIGGERED
            states.append((L.grid_note(column, L.GRID_STOP_ROW), stop))
        for row in range(L.GRID_STOP_ROW + 1):
            for column in range(L.GRID_TRACKS):
                states.append((L.grid_note(column, row, shift=True), _shift_led(column, row)))
        return states

    def _slot_led(self, slot):
        if slot is None or not slot.has_clip:
            return L.GRID_LED_EMPTY
        clip = slot.clip
        velocity = clip.color_index % 14 + 2
        if clip.is_triggered:
            velocity += L.GRID_LED_TRIGGERED
        if clip.is_recording:
            velocity += L.GRID_LED_RECORDING
        if clip.is_playing and self._song.is_playing:
            velocity += L.GRID_LED_PLAYING
        return velocity
