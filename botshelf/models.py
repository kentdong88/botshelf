from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    field: str
    quote: str


class Fact(StrictModel):
    value: str
    evidence: Evidence


class Product(StrictModel):
    product_id: str
    name: str
    category: str
    description: str = ""
    features: str = ""
    source: str = "WANDS"
    structured: Dict[str, List[Fact]] = Field(default_factory=dict)


class Constraint(StrictModel):
    attribute: Literal["top_material", "shape", "seats", "width_cm"]
    operator: Literal["eq", "gte", "lte"] = "eq"
    value: str


class Need(StrictModel):
    need_id: str
    text: str
    constraints: List[Constraint] = Field(default_factory=list)
    preferences: str = ""
    target_id: str = ""
    split: Literal["dev", "test", "custom"] = "custom"
    origin: str = "team-authored"
    reviewed: bool = False
    truth_evidence: List[Evidence] = Field(default_factory=list)


class Issue(StrictModel):
    attribute: str
    kind: Literal["missing", "unclear", "conflict", "mismatch"]
    explanation: str
    evidence: List[Evidence] = Field(default_factory=list)


class Revision(StrictModel):
    attribute: str
    old_value: str
    new_value: str
    evidence: Evidence
    reason: str


class Assessment(StrictModel):
    product_id: str
    statuses: List[Literal["met", "unmet", "unknown", "conflict"]]
    evidence: List[Evidence] = Field(default_factory=list)
    reason: str


class ShoppingResult(StrictModel):
    recommendations: List[str] = Field(default_factory=list, max_length=3)
    assessments: List[Assessment]


class Run(StrictModel):
    status: Literal["ok", "failed"]
    engine: str
    config_hash: str
    elapsed_s: float
    api_calls: int = 0
    error: Optional[str] = None
    result: Optional[ShoppingResult] = None
