import argparse
from pathlib import Path

import torch

from config import FUNC_LABELS
from netlist_to_pyg import convert_netlist_to_data


DEFAULT_KEYWORDS = [
    ("trigger", "Trigger"),
    ("counter", "Counter"),
    ("adder", "Adder"),
    ("comparator", "Comparator"),
    ("fsm", "FSM"),
    ("decoder", "Decoder"),
]


def _resolve_label(name: str, keywords):
    lowered = name.lower()
    for key, label in keywords:
        if key in lowered:
            return label
    return "Unknown"


def _label_id(label: str) -> int:
    if label.isdigit():
        return int(label)
    if label in FUNC_LABELS:
        return FUNC_LABELS.index(label)
    raise ValueError(f"Unknown label: {label}. Valid: {', '.join(FUNC_LABELS)}")


def main():
    parser = argparse.ArgumentParser(description="Build labeled .pt dataset from netlist files")
    parser.add_argument("--netlist-dir", default="../raw_data", help="Directory with netlist files (default: ../raw_data)")
    parser.add_argument("--out-dir", default="../output", help="Output directory for .pt graphs (default: ../output)")
    parser.add_argument("--add-centrality", action="store_true", default=True, help="Append 4 centrality features")
    parser.add_argument("--label", help="Override label for all files (name or id)")
    args = parser.parse_args()

    # Resolve paths relative to this script or current working directory
    base_dir = Path(__file__).resolve().parent
    # If arguments are provided as relative paths, resolve them against CWD (standard behavior),
    # but if they are defaults, we might want them relative to the script or a known root.
    # However, strict resolution often resolves against CWD.
    # Let's assume running from project root or inside src.
    # To be safe for "default" case relative to project structure (../raw_data), we can check:
    netlist_dir = Path(args.netlist_dir)
    if not netlist_dir.is_absolute() and args.netlist_dir == "../raw_data":
         # If default, interpret relative to this script's parent (src) -> parent (AEGIS)
         netlist_dir = (base_dir / args.netlist_dir).resolve()
    else:
         netlist_dir = netlist_dir.resolve()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute() and args.out_dir == "../output":
         out_dir = (base_dir / args.out_dir).resolve()
    else:
         out_dir = out_dir.resolve()

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Searching netlists in: {netlist_dir}")
    print(f"Output directory: {out_dir}")

    # Use rglob for recursive search
    files = sorted(netlist_dir.rglob("*.v"))
    if not files:
        # Fallback: try looking in current directory if recursive failed or logic was weird
        files = sorted(netlist_dir.glob("*.v"))
        
    if not files:
        raise FileNotFoundError(f"No netlist files found in {netlist_dir}")

    for netlist_path in files:
        label_name = args.label or _resolve_label(netlist_path.stem, DEFAULT_KEYWORDS)
        label_id = _label_id(label_name)

        print(f"Processing: {netlist_path.relative_to(netlist_dir)}")
        data = convert_netlist_to_data(netlist_path, add_centrality=args.add_centrality)
        data.y_func = torch.full((data.num_nodes,), label_id, dtype=torch.long)
        data.func_mask = torch.ones(data.num_nodes, dtype=torch.bool)

        # Unique name: ParentFolder_FileName.pt
        parent_name = netlist_path.parent.name
        file_stem = netlist_path.stem
        # Avoid redundant prefix if parent name is already in filename
        if parent_name.lower() in file_stem.lower():
             out_name = f"{file_stem}.pt"
        else:
             out_name = f"{parent_name}_{file_stem}.pt"
        
        out_path = out_dir / out_name
        torch.save(data, out_path)
        print(f"Saved: {out_path.name}")


if __name__ == "__main__":
    main()
