"""Amazon shelf experiment contracts. ESCI labels never belong to Listing."""
from typing import List, Literal, Optional
from pydantic import Field
from .models import StrictModel


class SourceBlock(StrictModel):
    block_id: str
    field: str
    text: str


class MerchantFact(StrictModel):
    attribute: str
    value: str
    source_note: str
    confirmed_by: str
    confirmed_at: str


class Listing(StrictModel):
    product_id: str
    title: str
    bullets: List[str] = Field(default_factory=list)
    description: str = ""
    brand: str = ""
    color: str = ""
    locale: str = "us"
    attributes: List[SourceBlock] = Field(default_factory=list)
    merchant_facts: List[MerchantFact] = Field(default_factory=list)


class BuyerScenario(StrictModel):
    scenario_id: str
    text: str
    origin: str = "ESCI real query"
    source_query_id: Optional[str] = None


class Shelf(StrictModel):
    shelf_id: str
    category: str
    query_id: str
    query: str
    products: List[Listing]
    scenarios: List[BuyerScenario]
    selection_note: str


class RankedItem(StrictModel):
    product_id: str
    reason: str
    evidence_ids: List[str]
    missing_information: List[str]
    suitability: Literal["supported", "uncertain", "mismatch"]


class ShelfRanking(StrictModel):
    ranking: List[RankedItem]
    selected_id: Optional[str]
    selection_reason: str


class RewritePlan(StrictModel):
    # IDs select complete source blocks, so numbers, negations and qualifiers survive.
    ordered_block_ids: List[str]
    decisive_block_id: Optional[str]
    merchant_questions: List[str]


class ShelfTrial(StrictModel):
    scenario_id: str
    scenario: str
    repeat: int
    candidate_order: List[str]
    status: Literal["ok", "failed"]
    result: Optional[ShelfRanking] = None
    error: Optional[str] = None
    api_calls: int = 0
    elapsed_s: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
