"""Minimale Attrappen von Live und _Framework, damit Drop V2 ohne Ableton laeuft.

Nur das, was Drop V2 tatsaechlich benutzt. install() traegt die Module in sys.modules ein.
"""

import sys
import types
from collections import OrderedDict
from contextlib import contextmanager

SENT = []  # alle gesendeten MIDI-Bytes, egal ob von Elementen oder vom Skript


class Subject(object):
    """Live-Objekt mit add_<event>_listener / remove_<event>_listener."""

    def __init__(self):
        self.__dict__["_listeners"] = {}

    def __getattr__(self, name):
        if name.startswith("add_") and name.endswith("_listener"):
            event = name[4:-9]
            return lambda callback: self._listeners.setdefault(event, []).append(callback)
        if name.startswith("remove_") and name.endswith("_listener"):
            event = name[7:-9]
            return lambda callback: self._listeners[event].remove(callback)
        raise AttributeError(name)

    def notify(self, event, *args):
        for callback in list(self._listeners.get(event, [])):
            callback(*args)

    def listener_count(self, event):
        return len(self._listeners.get(event, []))


# --- Live ----------------------------------------------------------------------------------

class Device(Subject):
    def __init__(self, class_name, name, parameter_names, canonical_parent=None, macro_count=None):
        super(Device, self).__init__()
        self.class_name = class_name
        self.name = name
        self.canonical_parent = canonical_parent
        self.parameters = [Parameter("Device On", self, value=1.0, maximum=1.0, quantized=True)]
        self.parameters += [Parameter(n, self) for n in parameter_names]
        if macro_count is not None:
            self.visible_macro_count = macro_count


class Parameter(Subject):
    def __init__(self, original_name, owner, value=0.5, maximum=1.0, quantized=False, default=0.25):
        super(Parameter, self).__init__()
        self.original_name = original_name
        self.name = original_name
        self.canonical_parent = owner
        self.min = 0.0
        self.max = maximum
        self.is_quantized = quantized
        self.is_enabled = True
        self.default_value = default
        self.__dict__["_value"] = value

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.__dict__["_value"] = value
        self.notify("value")

    def __repr__(self):
        return "<Param %s>" % self.original_name


class MixerDevice(Subject):
    def __init__(self, send_count):
        super(MixerDevice, self).__init__()
        self.volume = Parameter("Track Volume", self)
        self.panning = Parameter("Track Panning", self)
        self.sends = tuple(Parameter("Send %s" % chr(65 + i), self) for i in range(send_count))


class TrackView(Subject):
    def __init__(self):
        super(TrackView, self).__init__()
        self.selected_device = None


class Clip(object):
    def __init__(self, color_index, playing=False, recording=False, triggered=False):
        self.color_index = color_index
        self.is_playing = playing
        self.is_recording = recording
        self.is_triggered = triggered


class ClipSlot(object):
    def __init__(self):
        self.clip = None
        self.fired = 0

    @property
    def has_clip(self):
        return self.clip is not None

    def fire(self):
        self.fired += 1


class Scene(object):
    def __init__(self):
        self.fired = 0

    def fire(self):
        self.fired += 1


class Track(Subject):
    def __init__(self, name, send_count=2):
        super(Track, self).__init__()
        self.name = name
        self.devices = []
        self.view = TrackView()
        self.mixer_device = MixerDevice(send_count)
        self.clip_slots = []
        self.fired_slot_index = -1
        self.stopped = 0
        self.__dict__["_mute"] = False
        self.arm = False
        self.can_be_armed = True

    @property
    def mute(self):
        return self._mute

    @mute.setter
    def mute(self, value):
        self.__dict__["_mute"] = value
        self.notify("mute")

    def stop_all_clips(self):
        self.stopped += 1

    def add_device(self, device):
        device.canonical_parent = self
        self.devices.append(device)
        self.notify("devices")
        return device


class SongView(Subject):
    def __init__(self, song):
        super(SongView, self).__init__()
        self._song = song
        self.__dict__["_selected_track"] = None
        self.selected_parameter = None

    @property
    def selected_track(self):
        return self._selected_track

    @selected_track.setter
    def selected_track(self, track):
        self.__dict__["_selected_track"] = track
        self.notify("selected_track")

    def select_device(self, device):
        node = device
        while not isinstance(node, Track):
            node = node.canonical_parent
        if self.selected_track is not node:
            self.selected_track = node
        node.view.selected_device = device
        node.view.notify("selected_device")

    def click_parameter(self, parameter):
        self.selected_parameter = parameter
        self.notify("selected_parameter")


class Song(Subject):
    def __init__(self, tracks, returns=0, scenes=4):
        super(Song, self).__init__()
        self.tracks = list(tracks)
        self.visible_tracks = list(tracks)
        self.return_tracks = [Track("Return %d" % i, 0) for i in range(returns)]
        self.master_track = Track("Master", 0)
        self.scenes = [Scene() for _ in range(scenes)]
        for track in self.visible_tracks:
            track.clip_slots = [ClipSlot() for _ in range(scenes)]
        self.is_playing = False
        self.all_stopped = 0
        self.view = SongView(self)
        self.view.__dict__["_selected_track"] = self.visible_tracks[0]

    def stop_all_clips(self):
        self.all_stopped += 1


class MapMode(object):
    absolute = "absolute"


class AppView(object):
    def __init__(self):
        self.visible = "Detail/Clip"
        self.main = "Session"
        self.detail = True
        self.browser = True

    def is_view_visible(self, name):
        if name == "Detail":
            return self.detail
        if name == "Browser":
            return self.browser
        return name in (self.visible, self.main)

    def show_view(self, name):
        if name in ("Session", "Arranger"):
            self.main = name
        elif name == "Detail":
            self.detail = True
        elif name == "Browser":
            self.browser = True
        else:
            self.visible = name
            self.detail = True

    def hide_view(self, name):
        if name == "Detail":
            self.detail = False
        if name == "Browser":
            self.browser = False


class Application(object):
    def __init__(self):
        self.view = AppView()


# --- _Framework ----------------------------------------------------------------------------

MIDI_NOTE_TYPE = 0
MIDI_CC_TYPE = 1


class InputControlElement(Subject):
    def __init__(self, msg_type, channel, identifier, *a, **k):
        super(InputControlElement, self).__init__()
        self.msg_type = msg_type
        self.channel = channel
        self.identifier = identifier
        self.mapped = None

    def connect_to(self, parameter):
        self.mapped = parameter

    def release_parameter(self):
        self.mapped = None

    def send_value(self, value, force=False, channel=None):
        status = (0x90 if self.msg_type == MIDI_NOTE_TYPE else 0xB0) | self.channel
        SENT.append((status, self.identifier, int(value)))

    def receive_value(self, value):
        self.notify("value", value)


class EncoderElement(InputControlElement):
    def __init__(self, msg_type, channel, identifier, map_mode, *a, **k):
        super(EncoderElement, self).__init__(msg_type, channel, identifier)


class SliderElement(InputControlElement):
    pass


class ButtonElement(InputControlElement):
    def __init__(self, is_momentary, msg_type, channel, identifier, *a, **k):
        super(ButtonElement, self).__init__(msg_type, channel, identifier)


class ControlSurface(object):
    def __init__(self, c_instance):
        self._c_instance = c_instance
        self.messages = []
        self.logs = []
        self.scheduled = []
        self._application = Application()

    def song(self):
        return self._c_instance.song()

    def application(self):
        return self._application

    @contextmanager
    def component_guard(self):
        yield

    def schedule_message(self, delay, callback, parameter=None):
        self.scheduled.append(callback)

    def run_scheduled(self):
        while self.scheduled:
            self.scheduled.pop(0)()

    def show_message(self, message):
        self.messages.append(message)

    def log_message(self, *message):
        self.logs.append(" ".join(str(m) for m in message))

    def _send_midi(self, midi_bytes, optimized=True):
        SENT.append(tuple(midi_bytes))
        return True

    def refresh_state(self):
        pass

    def update_display(self):
        pass

    def build_midi_map(self, midi_map_handle):
        pass

    def disconnect(self):
        pass


class _Slot(object):
    def __init__(self, owner, method, event):
        self._owner = owner
        self._method = method
        self._event = event
        self._subject = None

    def _listener(self, *args):
        self._method(self._owner, *args)

    @property
    def subject(self):
        return self._subject

    @subject.setter
    def subject(self, subject):
        if self._subject is not None:
            getattr(self._subject, "remove_%s_listener" % self._event)(self._listener)
        self._subject = subject
        if subject is not None:
            getattr(subject, "add_%s_listener" % self._event)(self._listener)


class _SlotGroup(object):
    def __init__(self, owner, method, event):
        self._owner = owner
        self._method = method
        self._event = event

    def replace_subjects(self, subjects):
        for subject in subjects:
            getattr(subject, "add_%s_listener" % self._event)(
                lambda *args, s=subject: self._method(self._owner, *(args + (s,))))


def _slot_property(factory, event):
    def decorator(method):
        attribute = "_slot_" + method.__name__

        def getter(self):
            slot = self.__dict__.get(attribute)
            if slot is None:
                slot = self.__dict__[attribute] = factory(self, method, event)
            return slot
        return property(getter)
    return decorator


def subject_slot(event):
    return _slot_property(_Slot, event)


def subject_slot_group(event):
    return _slot_property(_SlotGroup, event)


# --- Abletons Bankdefinitionen (Ausschnitt) -------------------------------------------------

BANK_DEFINITIONS = {
    "AutoFilter2": OrderedDict((
        ("Filter", {"Parameters": ("Frequency", "Resonance", "Filter Type", "", "Drive", "", "", "Dry/Wet")}),
        ("LFO", {"Parameters": ("LFO Amount", "LFO Rate")}),
    )),
}


def install():
    def module(name, **attributes):
        mod = types.ModuleType(name)
        mod.__dict__.update(attributes)
        sys.modules[name] = mod
        return mod

    live = module("Live")
    live.MidiMap = module("Live.MidiMap", MapMode=MapMode)
    live.Device = module("Live.Device", Device=Device)
    module("_Framework")
    module("_Framework.ControlSurface", ControlSurface=ControlSurface)
    module("_Framework.ButtonElement", ButtonElement=ButtonElement)
    module("_Framework.EncoderElement", EncoderElement=EncoderElement)
    module("_Framework.SliderElement", SliderElement=SliderElement)
    module("_Framework.InputControlElement", MIDI_CC_TYPE=MIDI_CC_TYPE, MIDI_NOTE_TYPE=MIDI_NOTE_TYPE)
    module("_Framework.SubjectSlot", subject_slot=subject_slot, subject_slot_group=subject_slot_group)
    module("ableton")
    module("ableton.v3")
    module("ableton.v3.control_surface", BANK_PARAMETERS_KEY="Parameters")
    module("ableton.v3.control_surface.default_bank_definitions", BANK_DEFINITIONS=BANK_DEFINITIONS)
