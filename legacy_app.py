import hashlib
import json
import os
import time
import pandas as pd
import streamlit as st
from botshelf.catalog import ROOT, Retriever, load_catalog, load_needs
from botshelf.engine import Engine, simulate_shopping
from botshelf.evaluation import evaluate_pairs, experiment_products, html_report, review_fingerprint, revision_fingerprint
from botshelf.evidence import apply_revisions, audit_product, propose_revision
from botshelf.models import Constraint, Need
from botshelf.storage import Store

st.set_page_config(page_title="BotShelf | Evidence before influence", page_icon="◈", layout="wide")
st.markdown("""<style>.stApp{background:#f6f8f5}h1,h2,h3{color:#153f35}div[data-testid="stMetric"]{background:white;border:1px solid #dce6df;border-radius:12px;padding:16px}section[data-testid="stSidebar"]{background:#e7eee8}.block-container{padding-top:4.5rem}div.stButton>button[kind="primary"]{background:#185b49;border:0}</style>""", unsafe_allow_html=True)
st.caption("BOTSHELF / MERCHANT INTELLIGENCE LAB")
st.title("Evidence before influence.")
st.write("Understand what a shopping bot can verify. Improve the facts it sees. Measure the difference.")

if not (ROOT / "data/processed/catalog.json").exists():
    st.error("Catalog missing. Run: python scripts/prepare_data.py")
    st.stop()

@st.cache_data
def data():
    return load_catalog(), load_needs()

products, needs = data()
store = Store(os.getenv("BOTSHELF_DB", str(ROOT / "data/botshelf.sqlite")))
lookup = {p.product_id: p for p in products}

with st.sidebar:
    st.header("Experiment workspace")
    mode_label = st.radio("Engine", ["Offline rules baseline", "Live model API"])
    mode = "offline" if mode_label.startswith("Offline") else "live"
    st.caption("Offline is a deterministic test harness, not an AI shopping model.")
    experiment = st.radio("Experiment", ["A", "B"], format_func=lambda x: "A · Structure existing facts" if x == "A" else "B · Synthetic missing-field recovery")
    search = st.text_input("Search catalog")
    filtered = [p for p in products if search.lower() in (p.name+" "+p.product_id).lower()]
    if not filtered:
        st.info("No products match.")
        st.stop()
    ids = [p.product_id for p in filtered]
    product_id = st.selectbox("Target product", ids, index=ids.index("216") if "216" in ids else 0, format_func=lambda x: f"{lookup[x].name} · {x}")
    source = lookup[product_id]
    related = [n for n in needs if n.target_id == product_id]
    preset = related[0] if related else needs[0]
    custom = st.toggle("Custom shopping need")
    if custom:
        text = st.text_area("Shopping need", "A round dining table with a solid wood top.")
        st.caption("Confirm structured hard constraints below. Free text is retrieval context, not an automatic constraint parser.")
        material = st.selectbox("Tabletop material", ["Any", "solid wood", "manufactured wood", "glass", "metal"])
        shape = st.selectbox("Shape", ["Any", "round", "rectangular", "square", "oval"])
        seats = st.number_input("Minimum seats (0 = unspecified)", 0, 20, 0)
        width = st.number_input("Maximum explicit width, cm (0 = unspecified)", 0.0, 1000.0, 0.0)
        constraints = []
        if material != "Any": constraints.append(Constraint(attribute="top_material", value=material))
        if shape != "Any": constraints.append(Constraint(attribute="shape", value=shape))
        if seats: constraints.append(Constraint(attribute="seats", operator="gte", value=str(seats)))
        if width: constraints.append(Constraint(attribute="width_cm", operator="lte", value=str(width)))
        preference = st.text_input("Soft preferences", "")
        need = Need(need_id="custom", text=text, target_id=product_id, constraints=constraints, preferences=preference)
    else:
        need_id = st.selectbox("Shopping scenario", [n.need_id for n in needs],
            index=needs.index(preset), format_func=lambda x: next(n.text for n in needs if n.need_id == x), key="need_"+product_id)
        need = next(n for n in needs if n.need_id == need_id).model_copy(update={"target_id": product_id})
    page = st.radio("Workspace", ["Catalog & Audit", "Shopping Simulation", "Improve & Compare", "Evaluation & Export"])
    st.divider()
    st.caption("Local prototype · WANDS dining tables · No real checkout or marketplace ranking claims")

try:
    engine = Engine(mode)
except ValueError as exc:
    st.warning(str(exc))
    st.stop()

context = hashlib.sha256(json.dumps({"product": product_id, "need": need.model_dump(), "experiment": experiment, "config": engine.config_hash}, sort_keys=True).encode()).hexdigest()
if st.session_state.get("context") != context:
    for key in ("before_run", "after_run", "revised", "approved", "batch", "elapsed"):
        st.session_state.pop(key, None)
    st.session_state.context = context

candidates = Retriever(products).search(need.text)
baseline, _, _ = experiment_products(candidates, source, need, experiment) if need.constraints else (candidates, candidates, [])
target = next((p for p in baseline if p.product_id == product_id), source.model_copy(deep=True))
revision_source = source.model_copy(deep=True)
if experiment == "B":
    from botshelf.evidence import mask_attribute
    target = mask_attribute(source, need.constraints[0].attribute) if need.constraints else source
    revision_source.name, revision_source.description = target.name, ""
issues = audit_product(target, need)
proposals = propose_revision(target, issues, revision_source)
recalled = product_id in [p.product_id for p in candidates]

a,b,c = st.columns(3)
a.metric("Catalog products", len(products))
b.metric("Candidate set", f"{len(candidates)} / 15")
c.metric("Target retrieved", "Yes" if recalled else "No")
if mode == "offline": st.info("OFFLINE RULES BASELINE — no model API calls. Results test the pipeline, not AI behavior.")
if experiment == "B": st.warning("SYNTHETIC EXPERIMENT — prose is withheld for all candidates; one explicit target attribute is hidden and later restored from source evidence.")


def show_run(run):
    if run.status == "failed":
        st.error(run.error)
    else:
        st.write("**Top recommendations:** " + ("; ".join(f"{lookup[pid].name} ({pid})" for pid in run.result.recommendations) or "No eligible products"))
        st.dataframe(pd.DataFrame([{"Product ID": a.product_id,
            "Condition checks": "; ".join(f"{c.attribute}: {status}" for c, status in zip(need.constraints, a.statuses)),
            "Evidence": " | ".join(e.field+": "+e.quote for e in a.evidence), "Reason": a.reason}
            for a in run.result.assessments]), hide_index=True, width="stretch")
    st.caption(f"{run.engine} · {run.elapsed_s:.2f}s · {run.api_calls} API calls · config {run.config_hash[:12]}")


if page == "Catalog & Audit":
    st.subheader(source.name.title())
    st.caption(source.source)
    left, right = st.columns([1, 1])
    with left:
        st.markdown("#### Source record")
        st.write(target.description or "No description supplied.")
        st.dataframe(pd.DataFrame([{"source fragment": s} for s in target.features.split("|") if s]), hide_index=True, width="stretch")
    with right:
        st.markdown("#### Evidence audit")
        st.write(need.text)
        for issue in issues:
            with st.expander(f"{issue.kind.upper()} · {issue.attribute}", expanded=True):
                st.write(issue.explanation)
                for e in issue.evidence: st.code(e.field+": "+e.quote)
        st.caption("Supported checks: explicit tabletop material, shape, seating capacity and unit-labelled width. Prose-only claims and other attributes require human review.")

elif page == "Shopping Simulation":
    st.subheader("What can the shopper verify?")
    st.write(need.text)
    st.dataframe(pd.DataFrame([c.model_dump() for c in need.constraints]), hide_index=True)
    st.write("Soft preferences:", need.preferences or "None")
    with st.expander("Frozen candidate IDs"): st.write([p.product_id for p in baseline])
    if not recalled: st.warning("The target was not retrieved. It will not be forced into this experiment.")
    if st.button("Run baseline", type="primary", disabled=not need.constraints):
        with st.spinner("Checking candidates…"):
            run = simulate_shopping(need, baseline, engine)
            st.session_state.before_run = run
            store.save("shopping_run", context, {"need": need.model_dump(), "candidate_ids": [p.product_id for p in baseline], "config": engine.config, "run": run.model_dump()})
    if "before_run" in st.session_state: show_run(st.session_state.before_run)

elif page == "Improve & Compare":
    st.subheader("Approve facts. Then compare.")
    st.caption("The source remains immutable. Only checked, source-supported fields are copied to a new version.")
    selected = []
    for index, proposal in enumerate(proposals):
        if st.checkbox(f"{proposal.attribute}: {proposal.old_value} → {proposal.new_value}", key=f"approve-{context}-{index}"):
            selected.append(proposal)
        st.caption(proposal.reason)
        st.code(proposal.evidence.field+": "+proposal.evidence.quote)
    if not proposals: st.info("No safe automatic revisions. Resolve missing or conflicting facts with the merchant.")
    if st.button("Apply approved revisions", disabled=not selected, type="primary"):
        revised = apply_revisions(target, selected, revision_source)
        st.session_state.revised = revised
        st.session_state.approved = [p.model_dump() for p in selected]
        st.session_state.pop("after_run", None)
        store.save("revision", context, {"source": source.model_dump(), "baseline": target.model_dump(), "revised": revised.model_dump(), "approved": st.session_state.approved})
        st.success("Saved a new version with your approval.")
    if "revised" in st.session_state:
        st.json(st.session_state.revised.structured)
        if st.button("Run paired comparison", disabled=not recalled or not need.constraints):
            with st.spinner("Running the same need and candidate order before and after…"):
                updated = [st.session_state.revised if p.product_id == product_id else p for p in baseline]
                st.session_state.before_run = simulate_shopping(need, baseline, engine)
                st.session_state.after_run = simulate_shopping(need, updated, engine)
                store.save("comparison", context, {"before": st.session_state.before_run.model_dump(), "after": st.session_state.after_run.model_dump(), "config": engine.config, "candidate_ids": [p.product_id for p in baseline]})
        if "after_run" in st.session_state:
            left, right = st.columns(2)
            with left: st.markdown("#### Before"); show_run(st.session_state.before_run)
            with right: st.markdown("#### After"); show_run(st.session_state.after_run)

else:
    st.subheader("Measure honestly. Export the evidence.")
    with st.expander("Review draft cases before a formal evaluation"):
        review_id = st.selectbox("Case", [n.need_id for n in needs])
        case = next(n for n in needs if n.need_id == review_id)
        st.write(case.text)
        st.json(case.model_dump())
        st.json(lookup[case.target_id].model_dump())
        reviewer = st.text_input("Reviewer name")
        checked = st.checkbox("I checked every constraint and quoted source against the original record.")
        if st.button("Record case review", disabled=not checked or not reviewer.strip()):
            digest = review_fingerprint(case, lookup[case.target_id])
            store.save("case_review", digest, {"approved": True, "reviewer": reviewer, "case_id": case.need_id})
            st.success("Review recorded for this exact case version.")
        review_exp = st.selectbox("Revision experiment to review", ["A", "B"])
        _, _, case_changes = experiment_products(Retriever(products).search(case.text), lookup[case.target_id], case, review_exp)
        st.dataframe(pd.DataFrame([r.model_dump() for r in case_changes]), hide_index=True)
        changes_checked = st.checkbox("I verified every proposed revision against its quoted source; no unsupported claims.")
        if st.button("Record revision review", disabled=not changes_checked or not reviewer.strip()):
            store.save("revision_review", revision_fingerprint(case, lookup[case.target_id], review_exp, case_changes),
                       {"approved": True, "reviewer": reviewer, "case_id": case.need_id, "experiment": review_exp})
            st.success("Revision evidence review recorded.")
    split = st.selectbox("Evaluation set", ["dev", "test"])
    exploratory = st.checkbox("Allow unreviewed exploratory evaluation (clearly labelled)")
    evaluation_needs = [n.model_copy(deep=True) for n in needs if n.split == split]
    reviews = {e["scope"] for e in store.events("case_review")}
    for n in evaluation_needs:
        n.reviewed = review_fingerprint(n, lookup[n.target_id]) in reviews
    revision_reviews = {e["scope"] for e in store.events("revision_review")}
    revisions_complete = True
    review_retriever = Retriever(products)
    for n in evaluation_needs:
        for exp in ("A", "B"):
            _, _, changes = experiment_products(review_retriever.search(n.text), lookup[n.target_id], n, exp)
            if changes and revision_fingerprint(n, lookup[n.target_id], exp, changes) not in revision_reviews:
                revisions_complete = False
    st.caption(f"{sum(n.reviewed for n in evaluation_needs)} / {len(evaluation_needs)} cases reviewed. Two experiments × three repeats × before/after; live mode may incur API costs.")
    st.caption("Revision evidence reviews: " + ("complete" if revisions_complete else "pending; required for formal evaluation"))
    if st.button("Run batch evaluation", disabled=not exploratory and not (all(n.reviewed for n in evaluation_needs) and revisions_complete)):
        progress = st.progress(0.0)
        st.session_state.batch = evaluate_pairs(products, evaluation_needs, engine, store, progress.progress)
    if "batch" in st.session_state:
        batch = st.session_state.batch
        st.write(batch["manifest"])
        st.dataframe(pd.DataFrame(batch["summary"]), hide_index=True)
        st.download_button("Download evaluation CSV", pd.DataFrame(batch["rows"]).to_csv(index=False), "evaluation.csv", "text/csv")
        st.download_button("Download full evaluation JSON", json.dumps(batch, indent=2), "evaluation.json", "application/json")
        st.download_button("Download evaluation HTML", html_report(batch), "evaluation.html", "text/html")
    payload = {"mode": mode, "experiment": experiment, "product": source.model_dump(), "need": need.model_dump(),
        "audit": [i.model_dump() for i in issues], "approved_revisions": st.session_state.get("approved", []),
        "before": st.session_state.before_run.model_dump() if "before_run" in st.session_state else None,
        "after": st.session_state.after_run.model_dump() if "after_run" in st.session_state else None}
    if "revised" in st.session_state:
        st.download_button("Download revised product JSON", st.session_state.revised.model_dump_json(indent=2), "revised_product.json", "application/json")
    st.download_button("Download current audit HTML", html_report(payload), "audit_report.html", "text/html")
    with st.expander("Saved run history"):
        history = store.events()
        st.dataframe(pd.DataFrame([{k:v for k,v in event.items() if k != "payload"} for event in history[:50]]), hide_index=True)
        st.download_button("Download saved evidence history", json.dumps(history, indent=2), "history.json", "application/json")
    st.markdown("#### Time study (exploratory)")
    method = st.selectbox("Method", ["Manual", "BotShelf-assisted"])
    seconds = st.number_input("Observed completion time in seconds", min_value=0.0)
    observer = st.text_input("Observer / participant code")
    if st.button("Save observed timing", disabled=seconds <= 0 or not observer.strip()):
        store.save("timing", product_id, {"method": method, "seconds": seconds, "participant": observer})
        st.success("Observation saved. This is entered timing data, not an automated speed claim.")
