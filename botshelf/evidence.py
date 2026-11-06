"""Conservative extraction: ambiguous attributes remain ambiguous."""
import re
from typing import List
from .models import Constraint, Evidence, Fact, Issue, Need, Product, Revision

ALIASES = {"topmaterial": "top_material", "tableshape": "shape",
           "seatingcapacity": "seats", "overallwidth-sidetoside": "width_cm"}
SUPPORTED = tuple(ALIASES.values())


def dimension_cm(text):
    match = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(cm|mm|inches|inch|in|\"|\'\')\s*', text, re.I)
    if not match:
        return None
    number, unit = match.groups()
    return round(float(number) * ({"cm": 1, "mm": .1}.get(unit.lower(), 2.54)), 4)


def facts(product: Product):
    result = {key: [] for key in SUPPORTED}
    for segment in product.features.split("|"):
        if ":" not in segment:
            continue
        key, value = segment.split(":", 1)
        attr = ALIASES.get(key.strip().lower())
        value = value.strip().lower()
        if not attr or not value:
            continue
        if attr == "width_cm":
            converted = dimension_cm(value)
            if converted is None:
                continue
            value = str(converted)
        if attr == "seats" and not re.fullmatch(r"\d+(?:\.\d+)?", value):
            continue
        result[attr].append(Fact(value=value, evidence=Evidence(field="features", quote=segment)))
    # Only explicit, axis-labelled dimensions are taken from prose.
    for field in ("name", "description"):
        content = getattr(product, field)
        for match in re.finditer(r'\bwidth\s*[:=]?\s*(\d+(?:\.\d+)?\s*(?:cm|mm|inches|inch|in\b|\"|\'\'))', content, re.I):
            result["width_cm"].append(Fact(value=str(dimension_cm(match.group(1))),
                evidence=Evidence(field=field, quote=match.group(0))))
    for attr, values in product.structured.items():
        if attr in result:
            result[attr].extend(values)
    return result


def evidence_exists(product, evidence):
    return evidence.field in ("name", "description", "features") and bool(evidence.quote.strip()) and evidence.quote in getattr(product, evidence.field)


def check_constraint(product: Product, constraint: Constraint):
    extracted = facts(product)[constraint.attribute]
    values = set(f.value for f in extracted)
    if not values:
        return "unknown"
    if len(values) > 1:
        return "conflict"
    value = next(iter(values))
    if constraint.operator == "eq":
        meets = value.casefold() == constraint.value.casefold()
    else:
        try:
            meets = float(value) >= float(constraint.value) if constraint.operator == "gte" else float(value) <= float(constraint.value)
        except ValueError:
            return "unknown"
    return "met" if meets else "unmet"


def audit_product(product: Product, need: Need) -> List[Issue]:
    extracted = facts(product)
    issues = []
    required = {c.attribute: c for c in need.constraints}
    for attr in dict.fromkeys(list(required) + list(SUPPORTED)):
        values = extracted[attr]
        evidence = [v.evidence for v in values]
        if len(set(v.value for v in values)) > 1:
            issues.append(Issue(attribute=attr, kind="conflict", explanation="Multiple explicit values; confirm the exact variant before editing.", evidence=evidence))
        elif attr in required and check_constraint(product, required[attr]) == "unmet":
            issues.append(Issue(attribute=attr, kind="mismatch", explanation="The known product fact does not meet this requirement. Copy edits cannot fix it.", evidence=evidence))
        elif not values and attr in required:
            issues.append(Issue(attribute=attr, kind="missing", explanation="No unambiguous, supported fact. Ask the merchant; do not infer missing units.", evidence=[]))
        elif values and attr not in product.structured:
            issues.append(Issue(attribute=attr, kind="unclear", explanation="Fact exists in source text; expose it as a named, evidence-linked attribute.", evidence=evidence))
    return issues


def propose_revision(product: Product, issues: List[Issue], source=None) -> List[Revision]:
    source = source or product
    current, original = facts(product), facts(source)
    revisions = []
    for issue in issues:
        attr = issue.attribute
        values = original.get(attr, [])
        if issue.kind in ("conflict", "mismatch") or len(set(f.value for f in values)) != 1:
            continue
        fact = values[0]
        if not evidence_exists(source, fact.evidence):
            continue
        revisions.append(Revision(attribute=attr, old_value=", ".join(sorted(set(f.value for f in current[attr]))) or "Unknown",
            new_value=fact.value, evidence=fact.evidence,
            reason="Expose an existing source fact; no new claim." if source == product else "Restore an explicitly hidden fact from the original source (synthetic experiment)."))
    return revisions


def apply_revisions(product, revisions, source):
    revised = product.model_copy(deep=True)
    source_facts = facts(source)
    for revision in revisions:
        available = source_facts.get(revision.attribute, [])
        if len(set(f.value for f in available)) != 1 or not any(f.value == revision.new_value and f.evidence == revision.evidence for f in available):
            raise ValueError("Revision is unsupported or ambiguous")
        if not evidence_exists(source, revision.evidence):
            raise ValueError("Missing source evidence")
        # Restoring a hidden segment preserves the exact source fragment.
        field = revision.evidence.field
        if not evidence_exists(revised, revision.evidence):
            original_text = getattr(revised, field)
            setattr(revised, field, original_text + ("|" if field == "features" else " ") + revision.evidence.quote)
        revised.structured[revision.attribute] = [Fact(value=revision.new_value, evidence=revision.evidence)]
    return revised


def mask_attribute(product, attribute):
    """Remove all evidence surfaces for the selected attribute; do not leak truth to buyer."""
    masked = product.model_copy(deep=True)
    # In B, prose is withheld for ALL candidates to prevent material/shape leakage.
    masked.name = "Dining table " + product.product_id
    masked.description = ""
    masked.features = "|".join(seg for seg in product.features.split("|")
        if ALIASES.get(seg.split(":", 1)[0].strip().lower()) != attribute)
    masked.structured.pop(attribute, None)
    return masked
