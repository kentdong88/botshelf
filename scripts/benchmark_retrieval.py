"""Independent source-query benchmark. Labels never enter a shopping-model payload."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from botshelf.catalog import ROOT, Retriever, load_catalog


def main():
    products = load_catalog()
    ids = {p.product_id for p in products}
    labels = pd.read_csv(ROOT / "data/raw/label.csv", sep="\t", dtype=str)
    labels = labels[labels.product_id.isin(ids)]
    queries = pd.read_csv(ROOT / "data/raw/query.csv", sep="\t", dtype=str)
    retriever = Retriever(products)
    rows = []
    for query in queries.itertuples():
        subset = labels[labels.query_id == query.query_id]
        gains = {r.product_id: {"Exact": 2, "Partial": 1, "Irrelevant": 0}[r.label] for r in subset.itertuples()}
        positive = {pid for pid, gain in gains.items() if gain > 0}
        if not positive: continue
        found = [p.product_id for p in retriever.search(query.query)]
        ideal = sum((2**gain-1)/math.log2(i+2) for i, gain in enumerate(sorted(gains.values(), reverse=True)[:15]))
        actual = sum((2**gains.get(pid,0)-1)/math.log2(i+2) for i, pid in enumerate(found))
        rows.append({"query_id": query.query_id, "query": query.query, "ndcg_at_15": actual/ideal,
                     "positive_recall_at_15": len(positive & set(found))/len(positive),
                     "judged_fraction": sum(pid in gains for pid in found)/len(found) if found else 0})
    summary = {"scope": "200-product subset; original WANDS queries only; unjudged products treated as zero gain",
        "query_count": len(rows), "metrics": {k: sum(r[k] for r in rows)/len(rows) if rows else None
            for k in ("ndcg_at_15", "positive_recall_at_15", "judged_fraction")}, "rows": rows}
    (ROOT / "outputs/retrieval_benchmark.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
