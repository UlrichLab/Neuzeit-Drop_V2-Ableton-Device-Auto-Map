# Automatische Belegung, wenn fuer ein Geraet kein gelerntes Profil existiert.
#
#   Racks         -> Makro 1-8 in Reihe 1, Makro 9-16 in Reihe 2
#   Live-Geraete  -> Abletons eigene Parameterbaenke (wie bei Push), eine Bank pro Reihe;
#                    Baenke ohne einen einzigen Parameter fallen weg
#   Max-Geraete   -> lueckenlos: Hauptbank, Baenke des Geraets, dann alle uebrigen Parameter
#   alles andere  -> alle Parameter der Reihe nach (ohne "Device On")
# Jeder Parameter liegt nur auf einem Regler.
#
# Rueckgabe ist eine Liste von Parametern oder None, Laenge ein Vielfaches von 8.

from .profiles import RACK_CLASSES

BANK_SIZE = 8
DEVICE_ON_NAME = "Device On"
MX_MAIN_BANK_INDEX = -1  # so fragt Live die Hauptbank eines Max-Geraets ab


def load_bank_definitions(log=None):
    """Liest Abletons Bankdefinitionen aus den mitgelieferten Live-Skripten."""
    for module_name in ("ableton.v3.control_surface", "ableton.v2.control_surface"):
        try:
            package = __import__(module_name + ".default_bank_definitions", fromlist=["BANK_DEFINITIONS"])
            keys = __import__(module_name, fromlist=["BANK_PARAMETERS_KEY"])
            return package.BANK_DEFINITIONS, keys.BANK_PARAMETERS_KEY
        except Exception as error:
            if log:
                log("Bankdefinitionen aus", module_name, "nicht verfuegbar:", error)
    return {}, "Parameters"


def _pad(parameters):
    remainder = len(parameters) % BANK_SIZE
    if remainder:
        parameters = parameters + [None] * (BANK_SIZE - remainder)
    return parameters


def _by_original_name(parameters, name):
    for parameter in parameters:
        if parameter.original_name == name:
            return parameter
    return None


def _rack_macros(device, parameters):
    count = getattr(device, "visible_macro_count", 8)
    return [_by_original_name(parameters, "Macro %d" % number) for number in range(1, count + 1)]


def _slot_name(slot_definition, device):
    """Parametername eines Bank-Eintrags.

    Meist ist der Eintrag ein Text. Bedingte Eintraege wie
    use("Synced Rate").if_parameter("Sync On").has_value("On").else_use("Free Rate")
    kennen ihren Namen erst, wenn Live ihnen ein Geraet gibt; ohne Geraet liefert str()
    None. Die Definitionen teilen sich alle Skripte, deshalb wird das Geraet nur fuer
    diese Rechnung eingesetzt und danach zurueckgestellt.
    """
    if isinstance(slot_definition, str):
        return slot_definition
    try:
        host = slot_definition._parameter_host
        slot_definition._parameter_host = device
        try:
            name = slot_definition._calc_content()[0]
        finally:
            slot_definition._parameter_host = host
    except Exception:
        name = getattr(slot_definition, "_default_parameter_name", "")
    return name if isinstance(name, str) else ""


def _described_banks(definition, parameters_key, device, parameters):
    rows = []
    used = set()
    for bank in definition.values():
        names = bank.get(parameters_key) or ()
        row = []
        for slot_definition in names[:BANK_SIZE]:
            name = _slot_name(slot_definition, device)
            parameter = _by_original_name(parameters, name) if name else None
            if parameter is not None and id(parameter) in used:
                parameter = None  # steht schon in einer frueheren Bank
            if parameter is not None:
                used.add(id(parameter))
            row.append(parameter)
        rows.append(row + [None] * (BANK_SIZE - len(row)))
    return _without_empty_rows(rows)


def _max_banks(device, parameters, bank_count):
    """Max-Baenke legen oft nur einzelne Parameter fest, verstreut und doppelt (Depth in
    Hauptbank und Bank 1). Deshalb nur ihre Reihenfolge nehmen: Hauptbank, Baenke, dann
    alle uebrigen Parameter, lueckenlos und jeder nur einmal."""
    order = []
    try:
        order += list(device.get_bank_parameters(MX_MAIN_BANK_INDEX))
    except Exception:
        pass  # Geraet ohne Hauptbank
    for bank_index in range(bank_count):
        order += list(device.get_bank_parameters(bank_index))
    order += range(len(parameters))
    result = []
    used = set()
    for index in order:
        if 0 <= index < len(parameters) and index not in used:
            used.add(index)
            if parameters[index].original_name != DEVICE_ON_NAME:
                result.append(parameters[index])
    return result


def _without_empty_rows(rows):
    """Reihen ohne einen einzigen Parameter fallen weg, damit die Belegung oben anfaengt."""
    return [parameter for row in rows if any(row) for parameter in row]


def auto_layout(device, bank_definitions=None, parameters_key="Parameters"):
    parameters = list(device.parameters)
    class_name = device.class_name
    layout = None
    if class_name in RACK_CLASSES:
        layout = _rack_macros(device, parameters)
    elif bank_definitions and class_name in bank_definitions:
        try:
            layout = _described_banks(bank_definitions[class_name], parameters_key, device, parameters)
        except Exception:
            layout = None  # unbekanntes Format in einer neuen Live-Version: der Reihe nach
    elif class_name.startswith("MxDevice") and hasattr(device, "get_bank_count"):
        try:
            bank_count = device.get_bank_count()
            if bank_count > 0:
                layout = _max_banks(device, parameters, bank_count)
        except Exception:
            layout = None
    if not layout or not any(layout):
        layout = [p for p in parameters if p.original_name != DEVICE_ON_NAME]
    return _pad(layout)
