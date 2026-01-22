from typing import Dict, List

import torch

from config import FUNC_LABELS
from rules import choose_action


def _neighbors(edge_index: torch.Tensor, node_idx: int) -> List[int]:
    if edge_index.numel() == 0:
        return []
    src = edge_index[0].tolist()
    dst = edge_index[1].tolist()
    out = []
    for u, v in zip(src, dst):
        if u == node_idx:
            out.append(v)
        elif v == node_idx:
            out.append(u)
    return sorted(set(out))


def _neighbors_by_direction(edge_index: torch.Tensor, node_idx: int):
    if edge_index.numel() == 0:
        return [], []
    src = edge_index[0].tolist()
    dst = edge_index[1].tolist()
    in_nodes = []
    out_nodes = []
    for u, v in zip(src, dst):
        if v == node_idx:
            in_nodes.append(u)
        if u == node_idx:
            out_nodes.append(v)
    return sorted(set(in_nodes)), sorted(set(out_nodes))


def _first_name(node_names: List[str], indices: List[int]):
    for idx in indices:
        if idx < len(node_names):
            return node_names[idx]
    return None


def build_actions(
    data,
    predictions: List[Dict],
    threshold: float = 0.6,
    top_k: int = 10,
):
    suspects = [p for p in predictions if p["trojan_prob"] >= threshold]
    if not suspects:
        suspects = sorted(predictions, key=lambda x: x["trojan_prob"], reverse=True)[:top_k]

    node_names = getattr(data, "node_names", [str(i) for i in range(data.num_nodes)])
    actions = []
    for p in suspects:
        idx = p["node_idx"]
        name = node_names[idx] if idx < len(node_names) else str(idx)
        func_id = p.get("func_id", 0)
        func_name = p.get("func_name", FUNC_LABELS[func_id] if func_id < len(FUNC_LABELS) else "Unknown")

        in_nodes, out_nodes = _neighbors_by_direction(data.edge_index, idx)
        net_in = _first_name(node_names, in_nodes) or name
        net_out = _first_name(node_names, out_nodes) or name

        rule = choose_action(name, func_name)
        action = rule.get("action", "CUT_TIE")
        item = {"node_name": name, "action": action, "reason": rule.get("reason", "")}

        if action == "CUT_TIE":
            item["net"] = net_out or net_in or name
            item["val"] = "0"
        elif action == "BYPASS":
            item["net_in"] = net_in
            item["net_out"] = net_out
        elif action == "ISOLATE":
            item["safe_net"] = net_out
            item["sel_net"] = net_in
        actions.append(item)
    return actions


def build_prompt(
    data,
    predictions: List[Dict],
    threshold: float = 0.6,
    top_k: int = 10,
):
    suspects = [p for p in predictions if p["trojan_prob"] >= threshold]
    if not suspects:
        suspects = sorted(predictions, key=lambda x: x["trojan_prob"], reverse=True)[:top_k]

    node_names = getattr(data, "node_names", [str(i) for i in range(data.num_nodes)])
    lines = []
    lines.append("Analysis Report:")
    for p in suspects:
        idx = p["node_idx"]
        name = node_names[idx] if idx < len(node_names) else str(idx)
        func_name = p.get("func_name", FUNC_LABELS[p["func_id"]] if p["func_id"] < len(FUNC_LABELS) else "Unknown")
        nbrs = _neighbors(data.edge_index, idx)
        nbr_names = [node_names[n] if n < len(node_names) else str(n) for n in nbrs[:5]]
        lines.append(f"- Suspect Node: {name}")
        lines.append(f"  Trojan Prob: {p['trojan_prob']:.3f}")
        lines.append(f"  Functional Type: {func_name}")
        lines.append(f"  Neighbors: {', '.join(nbr_names) if nbr_names else 'None'}")

    lines.append("")
    lines.append("Task: Provide a Tcl ECO script using only CUT_TIE, BYPASS, or ISOLATE.")
    return "\n".join(lines)
