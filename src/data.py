import random
from pathlib import Path
from typing import List, Tuple

import torch
from torch_geometric.data import Data


def load_pt_files(path: Path) -> List[Path]:
    if path.is_file() and path.suffix == ".pt":
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Path not found: {path}")
    return sorted(path.glob("*.pt"))


def split_files(
    files: List[Path], seed: int = 42, train_ratio: float = 0.8, val_ratio: float = 0.1
) -> Tuple[List[Path], List[Path], List[Path]]:
    files = files[:]
    random.Random(seed).shuffle(files)
    n = len(files)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    train_files = files[:n_train]
    val_files = files[n_train : n_train + n_val]
    test_files = files[n_train + n_val :]
    return train_files, val_files, test_files


def _get_trojan_label(data: Data) -> torch.Tensor:
    if hasattr(data, "y_trojan"):
        return data.y_trojan
    if hasattr(data, "y"):
        return data.y
    raise ValueError("Missing trojan label (y_trojan or y).")


def _get_func_label(data: Data) -> torch.Tensor:
    if hasattr(data, "y_func"):
        return data.y_func
    return None


def _get_func_mask(data: Data) -> torch.Tensor:
    if hasattr(data, "func_mask"):
        return data.func_mask.bool()
    return None


def compute_class_weights(files: List[Path], num_func_classes: int):
    trojan_pos = 0
    trojan_neg = 0
    func_counts = torch.zeros(num_func_classes, dtype=torch.long)

    for path in files:
        data = torch.load(path)
        y_t = _get_trojan_label(data)
        trojan_pos += int((y_t == 1).sum())
        trojan_neg += int((y_t == 0).sum())

        y_f = _get_func_label(data)
        mask_f = _get_func_mask(data)
        if y_f is not None:
            if mask_f is None:
                mask_f = torch.ones_like(y_f, dtype=torch.bool)
            for c in range(num_func_classes):
                func_counts[c] += int(((y_f == c) & mask_f).sum())

    trojan_total = max(trojan_pos + trojan_neg, 1)
    trojan_w = torch.tensor(
        [trojan_total / max(trojan_neg, 1), trojan_total / max(trojan_pos, 1)],
        dtype=torch.float,
    )
    func_w = torch.ones(num_func_classes, dtype=torch.float)
    for i in range(num_func_classes):
        func_w[i] = float(func_counts.sum()) / float(max(func_counts[i], 1))

    return trojan_w, func_w
