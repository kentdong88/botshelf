# Four-minute Amazon shelf demo

## Before the demo

Start `streamlit run app.py`. Use Amazon shelf lab → Air purifiers. Keep the default first ASIN and five source queries; set three repetitions. Say which mode is active. If Codex is not installed and logged in, call it an offline scoring baseline throughout. Do not change the shelf after seeing a weak result.

## 0:00–0:40 — One listing, seven alternatives

“We help a small merchant find out what a shopping agent can verify. These eight historical products came from the same real Amazon search query. The agent does not know which one belongs to us.” Open the shelf table and point out the real ASINs and source query. Explain the 1/8 neutral reference and missing live prices.

## 0:40–1:20 — Audit the evidence

Show the five score components and concrete missing attributes. “This is an explicit checklist, not a magic probability. A high score is not proof that the agent will choose us.” Inspect source bullets and a gap. Do not assume a missing warranty means there is no warranty.

## 1:20–2:00 — Simulate the full shelf

Run the original shelf. Show selection rate, top-three rate, average rank, every competitor's reason and the target's missing-information questions. Explain product-order shuffling, full rankings and abstentions. In offline mode, show the formula rather than describing its reasons as Codex judgments.

## 2:00–2:45 — Rewrite and retest

Generate an evidence-locked rewrite. Review the original passage next to labelled bullets and structured attributes. Approve, then retest on exactly the same requests and permutations. “We have preserved the product's facts and qualifiers. If the result stays flat or falls, we retain it.” Show paired delta and sample count.

## 2:45–3:20 — Fill a real gap

Only if an actual source document is available, enter its specification, source note and reviewer. Otherwise demonstrate the empty form and explicitly state that a merchant must provide the fact. Do not fabricate a favorable warranty or certification for the performance demo. Retest after a genuine addition; identify this as a separate intervention from copy reorganization.

## 3:20–4:00 — Explain what the data proves

Show the 40,000-pair observed relevance analysis: coverage 43.19% versus 88.13% Exact, with actual bin counts. “Search relevance is not the same label as agent choice.” Export the HTML evidence report. Finish with the pending live-provider run and merchant validation, not a promise of sales uplift.

## Backup

`outputs/amazon_offline.html` is the saved six-shelf demonstration. Label it as prerecorded data if used. A provider failure remains visible; do not silently substitute offline output as Codex. Team screen recording and real merchant feedback are still required before final competition submission.
