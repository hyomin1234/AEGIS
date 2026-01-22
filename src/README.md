AEGIS (NetTAG-Free) Quickstart

1) Convert netlist to PyG data
   python AEGIS/netlist_to_pyg.py --netlist path/to/design.v --out AEGIS/data/design.pt --add-centrality

1b) (Optional) Attach function labels
   python AEGIS/label_nodes.py --pt AEGIS/data/design.pt --func-label 2
   python AEGIS/label_nodes.py --pt AEGIS/data/design.pt --func-label 1 --nodes path/to/trigger_nodes.txt

1c) (Optional) Auto-label by filename (dataset build)
   python AEGIS/dataset_builder.py --netlist-dir path/to/netlists --out-dir AEGIS/data --add-centrality

2) Train the multi-task GNN
   python AEGIS/train.py --data-dir AEGIS/data --epochs 50 --func-classes 7 --save AEGIS/checkpoints/aegis_gnn.pt

3) Run inference
   python AEGIS/infer.py --data AEGIS/data/design.pt --ckpt AEGIS/checkpoints/aegis_gnn.pt --out AEGIS/out/preds.json

4) Build LLM prompt text (bridge)
   Use AEGIS/bridge.py build_prompt(data, predictions)

5) Generate ECO script template
   Use AEGIS/bridge.py build_actions(data, predictions) + AEGIS/eco.py generate_tcl(actions, output_path)
