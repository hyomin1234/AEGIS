import argparse
import json
from pathlib import Path

import networkx as nx
import torch
from torch_geometric.data import Data

from standalone_parser import parse_netlist


def _load_graph_from_netlist(netlist_path: Path):
    return parse_netlist(netlist_path)


GATE_TYPES = [
    "AND",
    "NAND",
    "OR",
    "NOR",
    "XOR",
    "XNOR",
    "INV",
    "BUF",
    "MUX",
    "DFF",
    "DLH",
    "HA",
    "FA",
    "AOI",
    "OAI",
    "INPUT",
    "OUTPUT",
    "CONST",
    "UNKNOWN",
]
TYPE2IDX = {t: i for i, t in enumerate(GATE_TYPES)}


def _normalize_type(tpe: str) -> str:
    if not tpe:
        return "UNKNOWN"
    tpe = tpe.upper()
    if tpe in TYPE2IDX:
        return tpe
    if tpe in ["INPUT", "OUTPUT", "CONST"]:
        return tpe
    return "UNKNOWN"


def _build_features(g: nx.DiGraph, node_dict: dict, add_centrality: bool):
    node_names = list(g.nodes())
    idx = {n: i for i, n in enumerate(node_names)}

    x = torch.zeros(len(node_names), len(GATE_TYPES), dtype=torch.float32)
    for n in node_names:
        tpe = _normalize_type(getattr(node_dict.get(n), "tpe", None))
        x[idx[n], TYPE2IDX[tpe]] = 1.0

    deg_in = dict(g.in_degree())
    deg_out = dict(g.out_degree())

    pi_nodes = [
        n for n in node_names if _normalize_type(getattr(node_dict.get(n), "tpe", None)) == "INPUT"
    ]
    po_nodes = [
        n for n in node_names if _normalize_type(getattr(node_dict.get(n), "tpe", None)) == "OUTPUT"
    ]
    if not pi_nodes:
        pi_nodes = [n for n in node_names if deg_in.get(n, 0) == 0]
    if not po_nodes:
        po_nodes = [n for n in node_names if deg_out.get(n, 0) == 0]

    # level_in = nx.multi_source_shortest_path_length(g, pi_nodes) if pi_nodes else {}
    # 구버전에서도 돌아가는 다익스트라(Dijkstra) 함수로 교체
    level_in = nx.multi_source_dijkstra_path_length(g, pi_nodes) if pi_nodes else {}
    level_out = nx.multi_source_dijkstra_path_length(g.reverse(copy=False), po_nodes) if po_nodes else {}

    extra = torch.zeros(len(node_names), 4, dtype=torch.float32)
    for n in node_names:
        i = idx[n]
        extra[i, 0] = float(deg_in.get(n, 0))
        extra[i, 1] = float(deg_out.get(n, 0))
        extra[i, 2] = float(level_in.get(n, -1))
        extra[i, 3] = float(level_out.get(n, -1))

    if not add_centrality:
        return torch.cat([x, extra], dim=1), node_names

    betweenness = nx.betweenness_centrality(g.to_undirected(), normalized=True)
    centrality = torch.zeros(len(node_names), 1, dtype=torch.float32)
    for n in node_names:
        centrality[idx[n], 0] = float(betweenness.get(n, 0.0))

    return torch.cat([x, extra, centrality], dim=1), node_names


def _load_trojan_labels(trojan_path: Path, node_names: list) -> torch.Tensor:
    y = torch.zeros(len(node_names), dtype=torch.long)
    idx = {n: i for i, n in enumerate(node_names)}

    # 1. If trojan_path provided, load from file
    if trojan_path and trojan_path.exists():
        trojan_set = {
            line.strip()
            for line in trojan_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        }
        for name in trojan_set:
            if name in idx:
                y[idx[name]] = 1
        return y

    # 2. Fallback: Check if "trojan" is in the node name (Case-insensitive)
    for name in node_names:
        if "trojan" in name.lower():
            y[idx[name]] = 1
            
    return y


def _build_edge_index(g: nx.DiGraph, node_names: list) -> torch.Tensor:
    idx = {n: i for i, n in enumerate(node_names)}
    edges = [(idx[u], idx[v]) for u, v in g.edges()]
    if not edges:
        return torch.empty((2, 0), dtype=torch.long)
    return torch.tensor(edges, dtype=torch.long).t().contiguous()


def convert_netlist_to_data(netlist_path: Path, trojan_path: Path = None, add_centrality: bool = False):
    g, node_dict = _load_graph_from_netlist(netlist_path)
    x, node_names = _build_features(g, node_dict, add_centrality=add_centrality)
    edge_index = _build_edge_index(g, node_names)
    y_trojan = _load_trojan_labels(trojan_path, node_names)

    data = Data(x=x, edge_index=edge_index, y_trojan=y_trojan)
    data.node_names = node_names
    return data


def main():
    parser = argparse.ArgumentParser(description="Convert gate-level netlist to PyG Data")
    parser.add_argument("--netlist", required=True, help="Path to gate-level netlist")
    parser.add_argument("--trojan", help="Optional trojan gate list txt")
    parser.add_argument("--out", help="Output .pt path (default: same as netlist with .pt)")
    parser.add_argument("--add-centrality", action="store_true", help="Append betweenness centrality feature")
    parser.add_argument("--dump-map", help="Optional JSON path to dump node index -> name")
    args = parser.parse_args()

    netlist_path = Path(args.netlist).resolve()
    if not netlist_path.exists():
        raise FileNotFoundError(f"Netlist not found: {netlist_path}")

    trojan_path = Path(args.trojan).resolve() if args.trojan else None
    out_path = Path(args.out).resolve() if args.out else netlist_path.with_suffix(".pt")

    data = convert_netlist_to_data(
        netlist_path,
        trojan_path=trojan_path,
        add_centrality=args.add_centrality,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(data, out_path)

    if args.dump_map:
        dump_path = Path(args.dump_map).resolve()
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        node_names = getattr(data, "node_names", [str(i) for i in range(data.num_nodes)])
        mapping = {str(i): name for i, name in enumerate(node_names)}
        dump_path.write_text(json.dumps(mapping, indent=2), encoding="utf-8")

    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
