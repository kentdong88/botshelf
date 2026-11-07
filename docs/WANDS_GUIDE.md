# BotShelf

Evidence-first product auditing and controlled shopping experiments for small furniture merchants.
English Streamlit app, real WANDS product records, local SQLite history, two strictly separated experiments.

## Run locally

Python 3.9–3.12. The project includes a populated 200-product dining-table catalog and 40 draft scenarios.

```bash
cd /Users/kentdong/Desktop/Vibrathon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. No key is required for the clearly labelled **Offline rules baseline**.
Existing installations can simply run `.venv/bin/streamlit run app.py --server.address 127.0.0.1`.

## Live model setup

Export `LLM_API_KEY` (or `OPENAI_API_KEY`), `MODEL_NAME`, and optionally `LLM_BASE_URL` in your shell.
`.env.example` documents the configuration; `.env` files are not loaded automatically. Do not commit keys.
The endpoint must implement `/chat/completions`, JSON object output, and temperature 0. Other providers
can be used via a compatible gateway. No specific model is assumed or silently selected.

Select **Live model API**, run one baseline, inspect its evidence, then freeze the model configuration for evaluation.
Every run stores a configuration hash, prompt and model name; each batch captures one Engine instance.
Configuration changes produce a different experiment identity. A 30-case batch has at most 360 initial requests,
plus at most one retry per request; non-recalled targets are skipped. Check your provider's costs first.
Timeout is 45 seconds per request. Failures remain failures, with no fallback masquerading as a model result.

## Demo workflow

1. Default product **216**, scenario **need-02**, experiment A; inspect source and audit.
2. Run **Shopping Simulation → Run baseline**.
3. **Improve & Compare**: check evidence-linked fields, apply revisions, run paired comparison.
4. Switch to B and repeat, explicitly acknowledging synthetic removal and recovery of tabletop material.
5. **Evaluation & Export**: download audit HTML, revised product JSON, or saved history.

The source remains immutable. Switching product, need, experiment or model clears pending comparison state.
Custom text is retrieval context: users confirm hard constraints in the form. Supported constraints are tabletop
material, shape, minimum seats and maximum explicitly unit-labelled width. Other prose requirements are not
silently interpreted as verified constraints. Soft preferences affect live-model tie-breaking only.

## Data and evaluation

```bash
python scripts/download_data.py
python scripts/prepare_data.py
python scripts/benchmark_retrieval.py
python scripts/evaluate.py --mode offline --split dev --allow-unreviewed
python scripts/evaluate.py --mode offline --split test --allow-unreviewed
python -m pytest -q
```

Preparation deterministically chooses the first 200 Dining Tables by ID from 591 available records. It creates
10 development and 30 test cases with disjoint target products. Cases are **machine-drafted, not human-reviewed**.
The natural-language needs are team-authored templates grounded in explicit source facts, not original WANDS queries.
Source queries and relevance labels are used only by the separate retrieval benchmark. WANDS source license is retained.

To run a formal batch, use the review panel to review each case AND generated revisions for A and B.
Approvals bind to the exact case, product and revision content. Without these approvals, only the explicitly
labelled exploratory mode runs. `scripts/evaluate.py --mode live --split test` applies the same gate.
Review truthful facts rather than changing failed cases to improve results. Keep frozen datasets unchanged.

Experiment A exposes already-present facts in structured fields. Experiment B withholds prose for all candidates,
removes one target attribute, then restores exact source evidence. Retrieval uses original catalog records in both
conditions, so B measures conditional recommendation, not discoverability. The target is never forced into candidates.
Three fixed permutations are paired before/after. Unsupported `met` claims are rejected; this conservative validator
means accepted-output safety metrics also reflect the guardrails, not solely the model's intrinsic ability.

The generated offline report is a pipeline sanity check. Its A results should be unchanged because the same rules
already parse the source; B's change is expected from restoring required evidence. Neither is proof of LLM lift.
The current offline test set has 20/30 targets not retrieved. This limitation is preserved, not filtered away.

## Files and persistence

- `app.py`: four user workspaces.
- `botshelf/`: typed models, conservative evidence processing, model adapter, retrieval, evaluation and storage.
- `data/processed/`: catalog, draft scenarios and provenance manifest.
- `data/raw/`: original data and MIT license. Large raw CSVs are excluded from Git.
- `data/botshelf.sqlite`: append-only versions, approvals, runs, batch results and entered timing observations.
- `outputs/`: labelled evaluation JSON/CSV/HTML and source-query retrieval benchmark.
- `docs/PROJECT_BRIEF.md`, `docs/DEMO_SCRIPT.md`: competition narrative and live-demo script.

Override `BOTSHELF_DB` for an isolated app database. Test fixtures use temporary databases.
Exports are escaped HTML; catalog text is never executed. Keys are never persisted in run metadata.

## Current limitations

No live API key was configured during implementation, so live behavior has transport-mocked tests but no real-provider
smoke test. Human reviews, merchant interviews, real timing studies and a screen-recorded demo remain team activities.
Do not present those as completed. There is no automatic publication, checkout, sales attribution or real-platform ranking.
The extractor intentionally covers four attributes. General contradictions in prose and variant ambiguity require review.
