import json
from types import SimpleNamespace
import pytest
from botshelf.shelf_models import Listing, Shelf, BuyerScenario, RewritePlan, ShelfRanking
from botshelf.shelf_audit import audit_listing, source_blocks
from botshelf.shelf_engine import (ShelfEngine, run_shelf, run_trial, compare_shelves,
    rewrite_listing, add_merchant_fact, agent_product, validate_ranking, offline_rank)
from botshelf.catalog import ROOT


@pytest.fixture
def shelf():
    products=[Listing(product_id=str(i),title=f"Brand{i} air purifier",brand=f"Brand{i}",
        bullets=["HEPA filter included.","Covers 300 square feet.","Noise level: 25 dB.","Uses 20 watts.","Not suitable for outdoor use."],
        description="Manufacturer states indoor use only.") for i in range(8)]
    return Shelf(shelf_id="fixture",category="Air purifiers",query_id="q",query="air purifier",products=products,
        scenarios=[BuyerScenario(scenario_id="q",text="quiet air purifier",source_query_id="q")],selection_note="Test fixture")


def test_rubric_bounded_and_not_probability(shelf):
    audit=audit_listing(shelf.products[0],shelf.query,shelf.category)
    assert 0<=audit["score"]<=100
    assert len(audit["components"])==5
    assert not audit["attribute_presence"]["Warranty"]
    assert "not selection probability" in audit["method"]


def test_all_products_ranked_and_pair_order_preserved(shelf):
    engine=ShelfEngine()
    before=run_shelf(shelf,"0",engine)
    variant=shelf.products[0].model_copy(update={"description":"Additional formatting, same facts."})
    after=run_shelf(shelf,"0",engine,variant)
    assert before["context_hash"]==after["context_hash"]
    assert before["variant_hash"]!=after["variant_hash"]
    assert all(len(t["result"]["ranking"])==8 for t in before["trials"])
    assert [t["candidate_order"] for t in before["trials"]]==[t["candidate_order"] for t in after["trials"]]
    assert compare_shelves(before,after)["paired_trials"]==3
    assert before["metrics"]["equal_share_reference"]==.125


def test_offline_order_invariance_and_repeatability(shelf):
    a=offline_rank(shelf.scenarios[0],shelf.products,shelf.category,17)
    b=offline_rank(shelf.scenarios[0],list(reversed(shelf.products)),shelf.category,17)
    assert a==b


def test_changed_scenarios_not_comparable(shelf):
    a=run_shelf(shelf,"0",ShelfEngine())
    shelf.scenarios[0].text="Another request"
    b=run_shelf(shelf,"0",ShelfEngine())
    with pytest.raises(ValueError): compare_shelves(a,b)


def test_rewrite_preserves_facts_and_negation(shelf):
    p=shelf.products[0]; original=p.model_dump_json()
    proposal=rewrite_listing(p,shelf.query,shelf.category,ShelfEngine())
    assert proposal["status"]=="ok"
    revised=Listing.model_validate(proposal["listing"])
    assert "Not suitable for outdoor use." in revised.description
    assert p.model_dump_json()==original
    allowed={b.block_id:b.text for b in source_blocks(p)}
    assert all(allowed[b.block_id]==b.text for b in revised.attributes)
    assert not revised.merchant_facts


def test_merchant_completion_requires_source_and_no_override(shelf):
    p=shelf.products[0]
    with pytest.raises(ValueError): add_merchant_fact(p,"Warranty","2 years","","reviewer",shelf.category)
    revised=add_merchant_fact(p,"Warranty","2 years limited","Test-only source fixture","Fixture reviewer",shelf.category)
    assert not p.merchant_facts and len(revised.merchant_facts)==1
    with pytest.raises(ValueError): add_merchant_fact(revised,"Warranty","3 years","source","reviewer",shelf.category)
    assert "Fixture reviewer" not in json.dumps(agent_product(revised))
    assert "Test-only source fixture" not in json.dumps(agent_product(revised))
    assert "2 years limited" in json.dumps(agent_product(revised))


class FakeClient:
    def __init__(self,response=None,error=None): self.response=response; self.error=error; self.calls=[]
    def structured(self,schema,system,payload,model):
        kwargs=dict(schema=schema,system=system,payload=payload,model=model)
        self.calls.append(kwargs)
        if self.error: raise self.error
        return self.response,10,5


def test_codex_structured_contract_and_blinding(shelf):
    result=offline_rank(shelf.scenarios[0],shelf.products,shelf.category,1)
    client=FakeClient(result)
    engine=ShelfEngine("codex",model="test-model",client=client)
    trial=run_trial(engine,shelf.scenarios[0],shelf.products,shelf.category,0)
    assert trial.status=="ok" and trial.api_calls==1 and trial.input_tokens==10
    call=client.calls[0]
    assert call["schema"] is ShelfRanking
    payload=call["payload"]
    assert "target_id" not in payload and "esci_label" not in json.dumps(payload)
    assert "UNTRUSTED DATA" in call["system"]


@pytest.mark.parametrize("fault",["duplicate","missing","fake_evidence","wrong_winner"])
def test_invalid_ranking_retried_then_failed(shelf,fault):
    result=offline_rank(shelf.scenarios[0],shelf.products,shelf.category,1)
    if fault=="duplicate": result.ranking[1]=result.ranking[0]
    if fault=="missing": result.ranking.pop()
    if fault=="fake_evidence": result.ranking[0].evidence_ids=["invented"]
    if fault=="wrong_winner": result.selected_id=result.ranking[1].product_id
    client=FakeClient(result)
    trial=run_trial(ShelfEngine("codex","test",client),shelf.scenarios[0],shelf.products,shelf.category,0)
    assert trial.status=="failed" and trial.api_calls==2 and len(client.calls)==2


def test_failed_runs_retained_in_metrics(shelf):
    client=FakeClient(error=RuntimeError("credential-do-not-leak"))
    batch=run_shelf(shelf,"0",ShelfEngine("codex","test",client))
    assert batch["metrics"]["failed_trials"]==3
    assert batch["metrics"]["selection_rate"] is None
    assert "credential-do-not-leak" not in json.dumps(batch)


def test_rewrite_rejects_hallucinated_source(shelf):
    client=FakeClient(RewritePlan(ordered_block_ids=["imagined-warranty"],decisive_block_id=None,merchant_questions=[]))
    proposal=rewrite_listing(shelf.products[0],shelf.query,shelf.category,ShelfEngine("codex","test",client))
    assert proposal["status"]=="failed" and proposal["api_calls"]==2


def test_real_shelves_and_labels_kept_separate():
    import pandas as pd
    path=ROOT/"data/esci/processed"
    shelves=[Shelf.model_validate(s) for s in json.loads((path/"shelves.json").read_text())]
    provenance=pd.read_csv(path/"shelf_provenance.csv",dtype=str)
    assert len(shelves)==6
    for shelf in shelves:
        assert len(set(p.product_id for p in shelf.products))==8
        rows=provenance[provenance.shelf_id==shelf.shelf_id]
        assert set(rows.query_id)=={shelf.query_id}
        assert set(rows.esci_label)<={"E","S"}
        assert set(rows.product_id)=={p.product_id for p in shelf.products}
        assert all(s.origin=="ESCI real query" for s in shelf.scenarios)
        assert "esci_label" not in json.dumps([agent_product(p) for p in shelf.products])
    analysis=json.loads((path/"analysis.json").read_text())
    assert analysis["query_disjoint"] and analysis["sample_pairs"]==40000
    assert sum(b["pairs"] for b in analysis["coverage_bins"])==40000
