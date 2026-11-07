# BotShelf: when the customer is a bot

## User and problem

Small Amazon merchants with limited catalog-management resources need to understand why an AI shopper might prefer a competitor. BotShelf audits product evidence and runs controlled, blinded shelf experiments. It does not claim that real agents only read text; this prototype deliberately isolates text fields to study one mechanism.

The product serves one actionable loop: inspect → simulate → rewrite with evidence → retest → confirm missing facts → retest. The main measure is the target's selection frequency against seven alternatives. Top-three frequency and average rank provide supporting context. The 12.5% line is an equal-probability reference, not an expected fair allocation for unequal products.

## Demonstrable product

The local Streamlit app uses six real ESCI shelves, each containing eight distinct products under one actual US query. Users can choose any ASIN as their target. Five source queries per shelf become buyer requests; custom requests remain explicitly user-authored. The original WANDS lab is retained as a separate research workspace.

The audit reveals five equally weighted heuristics and their limitations. Codex mode uses the official local CLI, JSON Schema and Pydantic validation to rank every product, cite evidence and identify missing information. The offline mode exposes its BM25/specification formula and seeded noise, so it can demonstrate the workflow without pretending to be a language model.

Rewriting is extractive: the model selects and orders complete source blocks instead of inventing new specifications. Brand placement, labelled bullets and structured attributes make the evidence easier to inspect. Original unselected details stay in the record. A merchant approves the version before retesting. New facts require a value, source reference and reviewer attestation; the product records them as merchant-confirmed rather than externally validated.

## Actual data and analysis

Source: https://github.com/amazon-science/esci-data. Included categories are air purifiers, baby sound machines, baby carriers, bark collars, 1TB SSDs and backpacks. Eight E/S-related products per query are selected by ascending ASIN; the method does not select targets based on favorable agent outcomes. ESCI labels never enter the shopping-model payload.

The analysis samples 40,000 distinct, non-conflicting US query–product pairs using a fixed seed. Coverage bins contain 6,142 / 9,593 / 9,012 / 15,253 pairs, with Exact rates of 43.19% / 56.38% / 65.59% / 88.13%. A standardized logistic model uses coverage, numeric expressions, attribute mentions, structure, promotional-word ratio and listing length. Query-disjoint held-out ROC AUC is about 0.728. Products may recur across different queries; this is not a product-disjoint evaluation.

These are observational relevance associations, not causal effects and not agent purchases. Small fitted coefficients do not establish that specifications or wording are universally irrelevant. ESCI does not supply real-time prices, stock or AI-agent transaction labels. The value proposition is to investigate that separate selection question through controlled experiments, then validate it externally.

## Evidence and boundaries

All before/after comparisons reuse scenarios, candidate permutations and model settings. The target identity is withheld from the buyer. Full rankings, reasons, unknowns, failures, abstentions, token counts and configuration hashes are exported. Paired deltas use only common successful trials and disclose excluded failures. The initial six-shelf offline report contains 90 paired trials and retains zero-lift categories; it is a synthetic scoring demonstration, not evidence of Codex or marketplace performance.

A frozen full live evaluation remains pending. The successful live Codex smoke test covers one eight-product ranking and one source-locked rewrite; it checks integration only, not performance lift. New merchant facts are not fabricated for the shipped results. Source citations ensure traceability but cannot by themselves prove every generated explanation follows from its evidence. Human review is needed, especially for ambiguous, safety-related or certification claims.

## Business hypothesis and next validation

A plausible offering is a small-SKU catalog diagnostic subscription or one-off audit. Its value must be tested through merchant usability, measured time savings and eventually real channel outcomes. Interview two or three merchants, run the frozen live evaluation and compare original versus assisted catalog work before making revenue or conversion claims. The current deliverable is a usable evidence workflow and reproducible experiment, not a validated commercial growth promise.
