from pathlib import Path
from typing import Dict, List


def _tcl_cut_tie(node: str, net: str = "NET_NAME", val: str = "0"):
    return [
        f"## CUT_TIE {node}",
        f"disconnect_net [get_nets {net}] [get_pins {node}/*]",
        f"set_constant {val} [get_pins {node}/*]",
    ]


def _tcl_bypass(node: str, net_in: str = "NET_IN", net_out: str = "NET_OUT"):
    return [
        f"## BYPASS {node}",
        f"disconnect_net [get_nets {net_in}] [get_pins {node}/*]",
        f"disconnect_net [get_nets {net_out}] [get_pins {node}/*]",
        f"connect_net [get_nets {net_in}] [get_pins {node}/A]",
        f"connect_net [get_nets {net_out}] [get_pins {node}/Y]",
    ]


def _tcl_isolate(node: str, safe_net: str = "SAFE_NET", sel_net: str = "SEL_NET"):
    iso_cell = f"U_iso_{node}"
    return [
        f"## ISOLATE {node}",
        f"create_cell {iso_cell} MUX2_X1",
        f"connect_net [get_nets {sel_net}] [get_pins {iso_cell}/S]",
        f"connect_net [get_nets {safe_net}] [get_pins {iso_cell}/A]",
        f"connect_net [get_nets {node}] [get_pins {iso_cell}/B]",
    ]


def generate_tcl(actions: List[Dict], out_path: Path):
    lines = ["# Auto-generated ECO script (template)"]
    for item in actions:
        node = item.get("node_name", "NODE")
        action = item.get("action", "CUT_TIE")
        if action == "CUT_TIE":
            lines.extend(_tcl_cut_tie(node, item.get("net", "NET_NAME"), item.get("val", "0")))
        elif action == "BYPASS":
            lines.extend(_tcl_bypass(node, item.get("net_in", "NET_IN"), item.get("net_out", "NET_OUT")))
        elif action == "ISOLATE":
            lines.extend(_tcl_isolate(node, item.get("safe_net", "SAFE_NET"), item.get("sel_net", "SEL_NET")))
        else:
            lines.append(f"## UNKNOWN ACTION {action} for {node}")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
