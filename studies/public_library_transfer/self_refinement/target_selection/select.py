"""Select frozen behavior settings using only the current public prefix."""
from copy import deepcopy
import re


def option_key(key):
    key = re.sub(r"^(?:show|enable|use)-", "", key, flags=re.I)
    return re.sub(r"[^a-z0-9]", "", key.lower())


def feature_plan(example, prefix, *, nested, constant=None):
    plan = deepcopy(example)
    values = plan["defaults"] if nested else plan
    fields = {option_key(name) for name in re.findall(r"\boptions\.([a-zA-Z_]\w*)", prefix)}
    for key, value in values.items():
        if type(value) is bool:
            values[key] = option_key(key) in fields if constant is None else constant
    return plan


def witnessed_setting(options, prefix):
    if not options:
        return None
    bits = []
    for item in options:
        probe = item["candidate"]["probe"]
        tokens = re.findall(r"[#.]([a-zA-Z_][\w-]*)", probe["watch"])
        alternative = False
        if tokens and probe["measure"] in ("count", "visible"):
            token = re.escape(tokens[-1])
            mentioned = re.search(rf"""(?:['"`]{token}['"`]|[.#]{token}(?![\w-]))""", prefix)
            is_positive = {}
            for setting, readings in item["observations"].items():
                assert len(readings) == 2 and readings[0]["after"] == readings[1]["after"]
                is_positive[setting] = readings[0]["after"] > 0
            alternative = bool(mentioned and is_positive["alternative"] and not is_positive["original"])
        bits.append("1" if alternative else "0")
    return "".join(bits)
