import argparse
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser(description="Attach function labels to a .pt graph")
    parser.add_argument("--pt", required=True, help="Input .pt file")
    parser.add_argument("--out", help="Output .pt file (default: overwrite input)")
    parser.add_argument("--func-label", type=int, required=True, help="Function class id to assign")
    parser.add_argument(
        "--nodes",
        help="Optional text file with node names to label (one per line). If omitted, all nodes are labeled.",
    )
    args = parser.parse_args()

    pt_path = Path(args.pt).resolve()
    out_path = Path(args.out).resolve() if args.out else pt_path

    data = torch.load(pt_path)
    node_names = getattr(data, "node_names", [str(i) for i in range(data.num_nodes)])
    name_to_idx = {n: i for i, n in enumerate(node_names)}

    if args.nodes:
        nodes = {
            line.strip()
            for line in Path(args.nodes).read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        }
        mask = torch.zeros(data.num_nodes, dtype=torch.bool)
        for n in nodes:
            if n in name_to_idx:
                mask[name_to_idx[n]] = True
    else:
        mask = torch.ones(data.num_nodes, dtype=torch.bool)

    y_func = torch.full((data.num_nodes,), int(args.func_label), dtype=torch.long)
    data.y_func = y_func
    data.func_mask = mask

    torch.save(data, out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
