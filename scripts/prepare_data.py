"""Build a deterministic subset and draft cases; human review remains explicit."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from botshelf.catalog import ROOT, Retriever
from botshelf.evidence import facts
from botshelf.models import Constraint, Need, Product


def main():
    raw = ROOT / "data/raw/product.csv"
    frame = pd.read_csv(raw, sep="\t", keep_default_na=False)
    if frame.product_id.duplicated().any():
        raise ValueError("Duplicate source IDs")
    category = "Dining Tables"
    if (frame.product_class == category).sum() < 50:
        category = frame[frame.product_class.str.contains("Tables", case=False)].product_class.value_counts().index[0]
    selected = frame[frame.product_class == category].sort_values("product_id").head(200)
    products = [Product(product_id=str(row.product_id), name=row.product_name, category=row.product_class,
        description=row.product_description, features=row.product_features,
        source="https://github.com/wayfair/WANDS/blob/main/dataset/product.csv#product_id="+str(row.product_id))
        for row in selected.itertuples()]
    retriever = Retriever(products)
    needs = []
    # Cases use only explicit, consistent facts. No human-reviewed flag is fabricated.
    for product in products:
        extracted = facts(product)
        available = {k: v for k, v in extracted.items() if v and len(set(f.value for f in v)) == 1 and k != "width_cm"}
        if "top_material" not in available or "shape" not in available:
            continue
        constraints = [Constraint(attribute=k, value=available[k][0].value) for k in ("top_material", "shape")]
        text = f"Dining table with {constraints[0].value} top and {constraints[1].value} shape."
        if "seats" in available:
            constraints.append(Constraint(attribute="seats", operator="gte", value=available["seats"][0].value))
            text += f" Seats at least {constraints[-1].value}."
        # Do not force target recall; preserve both recalled and not-recalled cases.
        needs.append(Need(need_id=f"need-{len(needs)+1:02}", text=text, constraints=constraints,
            target_id=product.product_id, split="dev" if len(needs)<10 else "test",
            truth_evidence=[available[c.attribute][0].evidence for c in constraints]))
        if len(needs) == 40:
            break
    output = ROOT / "data/processed"
    output.mkdir(parents=True, exist_ok=True)
    for filename, data in (("catalog.json", [p.model_dump() for p in products]), ("needs.json", [n.model_dump() for n in needs])):
        (output / filename).write_text(json.dumps(data, indent=2))
    manifest = {"source": "https://github.com/wayfair/WANDS", "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "raw_sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "category": category,
        "product_count": len(products), "need_count": len(needs), "review_status": "draft; human review required",
        "selection": "First 200 source product IDs in category; first 40 with consistent material and shape",
        "units_policy": "No implicit units; no width inference from unlabeled title dimensions",
        "license_file": "data/raw/WANDS_LICENSE"}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    queries = pd.read_csv(ROOT / "data/raw/query.csv", sep="\t", keep_default_na=False)
    queries[queries['query'].str.contains('dining|table', case=False)].to_csv(output / "source_queries.csv", index=False)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
