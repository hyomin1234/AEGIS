from pathlib import Path
import sys

# Add src to path
sys.path.append(r"c:\Users\hyomin\Desktop\학연생_논문분석\hardware torjan\AEGIS\src")

from standalone_parser import _split_modules, _parse_module_block, parse_netlist

# Target File
file_path = Path(r"c:\Users\hyomin\Desktop\학연생_논문분석\hardware torjan\AEGIS\raw_data\AES\AES_T1500_TjIn\AES_T1500_TjIn_util0.7_clk2.0\top.netlist.v")

print(f"Checking file: {file_path}")
text = file_path.read_text(encoding="utf-8", errors="ignore")

# 1. Check Module Split
blocks = _split_modules(text)
print(f"Found {len(blocks)} raw blocks.")
for i, b in enumerate(blocks):
    print(f"Block {i} start: {b[:50]}...")

# 2. Check Parsed Modules
modules = {}
for b in blocks:
    m = _parse_module_block(b)
    if m:
        modules[m.name] = m
        print(f"Parsed Module: {m.name} (Instances: {len(m.instances)}, Assigns: {len(m.assigns)})")

# 3. Check for TSC/Trojan
print("\nScanning for Trojan-like modules...")
for name in modules:
    if "TSC" in name or "Trojan" in name:
        print(f"-> Found suspicious module: {name}")

# 4. Check Top Module Dependencies
top_name = list(modules.keys())[-1]
print(f"\nTop Module assumed: {top_name}")
top_mod = modules[top_name]

print("Top Module Instances types:")
instance_types = set(inst['cell_type'] for inst in top_mod.instances)
print(instance_types)

for t in instance_types:
    if t in modules:
        print(f"-> {t} is in modules (Will be flattened)")
    else:
        print(f"-> {t} is NOT in modules (Leaf gate)")

# 5. Full Parse Test
print("\nRunning full parse_netlist...")
g, node_dict = parse_netlist(file_path)
print(f"Graph Nodes: {g.number_of_nodes()}")
trojan_nodes = [n for n in g.nodes() if "trojan" in n.lower()]
print(f"Nodes with 'trojan' in name: {len(trojan_nodes)}")
print(f"Sample names: {trojan_nodes[:5]}")
