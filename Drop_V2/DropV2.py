# Drop V2 - Geraetesteuerung fuer den Neuzeit Drop auf Layer A, dazu der Clip-Launcher.
#
#   Regler Reihe 1-3 -> Parameter des ausgewaehlten Geraets (gelerntes Profil oder automatisch)
#   Regler Reihe 4   -> Send A-H der ausgewaehlten Spur
#   Regler druecken  -> kurz: Standardwert, halten + Parameter in Live anklicken: lernen,
#                       2 s halten ohne Klick: Regler freigeben
#   8 Tasten         -> < Spur, Spur >, Browser ein/aus, Session/Arrangement,
#                       Detailansicht ein/aus (1 s halten: naechste Seite, reihum),
#                       Clip-/Geraeteansicht (3 s halten: Profil Reset), < Geraet, Geraet >
#   Ring-Tasten      -> 7/2: < Spur / Spur >, 6/3: < Geraet / Geraet > (nur bei laufender Wiedergabe)
#   8 Fader          -> Fader 1: Volume der ausgewaehlten Spur, Fader 2-8 ohne Funktion
#   Layer B - E      -> Fader: Volume Spur 1-8 / 9-16 / 17-24 / 25-32, Tasten: Mute (halten: Aufnahme scharf)
#   Tastenmatrix     -> im Grid-Modus des Drop: Clip-Launcher (siehe cliplauncher.py)
#
# Ersetzt Neuzeits Skript Drop_v01; beide zugleich wuerden jede Clip-Taste doppelt ausloesen.

from __future__ import absolute_import, print_function, unicode_literals

import os
import time
from functools import partial

import Live
from _Framework.ButtonElement import ButtonElement
from _Framework.ControlSurface import ControlSurface
from _Framework.EncoderElement import EncoderElement
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.SliderElement import SliderElement
from _Framework.SubjectSlot import subject_slot, subject_slot_group

from . import layout as L
from .cliplauncher import ClipLauncher
from .parambanks import auto_layout, load_bank_definitions
from .profiles import ProfileStore, device_key, param_ref, resolve_ref

CLEAR_HOLD_SECONDS = 2.0
PAGE_HOLD_SECONDS = 1.0
SLOW_REMAP_SECONDS = 0.05  # langsamere Belegungen landen im Log
STALL_SECONDS = 0.5        # so lange ohne update_display: Live war beschaeftigt
PROFILE_RESET_HOLD_SECONDS = 3.0
CC_STATUS = 0xB0
LEARNED = "learned"
AUTO = "auto"
SEND = "send"


def _valid(obj):
    return obj is not None and obj != None


def _index_of(items, item):
    for index, candidate in enumerate(items):
        if candidate == item:
            return index
    return None


def _profile_path():
    # .../User Library/Remote Scripts/Drop_V2/DropV2.py -> .../User Library/Drop V2 Profile/
    script_folder = os.path.dirname(os.path.abspath(__file__))
    user_library = os.path.dirname(os.path.dirname(script_folder))
    return os.path.join(user_library, "Drop V2 Profile", "profiles.json")


class DropV2(ControlSurface):

    def __init__(self, c_instance):
        super(DropV2, self).__init__(c_instance)
        self._bank_definitions, self._bank_parameters_key = load_bank_definitions(self.log_message)
        self._profiles = ProfileStore(_profile_path(), self.log_message)
        self._device = None
        self._page = 0
        self._page_count = 1
        self._page_entries = [None] * len(L.KNOB_CCS)
        self._held_knob = None
        self._held_since = 0.0
        self._learned_while_held = False
        self._profile_reset_since = None
        self._detail_page_since = None
        self._last_display = None
        self._track_button_since = {}
        with self.component_guard():
            self._create_controls()
            self._clip_launcher = ClipLauncher(self.song(), self._send_midi, self._show_session_box)
            self._on_selected_track.subject = self.song().view
            self._on_selected_parameter.subject = self.song().view
            self._on_tracks_changed.subject = self.song()
            self._update_track()
            self._map_track_layers()
        self.schedule_message(2, self._send_full_state)
        self.log_message("Drop V2 geladen. Profile:", self._profiles.path)
        self.show_message("Drop V2 bereit")

    # --- Controls ------------------------------------------------------------------------

    def _create_controls(self):
        knob_channel = L.KNOB_CHANNEL - 1
        push_channel = L.PUSH_CHANNEL - 1
        remote_channel = L.REMOTE_CHANNEL - 1
        self._knobs = [EncoderElement(MIDI_CC_TYPE, knob_channel, cc, Live.MidiMap.MapMode.absolute)
                       for cc in L.KNOB_CCS]
        self._pushes = [ButtonElement(True, MIDI_NOTE_TYPE, push_channel, note) for note in L.KNOB_PUSH_NOTES]
        self._buttons = [ButtonElement(True, MIDI_NOTE_TYPE, push_channel, note) for note in L.BUTTON_NOTES]
        self._faders = [SliderElement(MIDI_CC_TYPE, L.FADER_CHANNEL - 1, cc) for cc in L.FADER_CCS]
        # Layer B-E, Index = Spur 0-31
        self._track_faders = [SliderElement(MIDI_CC_TYPE, layer["fader_channel"] - 1, cc)
                              for layer in L.TRACK_LAYERS for cc in layer["fader_ccs"]]
        self._track_buttons = [ButtonElement(True, MIDI_NOTE_TYPE, layer["button_channel"] - 1, note)
                               for layer in L.TRACK_LAYERS for note in layer["button_notes"]]
        # Ring-Tasten (CC 39) und Layer-Tasten (CC 40) ueber "Remote Send"
        self._remote_inputs = [ButtonElement(False, MIDI_CC_TYPE, remote_channel, cc)
                               for cc in (L.REMOTE_CC_BEATJUMP, L.REMOTE_CC_LAYER)]
        # Alle Grid-Noten abnehmen, damit keine davon in einer MIDI-Spur landet.
        self._grid_buttons = [ButtonElement(True, MIDI_NOTE_TYPE, L.GRID_CHANNEL - 1, note)
                              for note in range(L.GRID_REQUEST_NOTE, L.GRID_LAST_NOTE + 1)]
        self._on_knob_push.replace_subjects(self._pushes)
        self._on_button.replace_subjects(self._buttons)
        self._on_remote_input.replace_subjects(self._remote_inputs)
        self._on_grid_button.replace_subjects(self._grid_buttons)
        self._on_track_button.replace_subjects(self._track_buttons)
        # Fader 2-8 abnehmen, damit ihre CCs nicht in einer MIDI-Spur landen.
        self._on_unused_fader.replace_subjects(self._faders[1:])

    def _send_cc(self, channel, cc, value):
        self._send_midi((CC_STATUS | (channel - 1), cc, value))

    def _show_session_box(self, track_offset, scene_offset, width, height):
        self._c_instance.set_session_highlight(track_offset, scene_offset, width, height, False)

    def disconnect(self):
        self._show_session_box(-1, -1, -1, -1)
        super(DropV2, self).disconnect()

    def refresh_state(self):
        super(DropV2, self).refresh_state()
        self._send_full_state()

    def build_midi_map(self, midi_map_handle):
        # Live baut die Zuordnung nach jedem Geraetewechsel ganz neu auf.
        started = time.time()
        super(DropV2, self).build_midi_map(midi_map_handle)
        self._log_if_slow("Neuaufbau der MIDI-Zuordnung", started)

    def update_display(self):
        super(DropV2, self).update_display()
        # Live ruft das etwa alle 100 ms auf. Eine lange Pause heisst: Live war beschaeftigt.
        now = time.time()
        if self._last_display is not None and now - self._last_display > STALL_SECONDS:
            device = self._device.name if self._device is not None else "-"
            self.log_message("Live hat %d ms nicht reagiert (Geraet: %s)" % ((now - self._last_display) * 1000, device))
        self._last_display = now
        self._clip_launcher.update()

    def _send_full_state(self):
        with self.component_guard():
            self._send_cc(L.REMOTE_CHANNEL, L.REMOTE_CC_LAYER, 1)  # Drop auf Layer A
            for index, entry in enumerate(self._page_entries):
                if entry is None:
                    self._send_cc(L.KNOB_CHANNEL, L.KNOB_CCS[index], 0)
            self._send_colors()
            self._update_button_leds()
            self._update_track_leds()
            self._clip_launcher.invalidate()
            self._clip_launcher.update()

    # --- Auswahl verfolgen ---------------------------------------------------------------

    @subject_slot("selected_track")
    def _on_selected_track(self):
        with self.component_guard():
            self._update_track()

    @subject_slot("selected_device")
    def _on_selected_device(self):
        track = self.song().view.selected_track
        if self._device is not None and _valid(track) and track.view.selected_device == self._device:
            return  # dasselbe Geraet noch einmal gewaehlt: Belegung steht schon
        with self.component_guard():
            self._update_device()

    @subject_slot("devices")
    def _on_devices_changed(self):
        with self.component_guard():
            self._update_device()

    @subject_slot("parameters")
    def _on_parameters_changed(self):
        with self.component_guard():
            self._remap()

    @subject_slot("name")
    def _on_device_name_changed(self):
        with self.component_guard():
            self._remap()

    @subject_slot("visible_macro_count")
    def _on_macro_count_changed(self):
        with self.component_guard():
            self._remap()

    @subject_slot("sends")
    def _on_sends_changed(self):
        with self.component_guard():
            self._remap()

    def _update_track(self):
        track = self.song().view.selected_track
        valid = _valid(track)
        self._on_selected_device.subject = track.view if valid else None
        self._on_devices_changed.subject = track if valid else None
        self._on_sends_changed.subject = track.mixer_device if valid else None
        self._map_faders(track if valid else None)
        self._update_device()

    def _update_device(self):
        track = self.song().view.selected_track
        device = track.view.selected_device if _valid(track) else None
        if not _valid(device):
            device = None
            if _valid(track) and len(track.devices):
                device = track.devices[0]  # Spur ohne Auswahl: erstes Geraet
        changed = device != self._device
        if changed:
            self._page = 0
        self._device = device
        self._on_parameters_changed.subject = device
        self._on_device_name_changed.subject = device
        is_rack = device is not None and hasattr(device, "visible_macro_count")
        self._on_macro_count_changed.subject = device if is_rack else None
        self._remap()
        if changed and device is not None:
            self.log_message("Geraet %s (%s): %d von %d Parametern belegt"
                             % (device.name, device.class_name, self._mapped_count, len(device.parameters)))

    def _map_faders(self, track):
        if track is None:
            self._faders[0].release_parameter()
        else:
            self._faders[0].connect_to(track.mixer_device.volume)

    @subject_slot_group("value")
    def _on_unused_fader(self, value, sender):
        pass

    # --- Belegung ------------------------------------------------------------------------

    def _auto_entries(self, device):
        layout = auto_layout(device, self._bank_definitions, self._bank_parameters_key)
        return [(parameter, AUTO) if parameter is not None else None for parameter in layout]

    def _layout_entries(self, device):
        """Liste von (Parameter, Herkunft) oder None, ein Eintrag pro Regler-Slot ueber alle Seiten."""
        if device is None:
            return []
        slots = self._profiles.slots(device_key(device))
        if slots is None:
            return self._auto_entries(device)
        parameters = list(device.parameters)
        entries = [None] * ((max(slots) + 1) if slots else 0)
        for slot, ref in slots.items():
            parameter = resolve_ref(parameters, ref)
            if parameter is not None:
                entries[slot] = (parameter, LEARNED if ref.get("learned") else AUTO)
        return entries

    def _auto_refs(self, device):
        parameters = list(device.parameters)
        return [param_ref(parameters, entry[0]) if entry else None for entry in self._auto_entries(device)]

    def _send_entries(self):
        track = self.song().view.selected_track
        sends = list(track.mixer_device.sends)[:L.SEND_KNOBS] if _valid(track) else []
        return [(send, SEND) for send in sends] + [None] * (L.SEND_KNOBS - len(sends))

    def _remap(self):
        started = time.time()
        entries = self._layout_entries(self._device)
        self._mapped_count = sum(1 for entry in entries if entry)
        size = L.DEVICE_KNOBS
        self._page_count = max(1, (len(entries) + size - 1) // size)
        self._page = max(0, min(self._page, self._page_count - 1))
        page = list(entries[self._page * size:(self._page + 1) * size])
        page += [None] * (size - len(page))
        self._page_entries = page + self._send_entries()
        for index, knob in enumerate(self._knobs):
            entry = self._page_entries[index]
            if entry is None:
                knob.release_parameter()
                self._send_cc(L.KNOB_CHANNEL, L.KNOB_CCS[index], 0)
            else:
                knob.connect_to(entry[0])
        self._send_colors()
        self._update_button_leds()
        self._show_device_message()
        if self._device is not None:
            self._log_if_slow("Belegung von %s" % self._device.name, started)

    def _log_if_slow(self, what, started):
        elapsed = time.time() - started
        if elapsed > SLOW_REMAP_SECONDS:
            self.log_message("%s dauerte %d ms" % (what, elapsed * 1000))

    def _send_colors(self):
        for index, entry in enumerate(self._page_entries):
            if entry is None:
                hue = L.HUE_EMPTY
            elif entry[1] == LEARNED:
                hue = L.HUE_LEARNED
            elif entry[1] == SEND:
                hue = L.HUE_SEND
            else:
                hue = L.HUE_AUTO
            self._send_cc(L.KNOB_COLOR_CHANNEL, L.KNOB_CCS[index], hue)

    def _show_device_message(self):
        if self._device is None:
            self.show_message("Drop V2: kein Geraet ausgewaehlt")
            return
        source = "gelernt" if self._profiles.has(device_key(self._device)) else "automatisch"
        self.show_message("Drop V2: %s - Seite %d/%d (%s)" % (self._device.name, self._page + 1, self._page_count, source))

    # --- Tasten --------------------------------------------------------------------------

    def _all_tracks(self):
        song = self.song()
        return list(song.visible_tracks) + list(song.return_tracks) + [song.master_track]

    def _top_level_index(self, devices, device):
        """Position des Geraets (oder des Racks, in dem es steckt) in der Spur."""
        node = device
        for _ in range(32):
            if not _valid(node):
                return None
            index = _index_of(devices, node)
            if index is not None:
                return index
            node = getattr(node, "canonical_parent", None)
        return None

    def _update_button_leds(self):
        track = self.song().view.selected_track
        devices = list(track.devices) if _valid(track) else []
        position = self._top_level_index(devices, self._device)
        tracks = self._all_tracks()
        track_index = _index_of(tracks, track)
        states = {
            L.BTN_PREV_DEVICE: position is not None and position > 0,
            L.BTN_NEXT_DEVICE: len(devices) > 0 and (position is None or position < len(devices) - 1),
            L.BTN_PREV_TRACK: track_index is not None and track_index > 0,
            L.BTN_NEXT_TRACK: track_index is not None and track_index < len(tracks) - 1,
            L.BTN_BROWSER: True,
            L.BTN_MAIN_VIEW: True,
            L.BTN_DETAIL_PAGE: True,
            L.BTN_PROFILE_RESET: self._device is not None and self._profiles.has(device_key(self._device)),
        }
        for index, button in enumerate(self._buttons):
            button.send_value(127 if states[index] else 0, force=True)

    @subject_slot_group("value")
    def _on_button(self, value, sender):
        index = _index_of(self._buttons, sender)
        if index == L.BTN_PROFILE_RESET:
            self._handle_view_or_reset(bool(value))
            return
        if index == L.BTN_DETAIL_PAGE:
            self._handle_detail_or_page(bool(value))
            return
        if value:
            if index == L.BTN_PREV_DEVICE:
                self._step_device(-1)
            elif index == L.BTN_NEXT_DEVICE:
                self._step_device(1)
            elif index == L.BTN_PREV_TRACK:
                self._step_track(-1)
            elif index == L.BTN_NEXT_TRACK:
                self._step_track(1)
            elif index == L.BTN_MAIN_VIEW:
                self._toggle_main_view()
            elif index == L.BTN_BROWSER:
                self._toggle_view("Browser")
        # Die Taste ist "Temporary": der Drop schaltet ihre LED beim Loslassen selbst aus.
        self._update_button_leds()

    def _step_device(self, delta):
        track = self.song().view.selected_track
        devices = list(track.devices) if _valid(track) else []
        if not devices:
            return
        current = track.view.selected_device
        if not _valid(current):
            current = self._device
        position = self._top_level_index(devices, current)
        target = 0 if position is None else max(0, min(len(devices) - 1, position + delta))
        # Am Ende der Kette nicht dasselbe Geraet neu waehlen: Live wuerde alles neu melden
        # und waere bei Max-Geraeten eine Weile beschaeftigt.
        if devices[target] != current:
            started = time.time()
            self.song().view.select_device(devices[target])
            self._log_if_slow("Anwahl von %s" % devices[target].name, started)

    def _step_track(self, delta):
        tracks = self._all_tracks()
        position = _index_of(tracks, self.song().view.selected_track)
        target = 0 if position is None else max(0, min(len(tracks) - 1, position + delta))
        self.song().view.selected_track = tracks[target]

    def _next_page(self):
        if self._page_count > 1:
            self._page = (self._page + 1) % self._page_count
            self._remap()

    def _handle_detail_or_page(self, pressed):
        """Kurz druecken: Detailansicht ein/aus. 1 s halten: naechste Seite."""
        if pressed:
            self._detail_page_since = time.time()
            return
        since, self._detail_page_since = self._detail_page_since, None
        if since is not None:
            if time.time() - since < PAGE_HOLD_SECONDS:
                self._toggle_detail()
            else:
                self._next_page()
        self._update_button_leds()

    def _toggle_detail(self):
        self._toggle_view("Detail")

    def _toggle_view(self, name):
        view = self.application().view
        if view.is_view_visible(name):
            view.hide_view(name)
        else:
            view.show_view(name)

    def _toggle_main_view(self):
        view = self.application().view
        if view.is_view_visible("Session"):
            view.show_view("Arranger")
        else:
            view.show_view("Session")

    def _handle_view_or_reset(self, pressed):
        """Kurz druecken: Clip- / Geraeteansicht wechseln. 3 s halten: Profil Reset."""
        if pressed:
            self._profile_reset_since = time.time()
            return
        since, self._profile_reset_since = self._profile_reset_since, None
        if since is None:
            return
        if time.time() - since < PROFILE_RESET_HOLD_SECONDS:
            self._toggle_detail_view()
        elif self._device is not None and self._profiles.delete(device_key(self._device)):
            self.show_message("Drop V2: Profil von %s geloescht, wieder automatisch" % self._device.name)
            self._remap()
        self._update_button_leds()

    def _toggle_detail_view(self):
        view = self.application().view
        if view.is_view_visible("Detail/DeviceChain"):
            view.show_view("Detail/Clip")
        else:
            view.show_view("Detail/DeviceChain")

    # --- Regler druecken: Standardwert, Lernen, Freigeben --------------------------------

    @subject_slot_group("value")
    def _on_knob_push(self, value, sender):
        index = _index_of(self._pushes, sender)
        if value:
            self._held_knob = index
            self._held_since = time.time()
            self._learned_while_held = False
            return
        if self._held_knob != index:
            return
        held_for = time.time() - self._held_since
        self._held_knob = None
        if self._learned_while_held:
            return
        if held_for >= CLEAR_HOLD_SECONDS:
            self._clear_knob(index)
        else:
            self._reset_knob(index)

    def _reset_knob(self, index):
        entry = self._page_entries[index]
        if entry is None:
            return
        parameter = entry[0]
        if not parameter.is_enabled:
            return
        if parameter.is_quantized:
            self.show_message("Drop V2: %s hat keinen Standardwert" % parameter.name)
            return
        parameter.value = parameter.default_value
        self.show_message("Drop V2: %s auf Standardwert" % parameter.name)

    def _clear_knob(self, index):
        device = self._device
        if device is None or index >= L.DEVICE_KNOBS:
            return
        slot = self._page * L.DEVICE_KNOBS + index
        self._profiles.clear(device_key(device), device.name, self._auto_refs(device), slot)
        self.show_message("Drop V2: Regler %d bei %s freigegeben" % (index + 1, device.name))
        self._remap()

    @subject_slot("selected_parameter")
    def _on_selected_parameter(self):
        knob = self._held_knob
        if knob is None:
            return
        parameter = self.song().view.selected_parameter
        if not _valid(parameter):
            return
        owner = parameter.canonical_parent
        if not isinstance(owner, Live.Device.Device):
            self.show_message("Drop V2: nur Geraete-Parameter lassen sich lernen")
            return
        with self.component_guard():
            self._learn(owner, parameter, knob)

    def _learn(self, device, parameter, knob):
        self._learned_while_held = True
        if knob >= L.DEVICE_KNOBS:
            self.show_message("Drop V2: Reihe 4 gehoert den Sends, dort wird nichts gelernt")
            return
        page = self._page if device == self._device else 0
        slot = page * L.DEVICE_KNOBS + knob
        ref = param_ref(list(device.parameters), parameter)
        self._profiles.assign(device_key(device), device.name, self._auto_refs(device), slot, ref)
        self.show_message("Drop V2: %s auf Regler %d gelernt (%s)" % (parameter.name, knob + 1, device.name))
        if device == self._device:
            self._remap()
        else:
            self.schedule_message(1, partial(self._select_device, device))

    def _select_device(self, device):
        if _valid(device):
            self.song().view.select_device(device)

    # --- Ring- und Layer-Tasten ----------------------------------------------------------

    @subject_slot_group("value")
    def _on_remote_input(self, value, sender):
        if sender is self._remote_inputs[0]:
            # Die uebrigen Ring-Tasten machen am Drop nur ihren Beatjump.
            if value == L.RING_NEXT_TRACK:
                self._step_track(1)
            elif value == L.RING_PREV_TRACK:
                self._step_track(-1)
            elif value == L.RING_NEXT_DEVICE:
                self._step_device(1)
            elif value == L.RING_PREV_DEVICE:
                self._step_device(-1)
            return
        # Layer-Tasten sind noch im Test: nur anzeigen, was ankommt.
        self.log_message("Remote vom Drop: Layer-Taste (CC 40) Wert", value)
        self.show_message("Drop V2 Test: Layer-Taste (CC 40) Wert %d" % value)

    # --- Clip-Launcher -------------------------------------------------------------------

    @subject_slot_group("value")
    def _on_grid_button(self, value, sender):
        if value:
            self._clip_launcher.press(L.GRID_REQUEST_NOTE + _index_of(self._grid_buttons, sender))
            self._clip_launcher.update()

    # --- Layer B-E: feste Spuren ---------------------------------------------------------

    @subject_slot("tracks")
    def _on_tracks_changed(self):
        with self.component_guard():
            self._map_track_layers()

    @subject_slot_group("mute")
    def _on_track_mute(self, sender):
        self._update_track_leds()

    def _layer_tracks(self):
        """Spur 1-32 in Lives Reihenfolge (wie die Nummern im Spurkopf), fehlende als None."""
        count = len(self._track_faders)
        tracks = list(self.song().tracks)[:count]
        return tracks + [None] * (count - len(tracks))

    def _map_track_layers(self):
        tracks = self._layer_tracks()
        for fader, track in zip(self._track_faders, tracks):
            if track is None:
                fader.release_parameter()
            else:
                fader.connect_to(track.mixer_device.volume)
        self._on_track_mute.replace_subjects([track for track in tracks if track is not None])
        self._update_track_leds()

    def _update_track_leds(self):
        # Leuchtet wie Lives Spur-Aktivator: an = Spur spielt, aus = stumm
        for button, track in zip(self._track_buttons, self._layer_tracks()):
            button.send_value(127 if track is not None and not track.mute else 0, force=True)

    @subject_slot_group("value")
    def _on_track_button(self, value, sender):
        """Kurz druecken: Mute an/aus. Halten: Aufnahme scharf an/aus."""
        index = _index_of(self._track_buttons, sender)
        if value:
            self._track_button_since[index] = time.time()
        else:
            since = self._track_button_since.pop(index, None)
            track = self._layer_tracks()[index]
            if since is not None and track is not None:
                if time.time() - since >= L.TRACK_ARM_HOLD_SECONDS:
                    self._toggle_arm(track, index)
                else:
                    track.mute = not track.mute
        # Die Taste ist "Temporary": der Drop schaltet ihre LED beim Loslassen selbst aus.
        self._update_track_leds()

    def _toggle_arm(self, track, index):
        if not track.can_be_armed:
            self.show_message("Drop V2: Spur %d (%s) kann nicht aufnehmen" % (index + 1, track.name))
            return
        track.arm = not track.arm
        state = "scharf" if track.arm else "aus"
        self.show_message("Drop V2: Spur %d (%s) Aufnahme %s" % (index + 1, track.name, state))
