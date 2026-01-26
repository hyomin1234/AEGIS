import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import os

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


def process_single_netlist(netlist_path, netlist_dir, out_dir, add_centrality, override_label):
    try:
        label_name = override_label or _resolve_label(netlist_path.stem, DEFAULT_KEYWORDS)
        label_id = _label_id(label_name)

        print(f"Processing: {netlist_path.relative_to(netlist_dir)}")
        data = convert_netlist_to_data(netlist_path, add_centrality=add_centrality)
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
        return f"Saved: {out_path.name}"
    except Exception as e:
        return f"Error processing {netlist_path.name}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Build labeled .pt dataset from netlist files")
    parser.add_argument("--netlist-dir", default="../raw_data/AES_modi", help="Directory with netlist files (default: ../raw_data)")
    parser.add_argument("--out-dir", default="../output", help="Output directory for .pt graphs (default: ../output)")
    parser.add_argument("--add-centrality", action="store_true", default=False, help="Append 4 centrality features")
    parser.add_argument("--label", help="Override label for all files (name or id)")
    parser.add_argument("--workers", type=int, default=os.cpu_count(), help="Number of parallel workers (default: all cores)")
    args = parser.parse_args()

    # Resolve paths relative to this script or current working directory
    base_dir = Path(__file__).resolve().parent
    netlist_dir = Path(args.netlist_dir)
    if not netlist_dir.is_absolute() and args.netlist_dir == "../raw_data":
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
    print(f"Using {args.workers} parallel workers")

    # Use rglob for recursive search
    files = sorted(netlist_dir.rglob("*.v"))
    if not files:
        files = sorted(netlist_dir.glob("*.v"))
        
    if not files:
        raise FileNotFoundError(f"No netlist files found in {netlist_dir}")

    # Use ProcessPoolExecutor for parallel processing
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                process_single_netlist, 
                f, netlist_dir, out_dir, args.add_centrality, args.label
            ): f for f in files
        }
        
        for future in as_completed(futures):
            result = future.result()
            print(result)


if __name__ == "__main__":
    main()
