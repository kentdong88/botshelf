import hashlib
import html
import json
import random
import statistics
from .catalog import Retriever
from .engine import simulate_shopping
from .evidence import apply_revisions, audit_product, check_constraint, mask_attribute, propose_revision


def experiment_products(candidates, target, need, experiment):
    baseline = [p.model_copy(deep=True) for p in candidates]
    if experiment == "B":
        for p in baseline:
            p.name = "Dining table " + p.product_id
            p.description = ""
        baseline = [mask_attribute(p, need.constraints[0].attribute) if p.product_id == target.product_id else p for p in baseline]
    before = next((p for p in baseline if p.product_id == target.product_id), None)
    if before is None:
        return baseline, baseline, []
    # Synthetic recovery uses features only, keeping withheld prose withheld.
    source = target.model_copy(deep=True)
    if experiment == "B":
        source.name, source.description = before.name, ""
    revisions = propose_revision(before, audit_product(before, need), source)
    after = apply_revisions(before, revisions, source)
    return baseline, [after if p.product_id == target.product_id else p for p in baseline], revisions


def fingerprint(products, needs, config):
    payload = {"products": [p.model_dump() for p in products], "needs": [n.model_dump() for n in needs], "config": config}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def review_fingerprint(need, product):
    case = need.model_dump()
    case["reviewed"] = False
    return hashlib.sha256(json.dumps({"case": case, "source": product.model_dump()}, sort_keys=True).encode()).hexdigest()


def revision_fingerprint(need, product, experiment, changes):
    return hashlib.sha256(json.dumps({"case": review_fingerprint(need, product), "experiment": experiment,
        "changes": [c.model_dump() for c in changes]}, sort_keys=True).encode()).hexdigest()


def evaluate_pairs(products, needs, engine, store=None, progress=None):
    retriever = Retriever(products)
    lookup = {p.product_id: p for p in products}
    manifest = {"fingerprint": fingerprint(products, needs, engine.config), "config": engine.config,
                "seeds": [17, 29, 43], "review_status": "human-reviewed" if all(n.reviewed for n in needs) else "UNREVIEWED exploratory",
                "need_count": len(needs), "mode": engine.mode,
                "limitation": "Controlled simulator only; not platform visibility, sales or conversion lift."}
    approvals = {e["scope"] for e in store.events("revision_review") if e["payload"].get("approved")} if store else set()
    if store:
        store.save("evaluation_manifest", manifest["fingerprint"], manifest)
    rows, details = [], []
    for n_index, need in enumerate(needs):
        target = lookup[need.target_id]
        candidates = retriever.search(need.text)
        recalled = target.product_id in [p.product_id for p in candidates]
        eligible = all(check_constraint(target, c) == "met" for c in need.constraints)
        for experiment in ("A", "B"):
            baseline, revised, changes = experiment_products(candidates, target, need, experiment)
            changes_reviewed = not changes or revision_fingerprint(need, target, experiment, changes) in approvals
            for repeat, seed in enumerate(manifest["seeds"]):
                row = {"need_id": need.need_id, "split": need.split, "target_id": target.product_id,
                       "experiment": experiment, "repeat": repeat, "engine": engine.mode,
                       "reviewed": need.reviewed, "recalled": recalled, "eligible": eligible,
                       "status": "not_recalled", "before_top3": None, "after_top3": None,
                       "elapsed_s": 0, "api_calls": 0, "recommendations": 0,
                       "hard_violations": 0, "unknown_as_met": 0, "assessment_conditions": 0,
                       "revision_count": len(changes), "revisions_reviewed": changes_reviewed}
                if recalled:
                    order = list(range(len(baseline)))
                    random.Random(seed).shuffle(order)
                    before = simulate_shopping(need, [baseline[i] for i in order], engine)
                    after = simulate_shopping(need, [revised[i] for i in order], engine)
                    row.update(status="ok" if before.status == after.status == "ok" else "failed",
                        elapsed_s=before.elapsed_s+after.elapsed_s, api_calls=before.api_calls+after.api_calls)
                    if row["status"] == "ok":
                        row.update(before_top3=target.product_id in before.result.recommendations,
                                   after_top3=target.product_id in after.result.recommendations)
                    for run, surface in ((before, baseline), (after, revised)):
                        if not run.result:
                            continue
                        by_id = {p.product_id: p for p in surface}
                        row["recommendations"] += len(run.result.recommendations)
                        for pid in run.result.recommendations:
                            row["hard_violations"] += any(check_constraint(lookup[pid], c) == "unmet" for c in need.constraints)
                        for assessment in run.result.assessments:
                            row["assessment_conditions"] += len(assessment.statuses)
                            row["unknown_as_met"] += sum(status == "met" and check_constraint(by_id[assessment.product_id], c) in ("unknown", "conflict")
                                for c, status in zip(need.constraints, assessment.statuses))
                    details.append({"need_id": need.need_id, "experiment": experiment, "repeat": repeat,
                        "candidate_ids": [baseline[i].product_id for i in order], "before": before.model_dump(),
                        "after": after.model_dump(), "revisions": [c.model_dump() for c in changes]})
                rows.append(row)
        if progress:
            progress((n_index+1)/len(needs))
    manifest["revision_review_status"] = "human-reviewed" if all(r["revisions_reviewed"] for r in rows) else "UNREVIEWED exploratory"
    manifest["formal_evaluation"] = all(n.reviewed for n in needs) and all(r["revisions_reviewed"] for r in rows)
    result = {"manifest": manifest, "rows": rows, "details": details, "summary": summarize(rows)}
    if store:
        store.save("evaluation", manifest["fingerprint"], result)
    return result


def summarize(rows):
    output = []
    for group in ("A", "B"):
        selected = [r for r in rows if r["experiment"] == group]
        valid = [r for r in selected if r["status"] == "ok" and r["eligible"] and r["recalled"]]
        attempted = sum(r["status"] != "not_recalled" for r in selected)
        failed = sum(r["status"] == "failed" for r in selected)
        recommendation_count = sum(r["recommendations"] for r in selected)
        condition_count = sum(r["assessment_conditions"] for r in selected)
        per_repeat = []
        for repeat in range(3):
            subset = [r for r in valid if r["repeat"] == repeat]
            if subset:
                per_repeat.append(sum(int(r["after_top3"])-int(r["before_top3"]) for r in subset)/len(subset))
        output.append({"experiment": group, "paired_denominator": len(valid),
            "attempted_pairs": attempted,
            "failed_pair_rate": failed/attempted if attempted else None,
            "unique_needs": len(set(r["need_id"] for r in selected)),
            "not_recalled_needs": len(set(r["need_id"] for r in selected if not r["recalled"])),
            "failed_pairs": sum(r["status"] == "failed" for r in selected),
            "before_top3_rate": sum(r["before_top3"] for r in valid)/len(valid) if valid else None,
            "after_top3_rate": sum(r["after_top3"] for r in valid)/len(valid) if valid else None,
            "delta_by_repeat": per_repeat,
            "delta_std": statistics.pstdev(per_repeat) if per_repeat else None,
            "recommendations": sum(r["recommendations"] for r in selected),
            "hard_violations": sum(r["hard_violations"] for r in selected),
            "hard_violation_rate": sum(r["hard_violations"] for r in selected)/recommendation_count if recommendation_count else None,
            "unknown_as_met": sum(r["unknown_as_met"] for r in selected),
            "assessment_conditions": sum(r["assessment_conditions"] for r in selected),
            "unknown_as_met_rate": sum(r["unknown_as_met"] for r in selected)/condition_count if condition_count else None,
            "api_calls": sum(r["api_calls"] for r in selected),
            "elapsed_s": round(sum(r["elapsed_s"] for r in selected), 3)})
    return output


def html_report(payload):
    def esc(value): return html.escape(str(value))
    def table(rows):
        if not rows: return "<p>No records.</p>"
        keys = list(rows[0])
        return "<div class='scroll'><table><thead><tr>" + "".join("<th>"+esc(k)+"</th>" for k in keys) + "</tr></thead><tbody>" + "".join("<tr>"+"".join("<td>"+esc(r.get(k, ""))+"</td>" for k in keys)+"</tr>" for r in rows) + "</tbody></table></div>"
    content = ""
    if "summary" in payload:
        content += "<h2>Run identity & review status</h2><pre>"+esc(json.dumps(payload["manifest"], indent=2))+"</pre>"
        content += "<h2>Separate experimental results</h2>"+table(payload["summary"])
        content += "<h2>Every paired outcome</h2>"+table(payload["rows"])
    else:
        content += "<h2>Audit & approved revisions</h2>"+table(payload.get("audit", []))
        content += table(payload.get("approved_revisions", []))
    return """<!doctype html><html lang="en"><meta charset="utf-8"><title>BotShelf report</title>
    <style>body{font:15px system-ui;max-width:1100px;margin:48px auto;padding:0 24px;color:#17332d}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f5f3;padding:24px}h1{font-size:36px}table{border-collapse:collapse;font-size:13px}td,th{border:1px solid #dce6df;padding:10px;text-align:left;vertical-align:top}th{background:#e7eee8}.scroll{overflow:auto}summary{cursor:pointer;padding:16px;background:#e7eee8}</style>
    <h1>BotShelf · Evidence report</h1><p>Controlled simulation. Not real marketplace visibility or sales lift.
    Offline runs are deterministic baselines, not AI model experiments. Unreviewed cases are exploratory.</p>""" + content + "<details><summary>Complete evidence and configuration</summary><pre>" + esc(json.dumps(payload, indent=2)) + "</pre></details></html>"
