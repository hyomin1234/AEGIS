def choose_action(node_name: str, func_name: str):
    name = node_name.lower()
    func = func_name.lower()

    if "reset" in name or "rst" in name or "enable" in name:
        return {"action": "ISOLATE", "reason": "Critical control signal name match"}
    if "trigger" in func or "unknown" in func:
        return {"action": "CUT_TIE", "reason": "Likely trigger or unknown logic"}
    if "counter" in func or "comparator" in func:
        return {"action": "ISOLATE", "reason": "Stateful or comparison logic"}
    return {"action": "BYPASS", "reason": "Default to bypass"}
