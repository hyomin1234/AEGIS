import argparse
from pathlib import Path

import torch
from torch_geometric.loader import DataLoader

from config import (
    DEFAULT_ALPHA,
    DEFAULT_BATCH,
    DEFAULT_EPOCHS,
    DEFAULT_FUNC_CLASSES,
    DEFAULT_HIDDEN,
    DEFAULT_LAYERS,
)
from data import compute_class_weights, load_pt_files, split_files
from model import MultiTaskGNN
from utils import binary_f1, masked_accuracy

# [수정 제안] 메모리 안전한 로딩 방식
from torch_geometric.data import Dataset

class FileDataset(Dataset):
    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
    def len(self):
        return len(self.file_paths)
    def get(self, idx):
        return torch.load(self.file_paths[idx])



def _get_labels(data):
    y_t = getattr(data, "y_trojan", getattr(data, "y", None))
    if y_t is None:
        raise ValueError("Missing trojan label (y_trojan or y).")
    y_f = getattr(data, "y_func", None)
    mask_f = getattr(data, "func_mask", None)
    if mask_f is not None:
        mask_f = mask_f.bool()
    return y_t, y_f, mask_f


def train_one_epoch(model, loader, optimizer, crit_t, crit_f, alpha, device):
    model.train()
    total_loss = 0.0
    for data in loader:
        data = data.to(device)
        y_t, y_f, mask_f = _get_labels(data)
        optimizer.zero_grad()
        trojan_logits, func_logits = model(data)
        loss_t = crit_t(trojan_logits, y_t)
        loss = loss_t
        if y_f is not None:
            if mask_f is None:
                mask_f = torch.ones_like(y_f, dtype=torch.bool)
            if mask_f.any():
                loss_f = crit_f(func_logits[mask_f], y_f[mask_f])
                loss = loss + alpha * loss_f
        loss.backward()
        optimizer.step()
        total_loss += float(loss.item())
    return total_loss / max(len(loader), 1)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    all_pred = []
    all_tgt = []
    func_acc = []
    for data in loader:
        data = data.to(device)
        y_t, y_f, mask_f = _get_labels(data)
        trojan_logits, func_logits = model(data)
        pred_t = trojan_logits.argmax(dim=1)
        all_pred.append(pred_t.cpu())
        all_tgt.append(y_t.cpu())
        if y_f is not None:
            acc = masked_accuracy(func_logits.cpu(), y_f.cpu(), mask_f.cpu() if mask_f is not None else None)
            func_acc.append(acc)
    pred = torch.cat(all_pred) if all_pred else torch.tensor([])
    tgt = torch.cat(all_tgt) if all_tgt else torch.tensor([])
    precision, recall, f1 = binary_f1(pred, tgt)
    func_acc_val = sum(func_acc) / max(len(func_acc), 1)
    return precision, recall, f1, func_acc_val


def main():
    parser = argparse.ArgumentParser(description="AEGIS Multi-Task GNN training")
    parser.add_argument("--data-dir", required=True, help="Directory with .pt graphs")
    parser.add_argument("--epochs", type=int, default=DEFAULT_EPOCHS)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--hidden", type=int, default=DEFAULT_HIDDEN)
    parser.add_argument("--layers", type=int, default=DEFAULT_LAYERS)
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--model", choices=["sage", "gin"], default="sage")
    parser.add_argument("--func-classes", type=int, default=DEFAULT_FUNC_CLASSES)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-class-weights", action="store_true")
    parser.add_argument("--save", default="aegis_gnn.pt")
    parser.add_argument("--load-checkpoint", type=str, default=None, help="Path to pre-trained model checkpoint")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    files = load_pt_files(data_dir)
    if not files:
        raise FileNotFoundError(f"No .pt files found in {data_dir}")

    train_files, val_files, test_files = split_files(files, seed=args.seed)
    train_loader = DataLoader(FileDataset(train_files), batch_size=args.batch_size, shuffle=True, num_workers=4) # num_workers로 속도 업
    val_loader = DataLoader(FileDataset(val_files), batch_size=args.batch_size, num_workers=4)
    test_loader = DataLoader(FileDataset(test_files), batch_size=args.batch_size, num_workers=4)
    sample = torch.load(train_files[0])
    in_dim = sample.x.size(1)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MultiTaskGNN(
        in_dim=in_dim,
        hidden_dim=args.hidden,
        num_layers=args.layers,
        num_func_classes=args.func_classes,
        backbone=args.model,
    ).to(device)

    if args.load_checkpoint:
        print(f"Loading checkpoint from {args.load_checkpoint}...")
        ckpt = torch.load(args.load_checkpoint, map_location=device)
        model.load_state_dict(ckpt["model_state"])
        print("Checkpoint loaded successfully.")

    if args.no_class_weights:
        trojan_w = None
        func_w = None
    else:
        trojan_w, func_w = compute_class_weights(train_files, args.func_classes)
        trojan_w = trojan_w.to(device)
        func_w = func_w.to(device)

    crit_t = torch.nn.CrossEntropyLoss(weight=trojan_w)
    crit_f = torch.nn.CrossEntropyLoss(weight=func_w) if func_w is not None else torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    for epoch in range(1, args.epochs + 1):
        loss = train_one_epoch(model, train_loader, optimizer, crit_t, crit_f, args.alpha, device)
        p, r, f1, f_acc = evaluate(model, val_loader, device)
        print(f"Epoch {epoch:03d} loss={loss:.4f} trojan_f1={f1:.4f} func_acc={f_acc:.4f}")

    p, r, f1, f_acc = evaluate(model, test_loader, device)
    print(f"Test trojan_f1={f1:.4f} func_acc={f_acc:.4f}")

    save_path = Path(args.save).resolve()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state": model.state_dict(),
            "in_dim": in_dim,
            "hidden": args.hidden,
            "layers": args.layers,
            "func_classes": args.func_classes,
            "model": args.model,
        },
        save_path,
    )
    print(f"Saved: {save_path}")


if __name__ == "__main__":
    main()
