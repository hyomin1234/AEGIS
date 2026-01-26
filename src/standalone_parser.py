import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Set

import networkx as nx


@dataclass
class SimpleNode:
    tpe: str


@dataclass
class ModuleDef:
    name: str
    inputs: Set[str]
    outputs: Set[str]
    wires: Set[str]
    instances: List[dict]
    assigns: List[dict]


GATE_PATTERNS = [
    (r"^(S)*DFF(R)*(S)*(\d)*_X(\d+)", "DFF"),
    (r"^DFF", "DFF"),
    (r"^INV(\d)*_X(\d+)", "INV"),
    (r"^NOT", "INV"),
    (r"^BUF(\d)*_X(\d+)", "BUF"),
    (r"^CLKBUF(\d)*_X(\d+)", "BUF"),
    (r"^TBUF(\d)*_X(\d+)", "BUF"),
    (r"^BUFH(\d)*_X(\d+)", "BUF"),
    (r"^XOR(\d)*_X(\d+)", "XOR"),
    (r"^XNOR(\d)*_X(\d+)", "XNOR"),
    (r"^AOI(\d)*_X(\d+)", "AOI"),
    (r"^AO(\w)*_X(\d+)", "AOI"),
    (r"^OAI(\w)*_X(\d+)", "OAI"),
    (r"^OA(\d)*_X(\d+)", "OAI"),
    (r"^OR(\d)*_X(\d+)", "OR"),
    (r"^NOR(\w)*_X(\d+)", "NOR"),
    (r"^NAND(\w)*_X(\d+)", "NAND"),
    (r"^AND(\d)*_X(\d+)", "AND"),
    (r"^MUX(\d)*_X(\d+)", "MUX"),
    (r"^MX(\w)*_X(\d+)", "MUX"),
    (r"^HA(\d)*_X(\d+)", "HA"),
    (r"^ADDH(\d)*_X(\d+)", "HA"),
    (r"^FA(\d)*_X(\d+)", "FA"),
    (r"^ADDF(\d)*_X(\d+)", "FA"),
    (r"^DLH(\d)*_X(\d+)", "DLH"),
]


INPUT_PORTS = {
    "D", "CK", "CLK", "A", "A0", "A1", "A2", "A3", "A4", "A1N", "A0N", "AN",
    "B", "B0", "B1", "B2", "B3", "B4", "B0N", "BN",
    "C", "C0", "C1", "C2", "DN", "RN", "SI", "SE", "SN",
    "S0", "S1", "S2", "S3", "GN", "EN", "I", "G", "E", "CI",
    "D0", "D1", "D2", "D3", "TE", "TI"
}

OUTPUT_PORTS = {"Q", "QN", "Z", "ZN", "Y", "CO", "O", "OUT", "GCK"}


DECL_RE = re.compile(r"^\s*(input|output|wire|reg|logic)\b", re.IGNORECASE)
ASSIGN_RE = re.compile(r"^\s*assign\b", re.IGNORECASE)


def _strip_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return text


def _split_statements(text: str) -> List[str]:
    # 세미콜론(;) 기준으로 그냥 자릅니다.
    return [s.strip() for s in text.split(";") if s.strip()]


def _parse_decl(stmt: str) -> Tuple[str, List[str]]:
    kind = stmt.strip().split()[0].lower()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stmt)
    keywords = {"input", "output", "wire", "reg", "logic", "signed", "tri", "tri1", "tri0"}
    names = [t for t in tokens if t.lower() not in keywords]
    return kind, names


def _strip_param_block(stmt: str) -> str:
    idx = stmt.find("#(")
    if idx == -1:
        return stmt
    depth = 0
    start = idx
    for i in range(idx, len(stmt)):
        ch = stmt[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                # Remove #(...) block
                return stmt[:start] + " " + stmt[i+1:]
    return stmt


def _normalize_gate_type(cell_type: str) -> str:
    tpe = cell_type.upper()
    if tpe.startswith("DFF"): return "DFF"
    if tpe.startswith("AND"): return "AND"
    if tpe.startswith("NAND"): return "NAND"
    if tpe.startswith("OR"): return "OR"
    if tpe.startswith("NOR"): return "NOR"
    if tpe.startswith("XOR"): return "XOR"
    if tpe.startswith("XNOR"): return "XNOR"
    if tpe.startswith("INV") or tpe.startswith("NOT"): return "INV"
    if tpe.startswith("BUF") or tpe.startswith("CLKBUF") or tpe.startswith("TBUF") or tpe.startswith("BUFH"): return "BUF"
    if tpe.startswith("MUX") or tpe.startswith("MX"): return "MUX"
    if tpe.startswith("FA") or tpe.startswith("ADDF"): return "FA"
    if tpe.startswith("HA") or tpe.startswith("ADDH"): return "HA"
    
    for pattern, label in GATE_PATTERNS:
        if re.search(pattern, tpe):
            return label
    return "UNKNOWN"


def _is_output_port(port: str, gate_type: str) -> bool:
    p = port.upper()
    g = gate_type.upper()
    if p in OUTPUT_PORTS: return True
    if p == "S" and g in {"HA", "FA"}: return True
    return False


def _split_ports(port_str: str) -> List[str]:
    parts = port_str.split(",")
    return [p.strip() for p in parts if p.strip()]


def _const_from_expr(expr: str):
    expr = expr.strip()
    if expr in {"0", "1", "1'b0", "1'b1"}:
        return "CONST_1" if "1" in expr else "CONST_0"
    m = re.match(r"^\d+'b([01xz]+)$", expr, flags=re.IGNORECASE)
    if m:
        bits = m.group(1)
        return "CONST_1" if "1" in bits else "CONST_0"
    return None


def _extract_net_list(expr: str) -> List[str]:
    const = _const_from_expr(expr)
    if const:
        return [const]
    # Simple regex for identifiers, possibly escaped
    token_re = re.compile(r"\\?[A-Za-z_][A-Za-z0-9_\\/$\\.]*")
    nets = []
    for token in token_re.findall(expr):
        name = token.lstrip("\\")
        if not name: continue
        nets.append(name)
    return nets


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^\w$]+", "_", name)


def _parse_instance(stmt: str):
    stmt = _strip_param_block(stmt)
    # Relaxed match: Type Name ( ... )
    # Use \S+ to capture type and name (handles escaped names like \foo[0] )
    m = re.match(r"^\s*(\S+)\s+(\S+)\s*\((.*)\)\s*$", stmt, flags=re.S)
    if not m:
        return None
    cell_type, inst_name, port_str = m.groups()
    gate_type = _normalize_gate_type(cell_type)
    ports = _split_ports(port_str)
    
    input_nets = []
    output_nets = []
    port_map = {}

    # Named mapping .Port(Net)
    if any(p.strip().startswith(".") for p in ports):
        for p in ports:
            pm = re.match(r"^\.(\w+)\s*\(\s*(.*?)\s*\)$", p.strip(), flags=re.S)
            if not pm: continue
            port_name, expr = pm.groups()
            port_map[port_name] = expr

            nets = _extract_net_list(expr)
            if not nets: continue
            
            if _is_output_port(port_name, gate_type):
                output_nets.extend(nets)
            else:
                input_nets.extend(nets)
    else:
        # Positional mapping
        pos_nets = []
        for p in ports:
            nets = _extract_net_list(p)
            if nets: pos_nets.append(nets[0])
        
        if len(pos_nets) >= 2:
            input_nets = pos_nets[:-1]
            output_nets = [pos_nets[-1]]
        elif len(pos_nets) == 1:
            input_nets = pos_nets

    return {
        "name": inst_name,
        "cell_type": cell_type, # Original type name (e.g. TSC)
        "tpe": gate_type,       # Normalized type (e.g. UNKNOWN if module)
        "inputs": input_nets,
        "outputs": output_nets,
        "port_map": port_map,
    }


def _parse_assign(stmt: str, assign_idx: int):
    m = re.match(r"^\s*assign\s+(.*?)\s*=\s*(.*?)\s*$", stmt, flags=re.S | re.IGNORECASE)
    if not m: return None
    lhs, rhs = m.groups()
    lhs_nets = _extract_net_list(lhs)
    if not lhs_nets: return None
    lhs_net = lhs_nets[0]
    
    rhs_expr = rhs.strip()
    gate_type = "BUF"
    if rhs_expr.startswith("~"):
        gate_type = "INV"
        rhs_expr = rhs_expr[1:].strip()
    
    input_nets = _extract_net_list(rhs_expr)
    name = f"assign_{assign_idx}_{_sanitize_name(lhs_net)}"
    
    return {
        "name": name,
        "cell_type": "ASSIGN",
        "tpe": gate_type,
        "inputs": input_nets,
        "outputs": [lhs_net],
        "port_map": {}
    }


def _split_modules(text: str) -> List[str]:
    # Split by endmodule. This is a heuristic.
    # We look for "endmodule" and capture everything before it back to "module"
    chunks = []
    # Normalize spaces
    
    # Logic: 
    # 1. Find all `module ... endmodule` ranges.
    # 2. Extract them.
    
    # We use regex with DOTALL.
    # Assuming valid verilog where module/endmodule are paired.
    # If nested modules (rare in netlists), this simple regex fails.
    # But netlists are usually flat list of modules.
    
    pattern = re.compile(r"\bmodule\s+.*?\bendmodule", re.S)
    matches = pattern.findall(text)
    return matches


def _parse_module_block(text: str) -> ModuleDef:
    # Remove module header/footer to parse body
    header_m = re.match(r"^\s*module\s+([A-Za-z0-9_]+)", text)
    if not header_m: return None
    module_name = header_m.group(1)
    
    # Get body: from first ';' to 'endmodule'
    # Or just rely on _split_statements filtering
    stmts = _split_statements(text)
    
    inputs = set()
    outputs = set()
    wires = set()
    instances = []
    assigns = []
    assign_idx = 0
    
    for stmt in stmts:
        if stmt.startswith("module ") or stmt.startswith("endmodule"):
            continue
            
        if DECL_RE.match(stmt):
            kind, names = _parse_decl(stmt)
            if kind == "input": inputs.update(names)
            elif kind == "output": outputs.update(names)
            elif kind in ("wire", "reg", "logic"): wires.update(names)
            continue
            
        if ASSIGN_RE.match(stmt):
            inst = _parse_assign(stmt, assign_idx)
            if inst:
                assigns.append(inst)
                assign_idx += 1
            continue
            
        inst = _parse_instance(stmt)
        if inst:
            instances.append(inst)
            
    return ModuleDef(module_name, inputs, outputs, wires, instances, assigns)


def _flatten_recursively(
    mod_name: str,
    modules: Dict[str, ModuleDef],
    prefix: str,
    net_map: Dict[str, str],
    flat_instances: List[dict]
):
    if mod_name not in modules:
        return

    mod = modules[mod_name]
    
    # helper
    def resolve(local_net):
        if local_net.startswith("CONST_"): return local_net
        if local_net not in net_map:
            net_map[local_net] = f"{prefix}{local_net}"
        return net_map[local_net]

    # Check if module is effectively empty (Blackbox/Stub)
    # If it has no instances and no assigns, but has inputs/outputs, it's likely a leaf macro.
    if not mod.instances and not mod.assigns:
        # Treat as leaf node
        # For the top module, this condition shouldn't happen usually.
        # But for 'TSC', this is what we want.
        # However, _flatten_recursively is called FOR checking instances.
        pass

    all_actions = mod.instances + mod.assigns
    for inst in all_actions:
        cell_type = inst["cell_type"]
        
        # Check if submodule exists AND IS NOT EMPTY
        # If submodule is empty (Stub), treat as Leaf.
        is_submodule = False
        if cell_type in modules:
            sub_mod = modules[cell_type]
            if sub_mod.instances or sub_mod.assigns:
                is_submodule = True
        
        if is_submodule:
            # === RECURSIVE EXPANSION ===
            sub_mod_name = cell_type
            sub_inst_name = inst["name"]
            new_prefix = f"{prefix}{sub_inst_name}."
            
            sub_net_map = {}
            port_map = inst.get("port_map", {})
            
            for p_name, expr in port_map.items():
                nets = _extract_net_list(expr)
                if nets:
                    current_net = nets[0]
                    global_net = resolve(current_net)
                    sub_net_map[p_name] = global_net
            
            _flatten_recursively(sub_mod_name, modules, new_prefix, sub_net_map, flat_instances)
            
        else:
            # === LEAF GATE (or Blackbox Module) ===
            new_inputs = [resolve(n) for n in inst["inputs"]]
            new_outputs = [resolve(n) for n in inst["outputs"]]
            
            flat_instances.append({
                "name": f"{prefix}{inst['name']}",
                "tpe": inst["tpe"], # Note: for TSC, tpe might be 'UNKNOWN' which is fine
                "inputs": new_inputs,
                "outputs": new_outputs
            })


def parse_netlist(netlist_path: Path) -> Tuple[nx.DiGraph, Dict[str, SimpleNode]]:
    text = netlist_path.read_text(encoding="utf-8", errors="ignore")
    text = _strip_comments(text)
    
    # 1. Parse all modules
    raw_blocks = _split_modules(text)
    modules: Dict[str, ModuleDef] = {}
    for block in raw_blocks:
        mdef = _parse_module_block(block)
        if mdef:
            modules[mdef.name] = mdef
            
    if not modules:
        # Fallback: treat whole file as one body if no 'module' keyword found properly
        # Make a dummy wrapper
        mdef = _parse_module_block("module TOP; " + text + " endmodule")
        if mdef:
            modules["TOP"] = mdef
            
    # 2. Identify Top Module
    # Heuristic: The last module in the file is usually Top
    top_name = list(modules.keys())[-1]
    
    # 3. Flatten
    flat_instances = []
    # Top module's ports are its own nets (no prefix usually, or empty prefix)
    _flatten_recursively(top_name, modules, "", {}, flat_instances)
    
    # 4. Build Graph
    g = nx.DiGraph()
    node_dict = {}
    net_driver = {}
    net_sinks = defaultdict(list)
    
    def add_node(name, tpe):
        if name not in node_dict:
            node_dict[name] = SimpleNode(tpe)
            g.add_node(name)
            
    for inst in flat_instances:
        add_node(inst["name"], inst["tpe"])
        for net in inst["outputs"]:
            if net: net_driver[net] = inst["name"]
        for net in inst["inputs"]:
            if net: net_sinks[net].append(inst["name"])
            
    # Add final edges
    for net, sinks in net_sinks.items():
        driver = net_driver.get(net)
        # Handle constants or unknown drivers
        if not driver:
            if net.startswith("CONST_"):
                add_node(net, "CONST")
                driver = net
            elif net.startswith("IN::"): 
                # Should have been added?
                pass
            else:
                # If it's a top-level input, we might need to add it explicitly
                # Our flattening logic didn't explicitly add input ports as nodes.
                # Let's add them if they appear in net_sinks but no driver.
                # But we don't know if they are truly inputs or floatings.
                # For now, if "IN::" logic was desired...
                pass
                
        if driver:
            for sink in sinks:
                if driver != sink:
                    g.add_edge(driver, sink)
                    
    # Re-add Top-Level Inputs/Outputs for Centrality/Feature calculation
    # The original _build_features relies on "INPUT" / "OUTPUT" nodes.
    # We should add them back.
    top_mod = modules[top_name]
    for inp in top_mod.inputs:
        n_name = f"IN::{inp}" # Flatten logic uses empty prefix for top, so just inp.
        # But wait, resolve() would have mapped 'inp' to 'inp'.
        # So we should check if 'inp' is in net_sinks.
        # Let's explicitly add INPUT nodes driving the top-level nets.
        add_node(n_name, "INPUT")
        net_driver[inp] = n_name
        
    for outp in top_mod.outputs:
        n_name = f"OUT::{outp}"
        add_node(n_name, "OUTPUT")
        net_sinks[outp].append(n_name)
        
    # Re-run edge connection for these new ports
    for net in [n for n in top_mod.inputs] + [n for n in top_mod.outputs]:
        # Connect logic duplicated here for safety
        driver = net_driver.get(net)
        sinks = net_sinks.get(net)
        if driver and sinks:
            for sink in sinks:
                if driver != sink:
                    g.add_edge(driver, sink)

    return g, node_dict
