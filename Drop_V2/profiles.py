# Gelernte Belegungen pro Geraetetyp, gespeichert als JSON ausserhalb jedes Live-Sets.
#
# Ein Profil haelt fuer jeden Regler-Slot (0 = Seite 1 Regler 1, 32 = Seite 2 Regler 1 ...)
# einen Verweis auf einen Parameter: dessen original_name plus Index als Hinweis.
# Fehlende Slots sind frei. "learned" unterscheidet selbst gelernte von automatisch
# uebernommenen Slots (nur fuer die Reglerfarbe).

import json
import os
import time

FORMAT_VERSION = 1

RACK_CLASSES = ("AudioEffectGroupDevice", "MidiEffectGroupDevice", "InstrumentGroupDevice", "DrumGroupDevice")
PLUGIN_CLASSES = ("PluginDevice", "AuPluginDevice")


def device_key(device):
    """Live-Geraete gelten pro Typ. Racks, Plugins und Max-Geraete zusaetzlich pro Name."""
    class_name = device.class_name
    if class_name in RACK_CLASSES or class_name in PLUGIN_CLASSES or class_name.startswith("MxDevice"):
        return "%s:%s" % (class_name, device.name)
    return class_name


def param_ref(parameters, parameter):
    index = -1
    for i, candidate in enumerate(parameters):
        if candidate == parameter:
            index = i
            break
    return {"name": parameter.original_name, "index": index}


def resolve_ref(parameters, ref):
    name = ref.get("name")
    index = ref.get("index", -1)
    if 0 <= index < len(parameters) and parameters[index].original_name == name:
        return parameters[index]
    for candidate in parameters:
        if candidate.original_name == name:
            return candidate
    return None


def _same_parameter(a, b):
    return a.get("name") == b.get("name") and a.get("index") == b.get("index")


class ProfileStore(object):

    def __init__(self, path, log=None):
        self._path = path
        self._log = log or (lambda *a: None)
        self._profiles = {}
        self._load()

    @property
    def path(self):
        return self._path

    def _load(self):
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as handle:
                data = json.load(handle)
            self._profiles = data.get("profiles", {})
        except Exception as error:
            self._log("Profile konnten nicht gelesen werden:", self._path, error)

    def _save(self):
        folder = os.path.dirname(self._path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        temp_path = self._path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump({"version": FORMAT_VERSION, "profiles": self._profiles}, handle, indent=2, sort_keys=True, ensure_ascii=False)
        os.replace(temp_path, self._path)

    def has(self, key):
        return key in self._profiles

    def slots(self, key):
        """{slot: ref} oder None, wenn das Geraet kein Profil hat."""
        profile = self._profiles.get(key)
        if profile is None:
            return None
        return dict((int(slot), ref) for slot, ref in profile.get("slots", {}).items())

    def _profile_for_edit(self, key, label, base_refs):
        profile = self._profiles.get(key)
        if profile is None:
            slots = {}
            for slot, ref in enumerate(base_refs):
                if ref is not None:
                    slots[str(slot)] = dict(ref, learned=False)
            profile = {"label": label, "slots": slots}
            self._profiles[key] = profile
        profile["label"] = label
        profile["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return profile

    def assign(self, key, label, base_refs, slot, ref):
        """Legt ref auf slot. Liegt derselbe Parameter schon auf einem anderen Slot, wird er dort entfernt."""
        profile = self._profile_for_edit(key, label, base_refs)
        slots = profile["slots"]
        for other in list(slots):
            if other != str(slot) and _same_parameter(slots[other], ref):
                del slots[other]
        slots[str(slot)] = dict(ref, learned=True)
        self._save()

    def clear(self, key, label, base_refs, slot):
        profile = self._profile_for_edit(key, label, base_refs)
        profile["slots"].pop(str(slot), None)
        self._save()

    def delete(self, key):
        if self._profiles.pop(key, None) is not None:
            self._save()
            return True
        return False
