"""Merchant-facing four-step Amazon shelf workspace."""
import json
import os
from collections import Counter
from pathlib import Path
import pandas as pd
import streamlit as st
from .catalog import ROOT
from .evaluation import html_report
from .shelf_models import Shelf, Listing, BuyerScenario
from .shelf_audit import SLOTS, audit_listing, source_blocks
from .shelf_engine import ShelfEngine, digest, run_shelf, rewrite_listing, compare_shelves, add_merchant_fact
from .storage import Store
from .shelf_report import shelf_report


@st.cache_data
def load_shelves():
    return [Shelf.model_validate(s) for s in json.loads((ROOT/"data/esci/processed/shelves.json").read_text())]


def percent(value): return "—" if value is None else f"{value:.1%}"


def ranking_rows(batch, target_id):
    rows=[]
    for trial in batch["trials"]:
        if trial["status"]!="ok":
            rows.append({"Scenario":trial["scenario"],"Repeat":trial["repeat"]+1,"Status":"failed","Reason":trial["error"]}); continue
        for rank,item in enumerate(trial["result"]["ranking"],1):
            rows.append({"Scenario":trial["scenario"],"Repeat":trial["repeat"]+1,"ASIN":item["product_id"],
                "Your SKU":item["product_id"]==target_id,"Rank":rank,"Selected":trial["result"]["selected_id"]==item["product_id"],
                "Suitability":item["suitability"],"Reason":item["reason"],"Missing information":"; ".join(item["missing_information"]),
                "Evidence IDs":", ".join(item["evidence_ids"]),"Status":"ok"})
    return rows


def show_results(batch, target_id, prefix):
    m=batch["metrics"]
    columns=st.columns(4)
    columns[0].metric("Selected",percent(m["selection_rate"]))
    columns[1].metric("Top 3",percent(m["top3_rate"]))
    columns[2].metric("Average rank","—" if m["average_rank"] is None else f"{m['average_rank']:.2f}")
    columns[3].metric("Valid / attempted",f"{m['successful_trials']} / {m['attempted_trials']}")
    st.caption(f"Equal-share reference: {m['equal_share_reference']:.1%} · Abstentions: {m['abstentions']} · Failures: {m['failed_trials']} · API calls: {m['api_calls']} · {batch['elapsed_s']:.2f}s")
    st.caption("The equal-share line is a neutral 1/N reference, not an entitlement or a prediction. Top-3 and mean rank include all ranked items, including unsuitable ones.")
    records=ranking_rows(batch,target_id)
    selected=[r for r in records if r.get("Your SKU")]
    st.dataframe(pd.DataFrame(selected),hide_index=True,width="stretch")
    gaps=Counter(g for t in batch["trials"] if t["status"]=="ok" for r in t["result"]["ranking"] if r["product_id"]==target_id for g in r["missing_information"])
    if gaps:
        st.markdown("**What the buyer could not confirm**")
        st.dataframe(pd.DataFrame([{"Question":q,"Trial mentions":count} for q,count in gaps.most_common()]),hide_index=True,width="stretch")
    with st.expander("Every competitor's rank, reason and evidence"):
        st.dataframe(pd.DataFrame(records),hide_index=True,width="stretch")
        st.json({p["product_id"]:[b.model_dump() for b in source_blocks(Listing.model_validate(p))] for p in batch["products"]})
    st.download_button("Download full rankings CSV",pd.DataFrame(records).to_csv(index=False),f"{prefix}_rankings.csv","text/csv",key=prefix+"csv")


def show_comparison(before,after,key):
    comparison=compare_shelves(before,after)
    cols=st.columns(3)
    d=comparison["selection_delta"]
    cols[0].metric("Paired selection change","—" if d is None else f"{d*100:+.1f} pp")
    d=comparison["top3_delta"]
    cols[1].metric("Paired top-3 change","—" if d is None else f"{d*100:+.1f} pp")
    d=comparison["rank_improvement"]
    cols[2].metric("Mean rank improvement","—" if d is None else f"{d:+.2f}")
    st.caption(f"{comparison['paired_trials']} successful pairs; {comparison['excluded_failed_pairs']} failed pairs excluded from deltas and retained in the export. Same shelf, buyer scenarios, order and model configuration.")
    chart=pd.DataFrame([{"Stage":"Before","Selection rate":before["metrics"]["selection_rate"],"Equal-share reference":before["metrics"]["equal_share_reference"]},
                        {"Stage":"After","Selection rate":after["metrics"]["selection_rate"],"Equal-share reference":after["metrics"]["equal_share_reference"]}]).set_index("Stage")
    st.bar_chart(chart,y="Selection rate",color="#206b57",height=220)
    st.caption("Bars use each stage's successful trials; paired deltas above use their common successful pairs. Results can be unchanged or worse.")
    with st.expander("Inspect paired outcomes"):
        st.dataframe(pd.DataFrame(comparison["rows"]),hide_index=True,width="stretch")
    return comparison


def main():
    st.markdown("""<style>.stApp{background:#f6f8f5}h1,h2,h3{color:#153f35}.block-container{padding-top:3.5rem}
    div[data-testid="stMetric"]{background:white;border:1px solid #dce6df;border-radius:12px;padding:14px}
    section[data-testid="stSidebar"]{background:#e7eee8}div.stButton>button[kind="primary"]{background:#185b49;border:0}
    </style>""",unsafe_allow_html=True)
    st.caption("BOTSHELF / THE AGENT-READY SHELF")
    st.title("Would a shopping agent choose you?")
    st.write("One listing. Seven real alternatives. Find the evidence gaps, improve the facts, and measure what changes.")
    if not (ROOT/"data/esci/processed/shelves.json").exists():
        st.info("Build the Amazon catalog first: python scripts/build_esci.py"); return
    shelves=load_shelves(); store=Store(os.getenv("BOTSHELF_DB",str(ROOT/"data/botshelf.sqlite")))
    with st.sidebar:
        st.header("Your competition shelf")
        sid=st.selectbox("Category",[s.shelf_id for s in shelves],format_func=lambda x:next(s.category for s in shelves if s.shelf_id==x),key="amazon_category")
        shelf=next(s for s in shelves if s.shelf_id==sid).model_copy(deep=True)
        pid=st.selectbox("Your SKU / ASIN",[p.product_id for p in shelf.products],format_func=lambda x:next(p.title[:64]+" · "+x for p in shelf.products if p.product_id==x),key="amazon_target_"+sid)
        mode_label=st.radio("Shopping agent",["Offline scoring baseline","Codex CLI"],key="amazon_agent")
        mode="offline" if mode_label.startswith("Offline") else "codex"
        model=""
        if mode=="codex":
            model=st.text_input("Codex model ID",value=os.getenv("CODEX_MODEL","gpt-6-astra"),
                help="Uses your local Codex CLI login. Keep this model fixed during paired experiments.")
            st.caption("Requires Codex CLI 0.160.1 or newer and codex login. No API key is copied into this app.")
        repeats=st.slider("Repeats per buyer request",min_value=1,max_value=5,value=3,key="amazon_repeats")
        choices=st.multiselect("Real buyer search queries",[s.scenario_id for s in shelf.scenarios],default=[s.scenario_id for s in shelf.scenarios],
            format_func=lambda x:next(s.text for s in shelf.scenarios if s.scenario_id==x),key="amazon_queries_"+sid)
        custom=st.text_area("Additional buyer requests (one per line)",help="These are merchant-authored scenarios, not observed customer data.",key="amazon_custom_"+sid)
        shelf.scenarios=[s for s in shelf.scenarios if s.scenario_id in choices]
        for i,line in enumerate(custom.splitlines()):
            if line.strip(): shelf.scenarios.append(BuyerScenario(scenario_id="custom-"+digest(line)[:12],text=line.strip(),origin="Merchant-authored scenario"))
        shelf.scenarios=list({s.scenario_id:s for s in shelf.scenarios}.values())
        st.caption(f"{len(shelf.scenarios)*repeats} trials per stage · Up to 3 concurrent calls · One validation retry maximum.")
        st.caption("Historical ESCI records. Current prices, stock and conversion outcomes are not supplied.")
    if not shelf.scenarios: st.warning("Choose at least one buyer request."); return
    if len(shelf.scenarios)>12: st.warning("Use at most 12 requests per experiment to bound runtime and API spend."); return
    try: engine=ShelfEngine(mode,model=model)
    except ValueError as exc: st.warning(str(exc)); return
    original=next(p for p in shelf.products if p.product_id==pid)
    context=digest({"shelf":shelf.model_dump(),"target":pid,"config":engine.config_hash,"repeats":repeats})
    if st.session_state.get("amazon_work",{}).get("context")!=context:
        st.session_state.amazon_work={"context":context}
    work=st.session_state.amazon_work
    if mode=="offline": st.info("OFFLINE BASELINE · BM25 + specification mentions + seeded noise. No Codex calls, no claim of real-agent lift.")
    else: st.info("CODEX EXPERIMENT · Local Codex CLI with a fixed model; controlled simulation, not Amazon ranking or real customer conversion.")
    latest=work.get("completed_run") or work.get("rewritten_run") or work.get("baseline")
    cols=st.columns(4)
    cols[0].metric("Your selection rate",percent(latest["metrics"]["selection_rate"]) if latest else "Not run")
    cols[1].metric("Equal-share reference",f"{1/len(shelf.products):.1%}")
    cols[2].metric("Real competitors",len(shelf.products)-1)
    cols[3].metric("Buyer requests",len(shelf.scenarios))
    with st.expander("Inspect the real shelf and selection method"):
        st.write(f"Source query: **{shelf.query}** · query ID {shelf.query_id}")
        st.caption(shelf.selection_note)
        st.dataframe(pd.DataFrame([{"Your SKU":p.product_id==pid,"ASIN":p.product_id,"Brand":p.brand,"Title":p.title} for p in shelf.products]),hide_index=True,width="stretch")
        st.caption("Relevant products are filtered by historical E/S labels. These labels are never sent to the shopping agent. Related queries may prefer different alternatives.")
    tabs=st.tabs(["01 · Audit","02 · Simulate buyers","03 · Rewrite & retest","04 · Fill the gaps","Data & methodology"])
    audit=audit_listing(original,shelf.query,shelf.category)
    with tabs[0]:
        st.subheader("Make the listing legible to an agent")
        st.metric("Agent-readability heuristic / 100",audit["score"])
        st.caption(audit["method"])
        st.dataframe(pd.DataFrame([{"Dimension":name,"Points / 20":score} for name,score in audit["components"].items()]),hide_index=True,width="stretch")
        left,right=st.columns(2)
        with left:
            st.markdown("#### Specific issues")
            for issue in audit["issues"]: st.write("• "+issue)
        with right:
            st.markdown("#### Source listing")
            st.write(original.title)
            for b in original.bullets: st.write("• "+b)
            with st.expander("Description and evidence blocks"):
                st.text(original.description or "Not supplied")
                st.json([b.model_dump() for b in source_blocks(original)])
        with st.expander("Scoring rubric, not a performance claim"):
            st.write("Vocabulary: fraction of query terms present × 20. Specs: min(number+unit matches / 5, 1) × 20. Attributes: category keyword groups mentioned × 20. Structure: title, up to five bullets, and description, equally weighted. Low fluff: max(0, 1 − promotional-token ratio / 0.10) × 20.")
            st.json(audit)
            st.caption("A mention is not verification. Certifications, medical suitability and safety claims are not independently checked. A high score does not guarantee selection.")
    with tabs[1]:
        st.subheader("Let the whole shelf compete")
        st.write("Every product receives a rank and a reason. The same requests and shuffled orders are reused for all three stages.")
        st.dataframe(pd.DataFrame([{"Buyer request":s.text,"Origin":s.origin,"Source query ID":s.source_query_id} for s in shelf.scenarios]),hide_index=True,width="stretch")
        if st.button("Run original shelf",type="primary",key="amazon_run_base"):
            bar=st.progress(0.0)
            work["baseline"]=run_shelf(shelf,pid,engine,repeats=repeats,progress=bar.progress)
            for k in ("rewritten_run","completed_run"): work.pop(k,None)
            store.save("amazon_run",context,{"stage":"original","run":work["baseline"]})
            st.rerun()
        if "baseline" in work: show_results(work["baseline"],pid,"base")
    with tabs[2]:
        st.subheader("Change the presentation. Preserve the facts.")
        st.write("Reorder supported source passages into labelled bullets and an attribute table. The original details are retained so qualifiers and limitations cannot disappear.")
        if st.button("Draft evidence-locked rewrite",key="amazon_draft"):
            with st.spinner("Organizing existing source evidence…"):
                work["draft"]=rewrite_listing(original,shelf.query,shelf.category,engine)
            st.rerun()
        if "draft" in work:
            draft=work["draft"]
            if draft["status"]=="failed": st.error(draft["error"])
            else:
                revised=Listing.model_validate(draft["listing"])
                left,right=st.columns(2)
                with left:
                    st.markdown("#### Original")
                    st.write(original.title)
                    for b in original.bullets: st.write("• "+b)
                with right:
                    st.markdown("#### Proposed")
                    st.write(revised.title)
                    for b in revised.bullets: st.write("• "+b)
                st.dataframe(pd.DataFrame(draft["evidence"]),hide_index=True,width="stretch")
                st.caption(draft["method"])
                if draft["plan"]["merchant_questions"]:
                    st.write("**Merchant to confirm:**")
                    for q in draft["plan"]["merchant_questions"]: st.write("• "+q)
                approved=st.checkbox("I checked the source passages and approve this version.",key="amazon_approve_"+context+digest(draft)[:8])
                if st.button("Save approved rewrite",disabled=not approved,key="amazon_save_rewrite"):
                    work["rewritten"]=revised.model_dump()
                    for k in ("rewritten_run","completed","completed_run"): work.pop(k,None)
                    store.save("amazon_version",context,{"stage":"rewritten","original":original.model_dump(),"draft":draft})
                    st.success("Approved version saved; original preserved.")
        if "rewritten" in work:
            if st.button("Retest rewritten shelf",disabled="baseline" not in work,key="amazon_retest",type="primary"):
                bar=st.progress(0.0)
                work["rewritten_run"]=run_shelf(shelf,pid,engine,Listing.model_validate(work["rewritten"]),repeats,bar.progress)
                store.save("amazon_run",context,{"stage":"rewritten","run":work["rewritten_run"]}); st.rerun()
            if "baseline" not in work: st.caption("Run the original shelf first to create a paired baseline.")
        if "rewritten_run" in work:
            show_comparison(work["baseline"],work["rewritten_run"],"rewrite")
            show_results(work["rewritten_run"],pid,"rewrite")
    with tabs[3]:
        st.subheader("Add the facts only the merchant can confirm")
        st.caption("Stage 3 adds new, merchant-attested information. It is a different intervention from rewriting. Source notes and reviewer names are stored but not sent to the ranking model.")
        current=Listing.model_validate(work.get("completed") or work.get("rewritten") or original.model_dump())
        gaps=[k for k,v in audit_listing(current,shelf.query,shelf.category)["attribute_presence"].items() if not v and not any(f.attribute==k for f in current.merchant_facts)]
        if gaps:
            with st.form("amazon_gap_form_"+context):
                attr=st.selectbox("Missing attribute",gaps)
                value=st.text_input("Verified value",placeholder="Enter the actual specification, including units and limitations")
                source_note=st.text_input("Source document / reference",placeholder="Manufacturer specification or merchant record")
                reviewer=st.text_input("Confirmed by")
                confirmed=st.checkbox("I confirm this is accurate for this exact SKU and supported by the cited record.")
                submitted=st.form_submit_button("Save merchant-confirmed fact")
                if submitted:
                    if not confirmed: st.error("Confirmation is required.")
                    else:
                        try:
                            updated=add_merchant_fact(current,attr,value,source_note,reviewer,shelf.category)
                            work["completed"]=updated.model_dump(); work.pop("completed_run",None)
                            store.save("amazon_version",context,{"stage":"merchant_completed","listing":updated.model_dump(),"parent":current.model_dump()})
                            st.rerun()
                        except ValueError as exc: st.error(str(exc))
        else: st.info("No remaining keyword-based gaps. Existing claims may still need factual verification; they are not silently overwritten.")
        if current.merchant_facts: st.dataframe(pd.DataFrame([f.model_dump() for f in current.merchant_facts]),hide_index=True,width="stretch")
        if "completed" in work:
            if st.button("Retest completed shelf",disabled="baseline" not in work,key="amazon_complete_test",type="primary"):
                bar=st.progress(0.0)
                work["completed_run"]=run_shelf(shelf,pid,engine,Listing.model_validate(work["completed"]),repeats,bar.progress)
                store.save("amazon_run",context,{"stage":"merchant_completed","run":work["completed_run"]}); st.rerun()
        if "completed_run" in work:
            reference=work.get("rewritten_run") or work["baseline"]
            st.caption("Comparison against "+("rewritten" if "rewritten_run" in work else "original")+" listing.")
            show_comparison(reference,work["completed_run"],"completed")
            show_results(work["completed_run"],pid,"completed")
    with tabs[4]:
        st.subheader("Relevance gets you onto a shelf. Choice is a separate question.")
        analysis=json.loads((ROOT/"data/esci/processed/analysis.json").read_text())
        manifest=json.loads((ROOT/"data/esci/processed/manifest.json").read_text())
        st.write(f"Computed from **{analysis['sample_pairs']:,} actual US query–product pairs**; {analysis['unique_queries']:,} queries. Outcome: ESCI Exact versus S/C/I.")
        st.dataframe(pd.DataFrame(analysis["coverage_bins"]),hide_index=True,width="stretch")
        st.bar_chart(pd.DataFrame(analysis["coverage_bins"]).set_index("coverage_bin")["exact_rate"],color="#206b57")
        st.write(f"Query-disjoint holdout: {analysis['test_pairs']:,} pairs · ROC AUC {analysis['heldout_auc']:.3f} · Accuracy {analysis['heldout_accuracy']:.3f} · Majority baseline {analysis['majority_baseline_accuracy']:.3f}")
        st.dataframe(pd.DataFrame(analysis["coefficients"]),hide_index=True,width="stretch")
        st.warning(analysis["interpretation"])
        st.caption(analysis["split_note"])
        st.caption("These relevance labels do not label purchases by an AI agent. Simulated selection is measured separately; we make no claim that every possible public dataset lacks such labels.")
        with st.expander("Sampling, feature definitions and source hashes"):
            st.json(analysis["feature_definitions"]); st.json(manifest)
        st.markdown("[Official Amazon ESCI dataset](https://github.com/amazon-science/esci-data) · [Codex structured-output documentation](https://learn.chatgpt.com/docs/non-interactive-mode)")
    st.divider()
    st.subheader("Take the evidence with you")
    report={"project":"BotShelf Amazon shelf lab","mode":mode,"context_hash":context,"target_id":pid,
            "source_query":shelf.query,"audit":audit,"scenarios":[s.model_dump() for s in shelf.scenarios],
            "stages":{k:work[k] for k in ("baseline","rewritten_run","completed_run") if k in work},
            "versions":{k:work[k] for k in ("draft","rewritten","completed") if k in work},
            "limitations":"Historical catalog. Offline is a synthetic scoring baseline. No causal sales claim; repeated scenarios are correlated; merchant facts are self-attested."}
    cols=st.columns(3)
    cols[0].download_button("Experiment JSON",json.dumps(report,indent=2),"botshelf_experiment.json","application/json")
    # Full JSON preserves readable evidence, configuration and every failed run.
    cols[1].download_button("Evidence HTML",shelf_report(report),"botshelf_evidence.html","text/html")
    export=work.get("completed") or work.get("rewritten") or original.model_dump()
    cols[2].download_button("Listing JSON",json.dumps(export,indent=2),"listing.json","application/json")
    with st.expander("Saved versions and experiment history"):
        events=[e for e in store.events() if e["kind"].startswith("amazon_")]
        st.dataframe(pd.DataFrame([{k:v for k,v in e.items() if k!="payload"} for e in events[:40]]),hide_index=True,width="stretch")
        st.download_button("Full saved history",json.dumps(events,indent=2),"amazon_history.json","application/json")
        compatible=[e for e in events if e["scope"]==context and e["kind"]=="amazon_run"]
        if compatible:
            restore_id=st.selectbox("Restore a matching saved stage",[e["id"] for e in compatible],format_func=lambda x:next(f"{e['created']} · {e['payload']['stage']}" for e in compatible if e['id']==x))
            if st.button("Restore saved result"):
                event=next(e for e in compatible if e["id"]==restore_id)
                stage={"original":"baseline","rewritten":"rewritten_run","merchant_completed":"completed_run"}[event["payload"]["stage"]]
                if stage!="baseline" and "baseline" not in work: st.error("Restore the matching original stage first.")
                else:
                    work[stage]=event["payload"]["run"]
                    if stage in ("rewritten_run","completed_run"):
                        version_key="rewritten" if stage=="rewritten_run" else "completed"
                        work[version_key]=next(p for p in work[stage]["products"] if p["product_id"]==pid)
                    st.rerun()
