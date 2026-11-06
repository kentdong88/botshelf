"""Standalone readable Amazon experiment report with escaped evidence."""
import html
import json


def shelf_report(report):
    def esc(x): return html.escape(str(x))
    parts=["<!doctype html><html lang='en'><meta charset='utf-8'><title>BotShelf shelf experiment</title>",
        "<style>body{font:16px system-ui;max-width:1100px;margin:48px auto;padding:0 24px;color:#173c32}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px;border:1px solid #d8e3dd;text-align:left;vertical-align:top}th{background:#e8f0eb}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f4;padding:20px}summary{cursor:pointer;margin-top:24px}h1{font-size:36px}</style>",
        "<h1>BotShelf · Does the agent choose you?</h1>",f"<p>Mode: <strong>{esc(report['mode'])}</strong> · ASIN: {esc(report['target_id'])} · Source query: {esc(report['source_query'])}</p>",
        "<p>Historical catalog. Equal share is a reference, not an entitlement. Offline scores are not evidence of actual AI-shopping behavior. Merchant facts are self-attested.</p>",
        "<h2>Stage results</h2><table><tr><th>Stage</th><th>Selected</th><th>Top 3</th><th>Mean rank</th><th>Valid / attempted</th><th>Abstentions</th></tr>"]
    for stage,run in report["stages"].items():
        m=run["metrics"]
        pct=lambda x: "Not available" if x is None else f"{x:.1%}"
        parts.append(f"<tr><td>{esc(stage)}</td><td>{pct(m['selection_rate'])}</td><td>{pct(m['top3_rate'])}</td><td>{esc(m['average_rank'])}</td><td>{m['successful_trials']} / {m['attempted_trials']}</td><td>{m['abstentions']}</td></tr>")
    parts.append("</table><h2>Listing diagnosis</h2><p>Heuristic score: "+esc(report["audit"]["score"])+" / 100 (not a probability)</p><ul>")
    parts.extend("<li>"+esc(issue)+"</li>" for issue in report["audit"]["issues"])
    parts.append("</ul><h2>Buyer requests</h2><ul>")
    parts.extend("<li>"+esc(s["text"])+" — "+esc(s["origin"])+"</li>" for s in report["scenarios"])
    parts.append("</ul><h2>Target-product explanations</h2>")
    for stage,run in report["stages"].items():
        parts.append("<h3>"+esc(stage)+"</h3><table><tr><th>Request / repeat</th><th>Rank</th><th>Reason</th><th>Unknowns</th></tr>")
        for trial in run["trials"]:
            if trial["status"]!="ok":
                parts.append("<tr><td>"+esc(trial["scenario"])+"</td><td colspan='3'>Failed: "+esc(trial["error"])+"</td></tr>"); continue
            rank,item=next((i+1,r) for i,r in enumerate(trial["result"]["ranking"]) if r["product_id"]==report["target_id"])
            parts.append("<tr><td>"+esc(trial["scenario"])+" / "+str(trial["repeat"]+1)+"</td><td>"+str(rank)+"</td><td>"+esc(item["reason"])+"</td><td>"+esc("; ".join(item["missing_information"]))+"</td></tr>")
        parts.append("</table>")
    parts.append("<details><summary>Full evidence, versions and configuration</summary><pre>"+esc(json.dumps(report,indent=2))+"</pre></details></html>")
    return "".join(parts)
