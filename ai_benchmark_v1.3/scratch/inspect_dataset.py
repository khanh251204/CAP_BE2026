import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR.parent))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_benchmark.evaluation.normalization import remove_accents

df = pd.read_csv(ROOT_DIR / "datasets" / "voicecash_producer_1000.csv")

with open(ROOT_DIR / "scratch" / "dataset_summary.txt", "w", encoding="utf-8") as f:
    for _, r in df.iterrows():
        f.write(f"ID {r['id']:3d}: [{r['intent']}] {r['text']}\n")

print("Dataset summary written to scratch/dataset_summary.txt")
