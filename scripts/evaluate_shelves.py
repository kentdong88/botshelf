"""Run original versus extractive rewrite for all six real shelves. No fake merchant facts."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from botshelf.catalog import ROOT
from botshelf.shelf_models import Shelf, Listing
from botshelf.shelf_engine import ShelfEngine, run_shelf, rewrite_listing, compare_shelves
from botshelf.evaluation import html_report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["offline","codex"],default="offline")
    parser.add_argument("--model",default=None)
    parser.add_argument("--repeats",type=int,default=3)
    args=parser.parse_args()
    engine=ShelfEngine(args.mode,args.model)
    shelves=[Shelf.model_validate(s) for s in json.loads((ROOT/"data/esci/processed/shelves.json").read_text())]
    results=[]; summary=[]; paired_rows=[]
    for shelf in shelves:
        target=shelf.products[0]
        before=run_shelf(shelf,target.product_id,engine,repeats=args.repeats)
        draft=rewrite_listing(target,shelf.query,shelf.category,engine)
        result={"shelf_id":shelf.shelf_id,"category":shelf.category,"before":before,"rewrite":draft}
        if draft["status"]=="ok":
            after=run_shelf(shelf,target.product_id,engine,Listing.model_validate(draft["listing"]),args.repeats)
            comparison=compare_shelves(before,after)
            result.update(after=after,comparison=comparison)
            summary.append({"category":shelf.category,"target_id":target.product_id,
                "before_selection":before["metrics"]["selection_rate"],"after_selection":after["metrics"]["selection_rate"],
                "paired_delta":comparison["selection_delta"],"paired_trials":comparison["paired_trials"],
                "failed_pairs":comparison["excluded_failed_pairs"],"equal_share_reference":1/len(shelf.products)})
            paired_rows.extend({"category":shelf.category,**r} for r in comparison["rows"])
        else: summary.append({"category":shelf.category,"target_id":target.product_id,"rewrite_status":"failed"})
        results.append(result)
        print(shelf.category,summary[-1],flush=True)
    report={"manifest":{"mode":args.mode,"config":engine.config,"selection":"first ASIN per shelf; no outcome-based target selection",
        "review_status":"Exploratory: generated rewrite proposals, not human-approved listing changes",
        "stages":"original and rewritten only; no merchant facts fabricated", "limitations":"Offline is a scoring demonstration, not real-agent choice or sales lift."},
        "summary":summary,"rows":paired_rows,"details":results}
    output=ROOT/"outputs"; output.mkdir(exist_ok=True)
    prefix=output/("amazon_"+args.mode)
    prefix.with_suffix(".json").write_text(json.dumps(report,indent=2))
    prefix.with_suffix(".html").write_text(html_report(report))
    pd.DataFrame(paired_rows).to_csv(prefix.with_suffix(".csv"),index=False)


if __name__=="__main__": main()
