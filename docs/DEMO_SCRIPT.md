# Four-minute demo script

## Preparation

Start the local app, default product 216 / need-02. Confirm the engine label before presenting.
For live mode, configure credentials outside the browser and complete a smoke test. Use the same model throughout.
For offline mode, explicitly say: “This is our deterministic pipeline baseline; live-model results are pending.”
Have `outputs/offline_test.html` ready as a labelled backup, not a substitute for a live model run.

## 0:00–0:35 — The merchant's question

“When an agent shops, can it verify that my table fits the customer's need? BotShelf shows what is known, what is
missing, and what cannot be fixed by rewriting copy.” Show the selected need and its explicit hard constraints.
Explain that “solid wood” in a name does not establish a solid-wood tabletop when the record says otherwise.

## 0:35–1:15 — Inspect the evidence

In Catalog & Audit, show a source fragment, a safe structure suggestion, and any missing-unit limitation.
“We preserve uncertainty. We do not convert an unlabelled number into an assumed inch measurement.”

## 1:15–2:00 — Run a baseline

In Shopping Simulation, show the fixed candidate IDs and run. Explain the result mode, evidence, unknowns, and any
abstentions. Do not guarantee the target will rank first. A live failure is visible and should be acknowledged.

## 2:00–2:45 — Approve and repeat

In Improve & Compare, approve the material/shape proposals and run the paired comparison.
“These revisions use source facts. We changed the representation, not the product.”
In offline A, point out that unchanged rankings are expected because the baseline already reads those fields.
If time permits, switch to B, explicitly name the synthetic intervention and restore the hidden material.

## 2:45–3:30 — Show the whole evaluation

Open the saved HTML report. A and B are separate. Call out 30 cases, 20 not-recalled targets, 10 recalled targets,
and three repeats per recalled target. Explain that this is a conditional result from an unreviewed offline baseline,
not actual marketplace reach. Failed and negative outcomes stay in the export.

## 3:30–4:00 — Value and next proof

Download an audit report and a revised product JSON. “The deliverable is an actionable, auditable catalog fix.
The next proof is merchant review, frozen live-model evaluation and measured operator time savings.”

## Recording and fallback checklist

- Record the complete screen flow after credentials and private windows are hidden.
- Include the engine label and synthetic-experiment banner in the recording.
- Name the backup recording `botshelf_demo_<date>_<engine>.mp4`.
- A recording is not included in this implementation; the team must capture and review it before submission.
- If a provider fails during presentation, switch openly to the saved offline report or labelled recording.
- Never describe the rule baseline as a shopping AI or its recovery metric as conversion lift.
