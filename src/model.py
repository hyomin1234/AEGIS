import torch
import torch.nn.functional as F
from torch_geometric.nn import GINConv, SAGEConv


class MultiTaskGNN(torch.nn.Module):
    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        num_layers: int,
        num_func_classes: int,
        backbone: str = "sage",
    ):
        super().__init__()
        if num_layers < 2:
            raise ValueError("num_layers must be >= 2")

        self.backbone = backbone
        self.convs = torch.nn.ModuleList()

        if backbone == "gin":
            self.convs.append(
                GINConv(torch.nn.Sequential(torch.nn.Linear(in_dim, hidden_dim), torch.nn.ReLU()))
            )
            for _ in range(num_layers - 1):
                self.convs.append(
                    GINConv(torch.nn.Sequential(torch.nn.Linear(hidden_dim, hidden_dim), torch.nn.ReLU()))
                )
        else:
            self.convs.append(SAGEConv(in_dim, hidden_dim))
            for _ in range(num_layers - 1):
                self.convs.append(SAGEConv(hidden_dim, hidden_dim))

        self.head_trojan = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim // 2),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim // 2, 2),
        )
        self.head_func = torch.nn.Sequential(
            torch.nn.Linear(hidden_dim, hidden_dim // 2),
            torch.nn.ReLU(),
            torch.nn.Linear(hidden_dim // 2, num_func_classes),
        )

    def forward(self, data):
        x, edge_index = data.x, data.edge_index
        for conv in self.convs:
            x = conv(x, edge_index)
            x = F.relu(x)
        trojan_logits = self.head_trojan(x)
        func_logits = self.head_func(x)
        return trojan_logits, func_logits
