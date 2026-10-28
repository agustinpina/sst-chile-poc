"""Step 1 - Run Scopus query variants: report hit counts and a random sample of titles.

Usage:
    export ELSEVIER_API_KEY=...            # required
    export ELSEVIER_INST_TOKEN=...         # optional (off-campus institutional access)
    python scripts/01_search.py                 # counts only (does not consume the download quota)
    python scripts/01_search.py --sample q1_broad --n 20   # download STANDARD view + sample titles
"""
import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from pybliometrics.scopus import ScopusSearch, init

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "queries"
OUT = ROOT / "outputs" / "tables"
SEED = 42


def read_query(name: str) -> str:
    return (QUERIES / f"{name}.txt").read_text(encoding="utf-8").strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", help="query name (without .txt) to download and sample")
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()

    key = os.environ.get("ELSEVIER_API_KEY")
    if not key:
        sys.exit("ELSEVIER_API_KEY is not set")
    token = os.environ.get("ELSEVIER_INST_TOKEN")
    init(keys=[key], inst_tokens=[token] if token else None)

    names = sorted(p.stem for p in QUERIES.glob("q*.txt"))
    rows = []
    for name in names:
        size = ScopusSearch(read_query(name), download=False).get_results_size()
        rows.append({"query": name, "n_results": size})
        print(f"{name}: {size}")
    OUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT / "query_counts.csv", index=False)

    if args.sample:
        res = ScopusSearch(read_query(args.sample), view="STANDARD", download=True)
        df = pd.DataFrame(res.results)
        sample = df.sample(min(args.n, len(df)), random_state=SEED)
        cols = [c for c in ("coverDate", "title", "publicationName", "doi") if c in sample]
        sample[cols].to_csv(OUT / f"sample_{args.sample}.csv", index=False)
        for _, r in sample.iterrows():
            print(f"- ({str(r.get('coverDate'))[:4]}) {r.get('title')} [{r.get('publicationName')}]")


if __name__ == "__main__":
    main()
