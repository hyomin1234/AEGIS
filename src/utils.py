import torch


def binary_f1(pred: torch.Tensor, target: torch.Tensor):
    pred = pred.view(-1)
    target = target.view(-1)
    tp = int(((pred == 1) & (target == 1)).sum())
    fp = int(((pred == 1) & (target == 0)).sum())
    fn = int(((pred == 0) & (target == 1)).sum())
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    return precision, recall, f1


def masked_accuracy(logits: torch.Tensor, target: torch.Tensor, mask: torch.Tensor):
    if mask is None:
        mask = torch.ones_like(target, dtype=torch.bool)
    pred = logits.argmax(dim=1)
    correct = ((pred == target) & mask).sum().item()
    total = mask.sum().item()
    return correct / max(total, 1)
