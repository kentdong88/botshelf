"""Reproducible real-query shelves and observational relevance analysis."""
import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import duckdb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler
from botshelf.catalog import ROOT
from botshelf.shelf_models import Listing, Shelf, BuyerScenario
from botshelf.shelf_audit import clean_text, tokens, SPEC, FLUFF

CATEGORIES = {
    "Air purifiers": ["air purifier", "air purifiers for home"],
    "Baby sound machines": ["white noise machine for baby", "best white noise machine for baby", "portable white noise machine baby"],
    "Baby carriers": ["baby carrier", "baby carrier front and back"],
    "Bark collars": ["bark collar", "bark collars"],
    "1TB SSDs": ["1tb ssd"], "Backpacks": ["backpack", "backpacks"],
}


def as_listing(row):
    raw=clean_text(row.product_bullet_point)
    bullets=[b.strip(" •\t") for b in re.split(r"\n+|[•●]",raw) if b.strip()]
    return Listing(product_id=str(row.product_id),title=clean_text(row.product_title),
        bullets=bullets,description=clean_text(row.product_description),brand=clean_text(row.product_brand),color=clean_text(row.product_color))


def features(query,p):
    text=" ".join([p.title,*p.bullets,p.description,p.brand,p.color])
    words=set(tokens(query)); overlap=len(words&set(tokens(text)))/len(words) if words else 0
    fluff=sum(len(term.split())*text.lower().count(term) for term in FLUFF)/max(1,len(text.split()))
    generic=[r"dimensions|\bcm\b|\binches\b",r"weight|\blbs?\b|\bkg\b",r"material|cotton|nylon|steel|wood",r"compatible|compatibility",r"warranty|guarantee",r"certified|certification",r"included|package|in the box"]
    return {"query_coverage":overlap,"numeric_specs":len(SPEC.findall(text)),
        "attribute_mentions":sum(bool(re.search(x,text,re.I)) for x in generic),
        "structure":(bool(p.title)+min(len(p.bullets)/5,1)+bool(p.description))/3,
        "fluff_ratio":fluff,"log_word_count":math.log1p(len(text.split()))}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--sample-size",type=int,default=40000); args=parser.parse_args()
    raw=ROOT/"data/esci/raw"; out=ROOT/"data/esci/processed"; out.mkdir(parents=True,exist_ok=True)
    examples=pd.read_parquet(raw/"examples.parquet")
    us=examples[examples.product_locale=="us"].copy()
    # Exclude conflicting labels; collapse repeated source pairs without favoring Exact.
    conflicts=us.groupby(["query_id","product_id"]).esci_label.nunique()
    bad=set(conflicts[conflicts>1].index)
    us=us[~pd.MultiIndex.from_frame(us[["query_id","product_id"]]).isin(bad)].drop_duplicates(["query_id","product_id"])
    plans=[]; selected_ids=set()
    for category,preferred in CATEGORIES.items():
        eligible=us[us.esci_label.isin(["E","S"])]
        chosen=None
        for text in preferred:
            candidates=eligible[eligible['query'].str.casefold()==text.casefold()]
            counts=candidates.groupby("query_id").product_id.nunique()
            enough=counts[counts>=8]
            if len(enough):
                qid=int(enough.index.min()); rows=candidates[candidates.query_id==qid].sort_values("product_id").head(8)
                chosen=(qid,str(rows.iloc[0]['query']),rows); break
        if chosen is None: continue
        qid,query,rows=chosen
        ids=rows.product_id.tolist(); selected_ids.update(ids)
        plans.append((category,qid,query,ids,rows))
    sample=us.sample(n=min(args.sample_size,len(us)),random_state=20261106).sort_values("example_id")
    selected_ids.update(sample.product_id.tolist())
    wanted=pd.DataFrame({"product_id":sorted(selected_ids)})
    con=duckdb.connect(); con.execute("SET threads=2"); con.execute("SET memory_limit='1GB'")
    con.register("wanted",wanted)
    catalog=con.execute("SELECT p.* FROM read_parquet(?) p JOIN wanted w USING(product_id) WHERE p.product_locale='us'",[str(raw/"products.parquet")]).df().fillna("")
    listings={str(r.product_id):as_listing(r) for r in catalog.itertuples()}
    shelves=[]; provenance=[]
    for category,qid,query,ids,rows in plans:
        if any(pid not in listings or not listings[pid].title for pid in ids):
            raise ValueError("Shelf contains absent source product")
        shared=us[us.product_id.isin(ids)&us.esci_label.isin(["E","S"])]
        counts=shared.groupby(["query_id","query"]).product_id.nunique().reset_index(name="shared")
        # Related source queries have at least two shelf products labelled E/S.
        related=counts[(counts.shared>=2)&(counts.query_id!=qid)].sort_values(["shared","query_id"],ascending=[False,True]).head(4)
        scenarios=[BuyerScenario(scenario_id=f"esci-{qid}",text=query,source_query_id=str(qid))]
        scenarios += [BuyerScenario(scenario_id=f"esci-{int(r.query_id)}",text=r.query,source_query_id=str(r.query_id)) for r in related.itertuples()]
        shelf=Shelf(shelf_id=f"us-{qid}",category=category,query_id=str(qid),query=query,
            products=[listings[pid] for pid in ids],scenarios=scenarios,
            selection_note="8 distinct historical US products under the SAME real query; E/S relevance filter, then ascending ASIN. Related scenarios share >=2 E/S shelf products. Labels are excluded from agent inputs.")
        shelves.append(shelf.model_dump())
        provenance.extend({"shelf_id":shelf.shelf_id,"query_id":str(qid),"product_id":str(r.product_id),"esci_label":r.esci_label,"example_id":str(r.example_id)} for r in rows.itertuples())
    (out/"shelves.json").write_text(json.dumps(shelves,indent=2))
    pd.DataFrame(provenance).to_csv(out/"shelf_provenance.csv",index=False)
    print("Built",len(shelves),"shelves; extracting sample features",flush=True)
    records=[]
    for row in sample.itertuples():
        if row.product_id not in listings: continue
        record=features(row.query,listings[row.product_id])
        record.update(example_id=str(row.example_id),query_id=str(row.query_id),product_id=row.product_id,
                      label=row.esci_label,exact=int(row.esci_label=="E"))
        records.append(record)
    f=pd.DataFrame(records); f.to_csv(out/"analysis_features.csv",index=False)
    cols=["query_coverage","numeric_specs","attribute_mentions","structure","fluff_ratio","log_word_count"]
    train,test=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=20261106).split(f,groups=f.query_id))
    scaler=StandardScaler().fit(f.iloc[train][cols]); model=LogisticRegression(max_iter=1000,solver="liblinear",random_state=20261106)
    model.fit(scaler.transform(f.iloc[train][cols]),f.iloc[train].exact)
    from scipy.special import expit
    # Elementwise dot avoids a macOS Accelerate matmul floating-status warning.
    x_test=scaler.transform(f.iloc[test][cols])
    probabilities=expit((x_test*model.coef_[0]).sum(axis=1)+model.intercept_[0])
    if not np.isfinite(probabilities).all() or not np.isfinite(model.coef_).all():
        raise ValueError("Non-finite regression output")
    buckets=pd.cut(f.query_coverage,[-.000001,.25,.5,.75,1],labels=["0–25%","25–50%","50–75%","75–100%"])
    bins=[]
    for label in buckets.cat.categories:
        group=f[buckets==label]; bins.append({"coverage_bin":label,"pairs":len(group),"exact_rate":float(group.exact.mean()) if len(group) else None})
    analysis={"sample_pairs":len(f),"train_pairs":len(train),"test_pairs":len(test),"unique_queries":int(f.query_id.nunique()),
        "sampling":"Fixed random sample of distinct non-conflicting US query-product pairs; seed 20261106",
        "query_disjoint":not bool(set(f.iloc[train].query_id)&set(f.iloc[test].query_id)),
        "heldout_auc":float(roc_auc_score(f.iloc[test].exact,probabilities)),"heldout_accuracy":float(accuracy_score(f.iloc[test].exact,probabilities>=.5)),
        "heldout_log_loss":float(log_loss(f.iloc[test].exact,probabilities)),"majority_baseline_accuracy":float(max(f.iloc[test].exact.mean(),1-f.iloc[test].exact.mean())),
        "coverage_bins":bins,"coefficients":[{"feature":name,"standardized_log_odds":float(coef),"odds_ratio_per_sd":float(np.exp(coef))} for name,coef in zip(cols,model.coef_[0])],
        "interpretation":"Observational association with ESCI Exact relevance, not causal effects or shopping-agent preference. Correlated features and query mix can confound coefficients. No significance test is claimed.",
        "split_note":"Query-disjoint holdout; products may recur across queries. No agent outcome labels exist in this dataset.",
        "feature_definitions":{"query_coverage":"unique non-stop query tokens present / unique non-stop query tokens", "numeric_specs":"number+unit regex matches","attribute_mentions":"7 generic keyword-group mentions, not verified completeness","structure":"title presence + min(bullets/5,1) + description presence, divided by 3","fluff_ratio":"fixed promotional phrase tokens / all whitespace tokens","log_word_count":"log(1 + whitespace word count)"}}
    (out/"analysis.json").write_text(json.dumps(analysis,indent=2))
    manifest={"source":"https://github.com/amazon-science/esci-data","built_utc":datetime.now(timezone.utc).isoformat(),
        "source_rows":len(examples),"us_distinct_pairs":len(us),"conflicting_pairs_excluded":len(bad),
        "shelf_count":len(shelves),"sample_pairs":len(f),"missing_catalog_pairs":len(sample)-len(f),
        "historical_data":True,"price_and_inventory":"not provided", "modifications":"US subset, cleaned HTML, split bullets, 8-product shelves, computed features and labels separated from product payloads.",
        "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw/"examples.parquet",raw/"products.parquet")}}
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps({k:v for k,v in analysis.items() if k not in ('feature_definitions','coefficients')},indent=2))


if __name__=="__main__": main()
