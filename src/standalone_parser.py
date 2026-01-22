import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx


@dataclass
class SimpleNode:
    tpe: str


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
    "D",
    "CK",
    "CLK",
    "A",
    "A0",
    "A1",
    "A2",
    "A3",
    "A4",
    "A1N",
    "A0N",
    "AN",
    "B",
    "B0",
    "B1",
    "B2",
    "B3",
    "B4",
    "B0N",
    "BN",
    "C",
    "C0",
    "C1",
    "C2",
    "DN",
    "RN",
    "SI",
    "SE",
    "SN",
    "S0",
    "S1",
    "S2",
    "S3",
    "GN",
    "EN",
    "I",
    "G",
    "E",
    "CI",
}

OUTPUT_PORTS = {"Q", "QN", "Z", "ZN", "Y", "CO", "O", "OUT", "GCK"}


DECL_RE = re.compile(r"^\s*(input|output|wire|reg|logic)\b", re.IGNORECASE)
ASSIGN_RE = re.compile(r"^\s*assign\b", re.IGNORECASE)


def _strip_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return text


def _split_statements(text: str) -> List[str]:
    # 세미콜론(;) 기준으로 그냥 자릅니다. (DC 넷리스트는 포맷이 일정해서 이걸로 충분)
    # 빈 줄이나 공백만 있는 항목은 제거합니다.
    return [s.strip() for s in text.split(";") if s.strip()]


def _parse_decl(stmt: str) -> Tuple[str, List[str]]:
    kind = stmt.strip().split()[0].lower()
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", stmt)
    keywords = {"input", "output", "wire", "reg", "logic", "signed"}
    names = [t for t in tokens if t.lower() not in keywords]
    return kind, names


def _strip_param_block(stmt: str) -> str:
    idx = stmt.find("#(")
    if idx == -1:
        return stmt
    depth = 0
    for i in range(idx, len(stmt)):
        ch = stmt[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return stmt[:idx] + " " + stmt[i + 1 :]
    return stmt


def _normalize_gate_type(cell_type: str) -> str:
    tpe = cell_type.upper()
    
    # 1. 자주 나오는 것부터 빠르게 리턴 (Prefix 매칭)
    if tpe.startswith("DFF"): return "DFF"
    if tpe.startswith("AND"): return "AND"
    if tpe.startswith("NAND"): return "NAND"
    if tpe.startswith("OR"): return "OR"
    if tpe.startswith("NOR"): return "NOR"
    if tpe.startswith("XOR"): return "XOR"
    if tpe.startswith("XNOR"): return "XNOR"
    if tpe.startswith("INV"): return "INV"
    if tpe.startswith("NOT"): return "INV"
    if tpe.startswith("BUF"): return "BUF"
    if tpe.startswith("MUX"): return "MUX"
    if tpe.startswith("MX"): return "MUX"
    if tpe.startswith("FA"): return "FA"
    if tpe.startswith("HA"): return "HA"
    
    # 2. 위에서 안 걸린 특이한 것들은 기존 정규식으로 처리 (느리지만 빈도 낮음)
    for pattern, label in GATE_PATTERNS:
        if re.search(pattern, tpe):
            return label
            
    return "UNKNOWN"


def _is_output_port(port: str, gate_type: str) -> bool:
    p = port.upper()
    g = gate_type.upper()
    if p in OUTPUT_PORTS:
        return True
    if p == "S" and g in {"HA", "FA"}:
        return True
    return False


def _split_ports(port_str: str) -> List[str]:
    # 괄호 안의 콤마 등을 처리해야 하지만, 
    # DC 넷리스트(.A(n1), .B(n2))는 구조가 단순하므로 단순 split으로 처리 가능
    # 만약 복잡한 식( {} 연결 등)이 있다면 regex split을 씁니다.
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
    token_re = re.compile(r"\\?[A-Za-z_][A-Za-z0-9_\\/$\\.]*")
    nets = []
    for token in token_re.findall(expr):
        name = token.lstrip("\\")
        if not name:
            continue
        nets.append(name)
    return nets


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^\w$]+", "_", name)


def _parse_instance(stmt: str):
    stmt = _strip_param_block(stmt)
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)\s*$", stmt, flags=re.S)
    if not m:
        return None
    cell_type, inst_name, port_str = m.groups()
    gate_type = _normalize_gate_type(cell_type)
    ports = _split_ports(port_str)
    input_nets = []
    output_nets = []
    if any(p.strip().startswith(".") for p in ports):
        for p in ports:
            pm = re.match(r"^\.(\w+)\s*\(\s*(.*?)\s*\)$", p.strip(), flags=re.S)
            if not pm:
                continue
            port_name, expr = pm.groups()
            nets = _extract_net_list(expr)
            if not nets:
                continue
            if _is_output_port(port_name, gate_type):
                output_nets.extend(nets)
            else:
                input_nets.extend(nets)
    else:
        pos_nets = []
        for p in ports:
            nets = _extract_net_list(p)
            if nets:
                pos_nets.append(nets[0])
        if len(pos_nets) >= 2:
            input_nets = pos_nets[:-1]
            output_nets = [pos_nets[-1]]
        elif len(pos_nets) == 1:
            input_nets = pos_nets
    return {
        "name": inst_name,
        "tpe": gate_type,
        "inputs": input_nets,
        "outputs": output_nets,
    }


def _parse_assign(stmt: str, assign_idx: int):
    m = re.match(r"^\s*assign\s+(.*?)\s*=\s*(.*?)\s*$", stmt, flags=re.S | re.IGNORECASE)
    if not m:
        return None
    lhs, rhs = m.groups()
    lhs_nets = _extract_net_list(lhs)
    if not lhs_nets:
        return None
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
        "tpe": gate_type,
        "inputs": input_nets,
        "outputs": [lhs_net],
    }


def parse_netlist(netlist_path: Path) -> Tuple[nx.DiGraph, Dict[str, SimpleNode]]:
    text = netlist_path.read_text(encoding="utf-8", errors="ignore")
    text = _strip_comments(text)
    stmts = _split_statements(text)

    inputs = set()
    outputs = set()
    instances = []
    assign_idx = 0

    for stmt in stmts:
        if DECL_RE.match(stmt):
            kind, names = _parse_decl(stmt)
            if kind == "input":
                inputs.update(names)
            elif kind == "output":
                outputs.update(names)
            continue
        if ASSIGN_RE.match(stmt):
            inst = _parse_assign(stmt, assign_idx)
            if inst:
                instances.append(inst)
                assign_idx += 1
            continue
        inst = _parse_instance(stmt)
        if inst:
            instances.append(inst)

    g = nx.DiGraph()
    node_dict: Dict[str, SimpleNode] = {}
    net_driver = {}
    net_sinks = defaultdict(list)

    def add_node(name: str, tpe: str):
        if name not in node_dict:
            node_dict[name] = SimpleNode(tpe=tpe)
            g.add_node(name)

    for inst in instances:
        add_node(inst["name"], inst["tpe"])
        for net in inst["outputs"]:
            if net and net not in net_driver:
                net_driver[net] = inst["name"]
        for net in inst["inputs"]:
            if net:
                net_sinks[net].append(inst["name"])

    for net in sorted(inputs):
        node_name = f"IN::{net}"
        add_node(node_name, "INPUT")
        if net not in net_driver:
            net_driver[net] = node_name

    for net in sorted(outputs):
        node_name = f"OUT::{net}"
        add_node(node_name, "OUTPUT")
        net_sinks[net].append(node_name)

    for net in list(net_sinks.keys()):
        if net.startswith("CONST_"):
            add_node(net, "CONST")
            if net not in net_driver:
                net_driver[net] = net

    for net, sinks in net_sinks.items():
        src = net_driver.get(net)
        if not src:
            continue
        for sink in sinks:
            if src != sink:
                g.add_edge(src, sink)

    return g, node_dict
