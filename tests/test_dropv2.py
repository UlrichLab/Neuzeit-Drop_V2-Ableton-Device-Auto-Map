"""Ablauftests fuer Drop V2 mit Live-Attrappen.  Aufruf: python3 -I tests/test_dropv2.py"""

import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import fakes  # noqa: E402

fakes.install()

from Drop_V2 import layout as L  # noqa: E402
from Drop_V2.DropV2 import DropV2  # noqa: E402

# Das Paket bindet "DropV2" an die Klasse, das Modul gibt es nur ueber sys.modules.
dropv2_module = sys.modules["Drop_V2.DropV2"]

RACK = "AudioEffectGroupDevice"
MACROS = ["Macro %d" % n for n in range(1, 17)] + ["Chain Selector"]
FILTER_PARAMS = ["Frequency", "Resonance", "Filter Type", "Drive", "Dry/Wet", "LFO Amount", "LFO Rate"]
NOTE_ON = 0x90 | (L.PUSH_CHANNEL - 1)
SENDS1 = ["Send A", "Send B", "Send C"] + [None] * 5  # Reihe 4 auf Spur "Bass"


class FakeCInstance(object):
    def __init__(self, song):
        self._song = song
        self.session_box = None

    def song(self):
        return self._song

    def set_session_highlight(self, track_offset, scene_offset, width, height, include_returns):
        self.session_box = (track_offset, scene_offset, width, height)


class Clock(object):
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now


class DropV2Test(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.profile_path = os.path.join(self.tmp, "Drop V2 Profile", "profiles.json")
        dropv2_module._profile_path = lambda: self.profile_path
        self.clock = Clock()
        dropv2_module.time = self.clock
        fakes.SENT[:] = []

        self.track1 = fakes.Track("Bass", send_count=3)
        self.rack = self.track1.add_device(fakes.Device(RACK, "Bass FX", MACROS, macro_count=16))
        self.filter1 = self.track1.add_device(fakes.Device("AutoFilter2", "Auto Filter", FILTER_PARAMS))
        self.plugin = self.track1.add_device(fakes.Device("PluginDevice", "Big Synth", ["P%d" % i for i in range(40)]))
        self.track2 = fakes.Track("Lead")
        self.filter2 = self.track2.add_device(fakes.Device("AutoFilter2", "Mein Filter", FILTER_PARAMS))
        self.song = fakes.Song([self.track1, self.track2], returns=1)
        self.track1.view.selected_device = self.rack
        self.c_instance = FakeCInstance(self.song)
        self.surface = DropV2(self.c_instance)
        self.surface.run_scheduled()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # Hilfen ------------------------------------------------------------------------------

    def mapped(self):
        return [knob.mapped.original_name if knob.mapped else None for knob in self.surface._knobs]

    def colors(self):
        status = 0xB0 | (L.KNOB_COLOR_CHANNEL - 1)
        latest = {}
        for message in fakes.SENT:
            if message[0] == status:
                latest[message[1]] = message[2]
        return [latest.get(cc) for cc in L.KNOB_CCS]

    def button_led(self, index):
        note = L.BUTTON_NOTES[index]
        values = [m[2] for m in fakes.SENT if m[0] == NOTE_ON and m[1] == note]
        return values[-1] if values else None

    def press(self, element, hold=0.1):
        element.receive_value(127)
        self.clock.now += hold
        element.receive_value(0)
        self.surface.run_scheduled()

    # Tests -------------------------------------------------------------------------------

    def test_rack_maps_16_macros_on_two_rows(self):
        self.assertEqual(self.mapped()[:16], MACROS[:16])
        self.assertEqual(self.mapped()[16:24], [None] * 8)
        self.assertEqual(self.mapped()[24:], SENDS1)
        self.assertEqual(self.colors(), [L.HUE_AUTO] * 16 + [L.HUE_EMPTY] * 8 + [L.HUE_SEND] * 3 + [L.HUE_EMPTY] * 5)

    def test_rack_with_8_visible_macros_uses_row_one(self):
        self.rack.visible_macro_count = 8
        self.rack.notify("visible_macro_count")
        self.assertEqual(self.mapped()[:8], MACROS[:8])
        self.assertEqual(self.mapped()[8:24], [None] * 16)

    def test_startup_selects_layer_a(self):
        self.assertIn((0xB0 | (L.REMOTE_CHANNEL - 1), L.REMOTE_CC_LAYER, 1), fakes.SENT)

    def test_next_device_uses_ableton_banks(self):
        self.press(self.surface._buttons[L.BTN_NEXT_DEVICE])
        self.assertIs(self.surface._device, self.filter1)
        row1 = ["Frequency", "Resonance", "Filter Type", None, "Drive", None, None, "Dry/Wet"]
        row2 = ["LFO Amount", "LFO Rate"] + [None] * 6
        self.assertEqual(self.mapped(), row1 + row2 + [None] * 8 + SENDS1)

    def test_device_buttons_light_when_possible(self):
        self.assertEqual(self.button_led(L.BTN_PREV_DEVICE), 0)
        self.assertEqual(self.button_led(L.BTN_NEXT_DEVICE), 127)
        self.assertEqual(self.button_led(L.BTN_BROWSER), 127)

    def test_plugin_pages(self):
        self.song.view.select_device(self.plugin)
        self.assertEqual(self.mapped(), ["P%d" % i for i in range(24)] + SENDS1)
        button = self.surface._buttons[L.BTN_DETAIL_PAGE]
        self.press(button, hold=1.0)  # halten: naechste Seite
        self.assertEqual(self.mapped(), ["P%d" % i for i in range(24, 40)] + [None] * 8 + SENDS1)
        self.press(button, hold=1.0)  # nach der letzten Seite wieder Seite 1
        self.assertEqual(self.mapped(), ["P%d" % i for i in range(24)] + SENDS1)
        self.assertTrue(self.surface.application().view.detail)  # Halten blendet nichts aus

    def test_button_5_short_press_toggles_detail_view(self):
        view = self.surface.application().view
        button = self.surface._buttons[L.BTN_DETAIL_PAGE]
        self.assertEqual(self.button_led(L.BTN_DETAIL_PAGE), 127)
        self.press(button)
        self.assertFalse(view.detail)
        self.press(button)
        self.assertTrue(view.detail)
        self.assertEqual(self.mapped()[:16], MACROS[:16])  # Seite bleibt

    def test_learn_saves_profile_and_applies_on_other_track(self):
        self.song.view.select_device(self.filter1)
        push = self.surface._pushes[0]
        push.receive_value(127)
        self.song.view.click_parameter(self.filter1.parameters[5])  # "Dry/Wet"
        push.receive_value(0)
        self.surface.run_scheduled()

        self.assertEqual(self.mapped()[0], "Dry/Wet")
        self.assertIsNone(self.mapped()[7], "Dry/Wet wandert von Regler 8 auf Regler 1")
        self.assertEqual(self.mapped()[1], "Resonance")
        self.assertEqual(self.colors()[0], L.HUE_LEARNED)
        self.assertEqual(self.colors()[1], L.HUE_AUTO)
        self.assertEqual(self.filter1.parameters[5].value, 0.5, "kein Reset nach dem Lernen")

        with open(self.profile_path) as handle:
            saved = json.load(handle)
        self.assertIn("AutoFilter2", saved["profiles"])

        self.song.view.selected_track = self.track2
        self.assertIs(self.surface._device, self.filter2)
        self.assertEqual(self.mapped()[0], "Dry/Wet", "gleicher Geraetetyp auf neuer Spur")

    def test_profile_survives_restart(self):
        self.song.view.select_device(self.filter1)
        push = self.surface._pushes[2]
        push.receive_value(127)
        self.song.view.click_parameter(self.filter1.parameters[2])  # "Resonance"
        push.receive_value(0)
        restarted = DropV2(FakeCInstance(self.song))
        self.assertEqual(restarted._knobs[2].mapped.original_name, "Resonance")

    def test_learn_parameter_of_other_device_selects_it(self):
        push = self.surface._pushes[4]
        push.receive_value(127)
        self.song.view.click_parameter(self.filter1.parameters[1])  # Frequency
        push.receive_value(0)
        self.surface.run_scheduled()
        self.assertIs(self.surface._device, self.filter1)
        self.assertEqual(self.mapped()[4], "Frequency")

    def test_mixer_parameter_is_not_learned(self):
        push = self.surface._pushes[0]
        push.receive_value(127)
        self.song.view.click_parameter(self.track1.mixer_device.volume)
        push.receive_value(0)
        self.assertIn("nur Geraete-Parameter", self.surface.messages[-2])
        self.assertFalse(os.path.exists(self.profile_path))

    def test_short_push_resets_to_default(self):
        macro = self.rack.parameters[3]
        macro.value = 0.9
        self.press(self.surface._pushes[2])
        self.assertEqual(macro.value, macro.default_value)

    def test_long_push_clears_knob(self):
        self.press(self.surface._pushes[0], hold=2.5)
        self.assertIsNone(self.mapped()[0])
        self.assertEqual(self.mapped()[1], "Macro 2")
        self.assertEqual(self.colors()[0], L.HUE_EMPTY)

    def test_profile_reset_needs_long_press(self):
        self.press(self.surface._pushes[0], hold=2.5)
        self.assertEqual(self.button_led(L.BTN_PROFILE_RESET), 127)
        self.press(self.surface._buttons[L.BTN_PROFILE_RESET], hold=0.2)
        self.assertIsNone(self.mapped()[0], "kurz druecken loescht nicht")
        self.press(self.surface._buttons[L.BTN_PROFILE_RESET], hold=2.5)
        self.assertIsNone(self.mapped()[0], "2,5 s reichen nicht")
        self.press(self.surface._buttons[L.BTN_PROFILE_RESET], hold=3.1)
        self.assertEqual(self.mapped()[0], "Macro 1")
        self.assertEqual(self.button_led(L.BTN_PROFILE_RESET), 0)

    def test_short_press_on_button_6_toggles_clip_and_device_view(self):
        view = self.surface.application().view
        self.press(self.surface._buttons[L.BTN_PROFILE_RESET])
        self.assertEqual(view.visible, "Detail/DeviceChain")
        self.press(self.surface._buttons[L.BTN_PROFILE_RESET])
        self.assertEqual(view.visible, "Detail/Clip")

    def test_next_device_at_end_of_chain_does_nothing(self):
        self.song.view.select_device(self.plugin)  # letztes Geraet der Spur
        calls = []
        original = self.song.view.select_device
        self.song.view.select_device = lambda device: calls.append(device) or original(device)
        self.press(self.surface._buttons[L.BTN_NEXT_DEVICE])
        self.press(self.surface._buttons[L.BTN_NEXT_DEVICE])
        self.assertEqual(calls, [])
        self.press(self.surface._buttons[L.BTN_PREV_DEVICE])  # ein Druck reicht zurueck
        self.assertIs(self.surface._device, self.filter1)

    def test_slow_midi_map_rebuild_is_logged(self):
        original = fakes.ControlSurface.build_midi_map
        fakes.ControlSurface.build_midi_map = lambda surface, handle: setattr(self.clock, "now", self.clock.now + 0.2)
        try:
            self.surface.build_midi_map(None)
        finally:
            fakes.ControlSurface.build_midi_map = original
        self.assertIn("Neuaufbau der MIDI-Zuordnung dauerte 200 ms", self.surface.logs[-1])

    def test_same_device_reported_again_is_not_remapped(self):
        before = len(self.surface.messages)
        self.track1.view.notify("selected_device")  # Live meldet dieselbe Auswahl noch einmal
        self.assertEqual(len(self.surface.messages), before)
        self.assertEqual(self.mapped()[:16], MACROS[:16])

    def test_button_4_toggles_session_and_arrangement(self):
        view = self.surface.application().view
        self.assertEqual(self.button_led(L.BTN_MAIN_VIEW), 127)
        self.press(self.surface._buttons[L.BTN_MAIN_VIEW])
        self.assertEqual(view.main, "Arranger")
        self.press(self.surface._buttons[L.BTN_MAIN_VIEW])
        self.assertEqual(view.main, "Session")

    def test_sends_on_row_four_follow_track(self):
        self.song.view.selected_track = self.track2
        self.assertEqual(self.mapped()[24:], ["Send A", "Send B"] + [None] * 6)
        self.assertEqual(self.colors()[24:], [L.HUE_SEND] * 2 + [L.HUE_EMPTY] * 6)
        mixer = self.track2.mixer_device
        mixer.sends += (fakes.Parameter("Send C", mixer),)
        mixer.notify("sends")
        self.assertEqual(self.mapped()[26], "Send C")
        self.assertIsNone(self.surface._faders[3].mapped)  # Fader 2-8 haben keine Funktion

    def test_row_four_is_not_learned(self):
        push = self.surface._pushes[24]
        push.receive_value(127)
        self.song.view.click_parameter(self.rack.parameters[1])
        push.receive_value(0)
        self.assertEqual(self.mapped()[24], "Send A")
        self.assertFalse(os.path.exists(self.profile_path))

    # Clip-Launcher -----------------------------------------------------------------------

    def grid_leds(self):
        status = 0x90 | (L.GRID_CHANNEL - 1)
        latest = {}
        for message in fakes.SENT:
            if message[0] == status:
                latest[message[1]] = message[2]
        return latest

    def grid_press(self, note):
        button = self.surface._grid_buttons[note - L.GRID_REQUEST_NOTE]
        button.receive_value(127)
        button.receive_value(0)

    def test_clip_launcher_leds(self):
        self.track2.clip_slots[1].clip = fakes.Clip(color_index=17, playing=True)
        self.song.is_playing = True
        self.surface.update_display()
        leds = self.grid_leds()
        self.assertEqual(leds[L.grid_note(1, 1)], 17 % 14 + 2 + L.GRID_LED_PLAYING)
        self.assertEqual(leds[L.grid_note(0, 0)], L.GRID_LED_EMPTY)
        self.assertEqual(leds[L.grid_note(2, 0)], L.GRID_LED_EMPTY, "keine dritte Spur")
        self.assertEqual(leds[L.grid_note(0, L.GRID_STOP_ROW)], L.GRID_LED_STOP)
        self.assertEqual(leds[L.grid_note(0, 0, shift=True)], L.GRID_LED_SCENE_DROP)
        self.assertEqual(leds[L.grid_note(3, 0, shift=True)], L.GRID_LED_SCENE_LAUNCH)
        self.assertEqual(leds[L.GRID_STOP_ALL_NOTE], L.GRID_LED_STOP)
        self.assertEqual(self.c_instance.session_box, (0, 0, 4, 4))

    def test_clip_launcher_sends_only_changes_until_drop_asks(self):
        self.surface.update_display()
        fakes.SENT[:] = []
        self.surface.update_display()
        self.assertEqual(self.grid_leds(), {})
        self.grid_press(L.GRID_REQUEST_NOTE)
        self.assertEqual(len(self.grid_leds()), 1 + 40)

    def test_clip_launcher_buttons(self):
        self.grid_press(L.grid_note(1, 2))
        self.assertEqual(self.track2.clip_slots[2].fired, 1)
        self.grid_press(L.grid_note(0, L.GRID_STOP_ROW))
        self.assertEqual(self.track1.stopped, 1)
        self.grid_press(L.grid_note(3, 1, shift=True))
        self.assertEqual(self.song.scenes[1].fired, 1)
        self.grid_press(L.grid_note(0, 1, shift=True))  # Szene als Drop: den Start schickt der Drop
        self.assertEqual(self.song.scenes[1].fired, 1)
        self.grid_press(L.GRID_STOP_ALL_NOTE)
        self.assertEqual(self.song.all_stopped, 1)

    def test_clip_box_moves_within_the_set(self):
        for track in self.song.visible_tracks:
            track.clip_slots += [fakes.ClipSlot(), fakes.ClipSlot()]
        self.song.scenes += [fakes.Scene(), fakes.Scene()]
        for _ in range(3):
            self.grid_press(L.GRID_DOWN_NOTE)
        self.assertEqual(self.c_instance.session_box, (0, 2, 4, 4))
        self.grid_press(L.GRID_RIGHT_NOTE)
        self.assertEqual(self.c_instance.session_box, (0, 2, 4, 4), "nur 2 Spuren")
        self.grid_press(L.grid_note(0, 0))
        self.assertEqual(self.track1.clip_slots[2].fired, 1)
        self.surface.disconnect()
        self.assertEqual(self.c_instance.session_box, (-1, -1, -1, -1))

    def test_button_3_toggles_browser(self):
        view = self.surface.application().view
        self.press(self.surface._buttons[L.BTN_BROWSER])
        self.assertFalse(view.browser)
        self.assertEqual(self.rack.parameters[0].value, 1.0)  # Device On bleibt an
        self.press(self.surface._buttons[L.BTN_BROWSER])
        self.assertTrue(view.browser)

    def test_live_stall_is_logged(self):
        self.surface.update_display()
        self.clock.now += 0.1
        self.surface.update_display()
        self.assertFalse(any("nicht reagiert" in line for line in self.surface.logs))
        self.clock.now += 2.0
        self.surface.update_display()
        self.assertIn("Live hat 2000 ms nicht reagiert (Geraet: Bass FX)", self.surface.logs[-1])

    def test_track_navigation_and_faders(self):
        faders = [f.mapped.original_name if f.mapped else None for f in self.surface._faders]
        self.assertEqual(faders, ["Track Volume"] + [None] * 7)
        self.press(self.surface._buttons[L.BTN_NEXT_TRACK])
        self.assertIs(self.song.view.selected_track, self.track2)
        self.assertIs(self.surface._faders[0].mapped, self.track2.mixer_device.volume)
        self.press(self.surface._buttons[L.BTN_NEXT_TRACK])
        self.press(self.surface._buttons[L.BTN_NEXT_TRACK])
        self.assertIs(self.song.view.selected_track, self.song.master_track)
        self.assertEqual(self.mapped(), [None] * 32)
        self.assertEqual(self.button_led(L.BTN_NEXT_TRACK), 0)

    # Layer B-E ---------------------------------------------------------------------------

    def track_led(self, index):
        button = self.surface._track_buttons[index]
        values = [m[2] for m in fakes.SENT if m[0] == (0x90 | button.channel) and m[1] == button.identifier]
        return values[-1] if values else None

    def test_layer_b_to_e_faders_follow_fixed_tracks(self):
        faders = self.surface._track_faders
        self.assertEqual(len(faders), 32)
        self.assertEqual((faders[0].channel, faders[0].identifier), (0, 92))
        self.assertEqual((faders[8].channel, faders[8].identifier), (2, 44))
        self.assertEqual((faders[16].channel, faders[16].identifier), (2, 92))
        self.assertEqual((faders[24].channel, faders[24].identifier), (4, 44))
        self.assertIs(faders[0].mapped, self.track1.mixer_device.volume)
        self.assertIs(faders[1].mapped, self.track2.mixer_device.volume)
        self.assertEqual([f.mapped for f in faders[2:]], [None] * 30)
        # Spurwahl aendert nichts an Layer B
        self.press(self.surface._buttons[L.BTN_NEXT_TRACK])
        self.assertIs(faders[0].mapped, self.track1.mixer_device.volume)
        track3 = fakes.Track("Drums")
        self.song.tracks.append(track3)
        self.song.notify("tracks")
        self.assertIs(faders[2].mapped, track3.mixer_device.volume)
        more = [fakes.Track("T%d" % n) for n in range(4, 34)]
        self.song.tracks.extend(more)
        self.song.notify("tracks")
        self.assertIs(faders[16].mapped, more[13].mixer_device.volume)  # Spur 17 auf Layer D
        self.assertIs(faders[24].mapped, more[21].mixer_device.volume)  # Spur 25 auf Layer E
        self.assertIs(faders[31].mapped, more[28].mixer_device.volume)  # Spur 32

    def test_layer_b_buttons_mute_and_arm(self):
        buttons = self.surface._track_buttons
        self.assertEqual((buttons[0].channel, buttons[0].identifier), (1, 84))
        self.assertEqual((buttons[8].channel, buttons[8].identifier), (3, 35))
        self.assertEqual((buttons[16].channel, buttons[16].identifier), (3, 84))
        self.assertEqual((buttons[24].channel, buttons[24].identifier), (5, 35))
        self.assertEqual(self.track_led(0), 127)
        self.assertEqual(self.track_led(2), 0)  # keine Spur 3
        self.press(buttons[1])
        self.assertTrue(self.track2.mute)
        self.assertEqual(self.track_led(1), 0)
        self.track2.mute = False  # in Live wieder eingeschaltet
        self.assertEqual(self.track_led(1), 127)
        self.press(buttons[0], hold=L.TRACK_ARM_HOLD_SECONDS)
        self.assertTrue(self.track1.arm)
        self.assertFalse(self.track1.mute)
        self.press(buttons[0], hold=L.TRACK_ARM_HOLD_SECONDS - 0.5)  # zu kurz: Mute
        self.assertTrue(self.track1.mute)
        self.assertTrue(self.track1.arm)
        self.track1.can_be_armed = False
        self.press(buttons[0], hold=L.TRACK_ARM_HOLD_SECONDS)
        self.assertTrue(self.track1.arm)
        self.assertIn("kann nicht aufnehmen", self.surface.messages[-1])
        self.press(buttons[5])  # keine Spur 6: nichts passiert
        self.assertEqual(self.track_led(5), 0)

    def test_nested_device_steps_from_its_rack(self):
        chain = fakes.Subject()
        chain.canonical_parent = self.rack
        inner = fakes.Device("Reverb", "Reverb", ["Decay Time", "Dry/Wet"], canonical_parent=chain)
        self.track1.view.selected_device = inner
        self.track1.view.notify("selected_device")
        self.assertEqual(self.mapped()[:2], ["Decay Time", "Dry/Wet"])
        self.press(self.surface._buttons[L.BTN_NEXT_DEVICE])
        self.assertIs(self.surface._device, self.filter1)

    def test_ring_buttons_step_tracks_and_devices(self):
        ring = self.surface._remote_inputs[0]
        ring.receive_value(L.RING_NEXT_DEVICE)
        self.assertIs(self.surface._device, self.filter1)
        ring.receive_value(L.RING_PREV_DEVICE)
        self.assertIs(self.surface._device, self.rack)
        ring.receive_value(L.RING_NEXT_TRACK)
        self.assertIs(self.song.view.selected_track, self.track2)
        self.assertIs(self.surface._device, self.filter2)
        ring.receive_value(L.RING_PREV_TRACK)
        self.assertIs(self.song.view.selected_track, self.track1)
        ring.receive_value(1)  # andere Ring-Taste: nur Beatjump am Drop
        self.assertIs(self.song.view.selected_track, self.track1)
        self.assertIs(self.surface._device, self.rack)

    def test_layer_input_is_logged(self):
        self.surface._remote_inputs[1].receive_value(3)
        self.assertTrue(any("Layer-Taste" in line for line in self.surface.logs))


class ConditionalSlot(object):
    """Wie Lives ParameterSlotDescription: str() ist None, solange kein Geraet gesetzt ist."""

    def __init__(self, name, condition_parameter, else_name):
        self._parameter_host = None
        self._default_parameter_name = name
        self._cached_content = (None, None)
        self._condition_parameter = condition_parameter
        self._else_name = else_name

    def _calc_content(self):
        parameters = self._parameter_host.parameters if self._parameter_host else []
        for parameter in parameters:
            if parameter.original_name == self._condition_parameter and parameter.value > 0.5:
                return self._default_parameter_name, None
        return self._else_name, None

    def __str__(self):
        return self._cached_content[0]


class ParamBanksTest(unittest.TestCase):

    def test_conditional_bank_slots_follow_the_device(self):
        from Drop_V2.parambanks import auto_layout
        slot = ConditionalSlot("Synced Rate", "Sync On", "Free Rate")
        definitions = {"AutoFilter2": {"Filter": {"Parameters": ("Frequency", slot, "")}}}
        device = fakes.Device("AutoFilter2", "Auto Filter", ["Frequency", "Sync On", "Synced Rate", "Free Rate"])
        names = [p.original_name if p else None for p in auto_layout(device, definitions)]
        self.assertEqual(names, ["Frequency", "Free Rate"] + [None] * 6)
        device.parameters[2].value = 1.0  # Sync On
        names = [p.original_name if p else None for p in auto_layout(device, definitions)]
        self.assertEqual(names[:2], ["Frequency", "Synced Rate"])
        self.assertIsNone(slot._parameter_host)  # gemeinsame Definition bleibt unveraendert

    def test_max_device_lists_each_parameter_once_from_row_one(self):
        from Drop_V2.parambanks import auto_layout
        # wie der Shaper: Depth in Hauptbank und Bank 1, Shape hinten in Bank 1,
        # Rate, Smooth und Offset in keiner Bank
        device = fakes.Device("MxDeviceAudioEffect", "Shaper", ["Rate", "Depth", "Smooth", "Offset", "Shape"])
        banks = {-1: [2, -1, -1, -1, -1, -1, -1, -1],
                 0: [-1] * 8,
                 1: [2, -1, -1, -1, -1, 5, -1, -1]}
        device.get_bank_count = lambda: 2
        device.get_bank_parameters = lambda index: banks[index]
        names = [p.original_name if p else None for p in auto_layout(device, {})]
        self.assertEqual(names, ["Depth", "Shape", "Rate", "Smooth", "Offset"] + [None] * 3)

    def test_live_bank_repeating_a_parameter_maps_it_once(self):
        from Drop_V2.parambanks import auto_layout
        definitions = {"Saturator": {"A": {"Parameters": ("Drive", "Dry/Wet")},
                                     "B": {"Parameters": ("Dry/Wet", "Output")}}}
        device = fakes.Device("Saturator", "Saturator", ["Drive", "Dry/Wet", "Output"])
        names = [p.original_name if p else None for p in auto_layout(device, definitions)]
        self.assertEqual(names, ["Drive", "Dry/Wet"] + [None] * 6 + [None, "Output"] + [None] * 6)

    def test_unknown_bank_format_falls_back_to_all_parameters(self):
        from Drop_V2.parambanks import auto_layout
        definitions = {"Eq8": {"Bank": None}}
        device = fakes.Device("Eq8", "EQ Eight", ["Gain", "Freq"])
        names = [p.original_name if p else None for p in auto_layout(device, definitions)]
        self.assertEqual(names, ["Gain", "Freq"] + [None] * 6)


class ProjectFileTest(unittest.TestCase):

    def test_generated_project_matches_layout(self):
        with open(os.path.join(ROOT, "Drop_V2_Projekt.json")) as handle:
            project = json.load(handle)
        for index, cc in enumerate(L.KNOB_CCS):
            cid = L.knob_control_id(index)
            knob = project["map"]["rotary"][cid]
            self.assertEqual((knob["0"]["ch"], int(knob["0"]["msgNr"])), (L.KNOB_CHANNEL, cc))
            self.assertEqual((knob["1"]["ch"], int(knob["1"]["msgNr"]), knob["1"]["curveId"]), (L.KNOB_COLOR_CHANNEL, cc, 34))
            self.assertEqual((knob["feedbId"], knob["feedbSlot"], knob["feedbSlotVis"]), (34, 1, 2))
            self.assertEqual(knob["name"], "Macro %d" % (index + 1) if index < 24 else "Send %d" % (index - 23))
            self.assertLessEqual(len(knob["name"]), 15)
            push = project["map"]["rotbut"][cid]["0"]
            self.assertEqual((push["msgType"], push["ch"], int(push["msgNr"])), (2, L.PUSH_CHANNEL, L.KNOB_PUSH_NOTES[index]))
        notes = [int(project["map"]["mute"]["0%d" % i]["0"]["msgNr"]) for i in range(8)]
        self.assertEqual(tuple(notes), L.BUTTON_NOTES)
        colors = [project["map"]["mute"]["0%d" % i]["colId"] for i in range(8)]
        self.assertEqual(colors, [6, 7, 5, 5, 5, 5, 6, 7])  # 1 = 7, 2 = 8, 3-6 blau
        faders = project["map"]["fader"]
        names = [faders["0%d" % i]["name"] for i in range(8)]
        self.assertEqual(names, ["Track Volume"] + ["%d none" % n for n in range(2, 9)])
        self.assertEqual([faders["0%d" % i]["colId"] for i in range(8)], [9] + [8] * 7)  # rot, weiss
        self.assertEqual({faders["0%d" % i]["behavId"] for i in range(8)}, {11})  # One per Layer
        for layer, first in ((1, 0), (2, 8), (3, 16), (4, 24)):
            for i in range(8):
                control = faders["%d%d" % (layer, i)]
                button = project["map"]["mute"]["%d%d" % (layer, i)]
                self.assertEqual(control["name"], "%d Vol" % (first + i + 1))
                self.assertEqual(round(control["0"]["maxOut"] / 16383 * 127), L.VOLUME_FADER_MAX)
                self.assertEqual(button["name"], "%d Mute" % (first + i + 1))
                self.assertEqual((button["behavId"], button["feedbSlot"]), (4, 1))
        self.assertEqual(project["layers"]["1"]["name"], "Vol 1-8")
        self.assertEqual(project["layers"]["2"]["name"], "Vol 9-16")
        self.assertEqual(project["layers"]["3"]["name"], "Vol 17-24")
        self.assertEqual(project["layers"]["4"]["name"], "Vol 25-32")
        max_out = [project["map"]["fader"]["0%d" % i]["0"]["maxOut"] for i in range(8)]
        self.assertEqual(round(max_out[0] / 16383 * 127), L.VOLUME_FADER_MAX)
        self.assertEqual(max_out[1:], [16383] * 7)
        self.assertEqual(project["remote"]["levelRx"], 1)
        self.assertEqual(project["remote"]["chanRx"], L.REMOTE_CHANNEL)
        self.assertEqual(project["remote"]["levelTx"], 1)
        self.assertEqual(project["remote"]["deviceTx"], 0)
        self.assertEqual(project["remote"]["chanTx"], L.REMOTE_CHANNEL)
        self.assertEqual(project["settings"]["sendOnLoad"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
