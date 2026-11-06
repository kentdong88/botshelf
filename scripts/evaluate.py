import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from botshelf.catalog import ROOT, load_catalog, load_needs
from botshelf.engine import Engine
from botshelf.evaluation import evaluate_pairs, html_report, review_fingerprint, revision_fingerprint, experiment_products
from botshelf.catalog import Retriever
from botshelf.storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "live"], default="offline")
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--allow-unreviewed", action="store_true")
    args = parser.parse_args()
    store = Store(ROOT / "data/botshelf.sqlite")
    reviewed = {e["scope"] for e in store.events("case_review") if e["payload"].get("approved")}
    needs = [n for n in load_needs() if n.split == args.split]
    products = load_catalog()
    lookup = {p.product_id:p for p in products}
    for need in needs:
        # Reviews bind to exact case JSON, not just a reusable ID.
        digest = review_fingerprint(need, lookup[need.target_id])
        need.reviewed = digest in reviewed
    if not args.allow_unreviewed and not all(n.reviewed for n in needs):
        parser.error("Cases need human review in the app, or --allow-unreviewed for exploratory runs.")
    if not args.allow_unreviewed:
        approvals = {e["scope"] for e in store.events("revision_review")}
        retriever = Retriever(products)
        for need in needs:
            target = lookup[need.target_id]
            for experiment in ("A", "B"):
                _, _, changes = experiment_products(retriever.search(need.text), target, need, experiment)
                if changes and revision_fingerprint(need, target, experiment, changes) not in approvals:
                    parser.error("Review generated revisions for both experiments, or use --allow-unreviewed.")
    engine = Engine(args.mode)
    result = evaluate_pairs(products, needs, engine, store)
    prefix = ROOT / "outputs" / f"{args.mode}_{args.split}"
    prefix.parent.mkdir(exist_ok=True)
    prefix.with_suffix(".json").write_text(json.dumps(result, indent=2))
    prefix.with_suffix(".html").write_text(html_report(result))
    pd.DataFrame(result["rows"]).to_csv(prefix.with_suffix(".csv"), index=False)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
