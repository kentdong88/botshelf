# BotShelf — When the customer is a bot

**Would a shopping agent choose your listing over seven real alternatives?**

BotShelf helps small merchants inspect a listing, simulate a complete competitor shelf, reorganize supported facts, and retest after filling evidence gaps. It is a controlled research prototype, not an Amazon SEO service or a promise of conversion lift.

## Run in two minutes

Python 3.9–3.12. Compact, real-data shelves are included; a fresh clone does not need the 1 GB raw catalog.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 127.0.0.1
```

Open http://localhost:8501. Default: **Amazon shelf lab**, offline baseline. The earlier furniture prototype remains accessible under **Product workspace → WANDS research lab**.

## The four-step product

1. **Audit:** an explicitly heuristic 0–100 score across buyer vocabulary, comparable numeric specs, category attributes, structure and promotional language. All five components and exact rules are visible. It is not a calibrated selection probability.
2. **Simulate buyers:** your chosen ASIN plus seven real products associated with the same historical ESCI query. Every product receives a full rank, a reason, evidence references and missing-information questions. Measure selection rate, top-three rate and mean rank against a 1/N equal-share reference.
3. **Rewrite & retest:** reorder complete source passages into labelled bullets and structured attributes; prepend the existing brand where appropriate. Source details remain intact, including negations and caveats. Approve the proposed version, then repeat identical scenarios and candidate permutations.
4. **Fill gaps:** enter an actual specification with a source note and reviewer attestation. New facts remain visibly merchant-confirmed, not independently verified. Run a third stage and compare it with the rewritten stage. Existing claims cannot be silently overwritten.

All versions, approvals and runs are recorded locally. Export full rankings CSV, evidence HTML, listing JSON and complete experiment JSON. Historical results can be restored when the experiment context matches.

## Claude mode

```bash
export ANTHROPIC_API_KEY='your-key'
export ANTHROPIC_MODEL='a-model-id-available-to-your-account'
streamlit run app.py --server.address 127.0.0.1
```

Select **Claude API**. Enter a supported model ID or discover available account models in the sidebar. No example model names are assumed to exist. The official Anthropic SDK uses `client.messages.parse(..., output_format=PydanticModel)` for ranking and rewrite plans. There are at most three concurrent requests and one application-level retry; SDK retries are disabled. A 5-request × 3-repeat stage makes 15 initial calls. Review your provider's pricing before running multiple stages. No key is stored in the repository or reports. `.env.example` is documentation; `.env` is not loaded automatically.

Without a key, the offline baseline is explicitly labelled: 80% normalized BM25, 15% numeric-spec mentions, 5% category attribute mentions, plus small deterministic paired noise. The same per-product noise is reused before and after. This is a transparent pipeline demonstration, not Claude and not a validated proxy for actual buying decisions. Reformatting can mechanically affect this score.

## Real data and results

Source: [Amazon Science ESCI](https://github.com/amazon-science/esci-data). The included shelves cover air purifiers, baby sound machines, baby carriers, bark collars, 1TB SSDs and backpacks. Each contains eight distinct US products from the same source query, filtered to E/S labels, then selected by ascending ASIN without looking at simulation results. All agents are blinded to ESCI labels and merchant target identity.

Each shelf has five actual source search queries: its base query and related queries sharing at least two E/S-labelled shelf products. Rich custom buyer requests can be entered but are labelled merchant-authored. Source records are historical; **prices, live inventory and AI-purchase outcomes are absent**. Missing descriptions remain missing. No prices or purchase outcomes have been invented.

The reproducible observational analysis uses **40,000** distinct US query–product pairs:

| Query-token coverage | Pairs | Exact relevance rate |
|---|---:|---:|
| 0–25% | 6,142 | 43.19% |
| >25–50% | 9,593 | 56.38% |
| >50–75% | 9,012 | 65.59% |
| >75–100% | 15,253 | 88.13% |

Query-disjoint validation: 29,976 training pairs, 10,024 test pairs; ROC AUC approximately **0.728**, accuracy **0.711**, majority baseline **0.691**. Numeric specs and promotional-language coefficients are small in this particular fitted model; that is not proof they never matter. Feature definitions, counts, standardized coefficients and caveats are visible under **Data & methodology**. These are associations with search relevance, not causal effects or agent selection labels.

`outputs/amazon_offline.html` records the actual six-shelf baseline experiment: 90 before/after pairs, with unchanged results retained. It includes original and proposed rewrites only; no merchant facts were invented to manufacture a third-stage result. No real Claude run has been claimed: `ANTHROPIC_API_KEY` was not configured during implementation.

## Reproduce and test

```bash
# Only needed to rebuild compact source data (downloads roughly 1.1 GB):
python scripts/download_esci.py
python scripts/build_esci.py --sample-size 40000

# No network or credentials needed:
python scripts/evaluate_shelves.py --mode offline --repeats 3
python -m pytest -q

# Live controlled experiment, with your configured credentials:
python scripts/evaluate_shelves.py --mode claude --model "$ANTHROPIC_MODEL" --repeats 3
```

The raw Parquet files are excluded from Git. Checksums are in `data/esci/processed/manifest.json`. The 40,000 feature rows, shelf provenance, compact listings and analysis results are included. Dataset license and attribution are in `data/esci/LICENSE` and `data/esci/NOTICE`; derived records are modified subsets with HTML cleanup and bullet splitting. WANDS attribution is retained separately.

## Experiment integrity

- Shuffle products for each scenario/repeat; reuse identical order across stages.
- Freeze shelf, scenarios, target, model configuration and repeats into a context hash. Changing these clears active results.
- Require every shelf product exactly once in a ranking. Invalid IDs, missing evidence and invalid winners fail validation, then retry once.
- Abstentions stay in the successful-trial denominator. Failures are counted separately, never converted to wins or hidden.
- Paired deltas use common successful pairs. Complete rankings include unsuitable items; top-three rank is not eligibility.
- Evidence IDs establish traceability, not automatic semantic entailment. Human verification is still necessary.
- Quotes and data are untrusted input, never instructions. Extractive rewrite plans can select only actual source blocks.
- Repeated queries are correlated. No population or causal significance claim is made from the small simulation.
- Keep the same model and frozen scenarios while reviewing unchanged and negative outcomes.

## Structure and handoff

- `app.py`, `botshelf/shelf_ui.py`: the four-step Amazon workspace.
- `botshelf/shelf_engine.py`: blinded structured ranking, paired metrics, evidence-locked rewriting and merchant facts.
- `botshelf/shelf_audit.py`: transparent diagnostics and BM25 baseline.
- `scripts/build_esci.py`: real shelf construction and feature/logistic analysis.
- `legacy_app.py`, other `botshelf/` modules: retained WANDS lab.
- `docs/AMAZON_PROJECT_BRIEF.md`, `docs/AMAZON_DEMO_SCRIPT.md`: competition materials.
- `data/botshelf.sqlite`: local history, ignored by Git. Set `BOTSHELF_DB` for an isolated database.

Tests cover both workspaces, all four stages, source preservation, merchant attestation, complete ranking, failure/retry behavior, target blinding, data provenance, paired ordering and state isolation. Provider-mocked tests exercise the Claude contract; a real-provider smoke test, merchant interviews and real timing studies remain pending.
