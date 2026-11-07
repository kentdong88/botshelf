# BotShelf — Evidence before influence

## 1. User, problem and business hypothesis

BotShelf serves small furniture merchants who maintain their own product catalogs. A shopping agent may not be able
to verify a relevant product when its material, shape, dimensions or capacity are ambiguous. Merchants need to know
whether the problem is missing evidence, unclear formatting, a conflicting attribute, or a product that simply does
not meet the shopper's requirement.

The prototype turns that question into a reviewable workflow: inspect the record, run a controlled shopping simulation,
review a supported change, repeat the same comparison and export the evidence. It never promises placement on a real
shopping platform. A potential business model is catalog auditing priced by product count. Willingness to pay and sales
impact are unvalidated hypotheses. An exploratory timing log supports later manual-versus-assisted workflow studies;
no time saving has yet been claimed.

## 2. Prototype, data and use of AI

Four workspaces cover Catalog & Audit, Shopping Simulation, Improve & Compare, and Evaluation & Export. The app uses
Python, Streamlit, Pydantic validation, TF-IDF retrieval and SQLite history. The shopping-model adapter accepts an
environment-configured compatible model API. A separate labelled deterministic baseline permits offline demonstration.

The source is Wayfair's WANDS dataset, under its included MIT license:
https://github.com/wayfair/WANDS. The catalog contains 200 dining-table records, deterministically selected by product ID
from 591 records in that category. Forty draft shopping needs use explicit material, shape and capacity evidence;
10 development and 30 test targets do not overlap. They are template-authored scenarios, not original user behavior.
Original WANDS queries and labels are reserved for a separate retrieval benchmark.

The model's job is to evaluate candidate products and explain supported choices. Deterministic extraction and validation
protect the supported hard constraints. Merchant review, not the model, approves revisions. Source references accompany
each change. Unknown dimensions stay unknown when units are absent. Conflicting values do not resolve automatically.
The app supports explicit tabletop material, shape, seats and unit-labelled width; it does not claim full semantic
coverage of every sentence in a catalog.

Experiment A exposes already-present facts as structured attributes. Experiment B explicitly simulates missing data:
prose is withheld from all candidates, one target attribute is removed, and exact source evidence is restored. Original
catalog retrieval is fixed before either condition. Experiments are reported separately and must not be pooled.

## 3. Evaluation, results and next validation

Each case uses three fixed candidate permutations. Before and after share the same candidate set, order, need, prompt,
model and parameters. Targets outside the top 15 are not inserted artificially. Primary recommendation rates are
conditional on a recalled, eligible target and a successful pair; skipped targets and failed pairs are reported separately.
The reports include paired outcomes, evidence, configuration hashes, runtime and API calls. Invalid claims are retried
once, then recorded as failures. This guardrail means accepted-output error counts do not measure raw model reliability.

The delivered offline test run covers 30 draft held-out scenarios. Twenty targets are not recalled, leaving ten distinct
targets and thirty repeated pairs per experiment. A has 90% top-three inclusion both before and after. B moves from 0%
to 90% when its deliberately removed material is restored. No API calls were made. These results validate pipeline
mechanics; A's unchanged result and B's expected recovery are not evidence of real AI shopping performance.

Live-provider validation is pending a configured key and model. Draft cases and their proposed revisions also require
human review; the UI records source-bound approvals, and formal evaluation is gated on them. The entire current
offline report is labelled exploratory. No merchant interview, measured labor saving, sales uplift or real-platform
ranking improvement is claimed.

Next validation: review the frozen cases and revisions, run a live-model smoke test, execute the untouched held-out set,
inspect failure and no-improvement cases, and test usability with two or three merchant operators. Any later retriever
improvement must be treated as a new experiment version rather than silently replacing this result.
