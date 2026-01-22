import argparse
import json
from pathlib import Path

import torch
from torch_geometric.data import Data

from config import FUNC_LABELS
from model import MultiTaskGNN


@torch.no_grad()
def main():
    parser = argparse.ArgumentParser(description="AEGIS inference")
    parser.add_argument("--data", required=True, help="Input .pt file")
    parser.add_argument("--ckpt", required=True, help="Model checkpoint")
    parser.add_argument("--out", required=True, help="Output JSON")
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    data_path = Path(args.data).resolve()
    ckpt_path = Path(args.ckpt).resolve()
    out_path = Path(args.out).resolve()

    data: Data = torch.load(data_path)
    ckpt = torch.load(ckpt_path, map_location="cpu")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if args.device == "cpu":
        device = torch.device("cpu")

    model = MultiTaskGNN(
        in_dim=ckpt["in_dim"],
        hidden_dim=ckpt["hidden"],
        num_layers=ckpt["layers"],
        num_func_classes=ckpt["func_classes"],
        backbone=ckpt["model"],
    ).to(device)
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    data = data.to(device)
    trojan_logits, func_logits = model(data)
    trojan_prob = torch.softmax(trojan_logits, dim=1)[:, 1].cpu().tolist()
    func_pred = torch.softmax(func_logits, dim=1).argmax(dim=1).cpu().tolist()

    node_names = getattr(data, "node_names", [str(i) for i in range(data.num_nodes)])
    result = []
    for i, name in enumerate(node_names):
        func_id = int(func_pred[i])
        func_name = FUNC_LABELS[func_id] if func_id < len(FUNC_LABELS) else "Unknown"
        result.append(
            {
                "node_idx": i,
                "node_name": name,
                "trojan_prob": float(trojan_prob[i]),
                "func_id": func_id,
                "func_name": func_name,
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
