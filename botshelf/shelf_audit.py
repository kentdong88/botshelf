"""Transparent heuristic diagnostics, not a learned selection probability."""
import hashlib
import html
import math
import re
from collections import Counter
from .shelf_models import Listing, SourceBlock

STOP = set("a an the for with and or of to in on by is it at from this that as your you can be are has have its our we not".split())
FLUFF = ("best quality", "premium quality", "perfect gift", "must have", "amazing", "incredible", "best ever", "top quality", "unmatched", "ultimate")
SPEC = re.compile(r"\b\d+(?:\.\d+)?\s*(?:sq\.?\s*ft|square feet|ft²|m²|cm|mm|inches|inch|lbs?|kg|oz|db|watts?|w|mah|hours?|months?|years?|tb|gb|mb/s|gb/s|hz|khz|l|liters?|percent|%)\b", re.I)
SLOTS = {
    "Air purifiers": {"Coverage": r"sq\.?\s*ft|square feet|ft²|m²", "Filtration": r"hepa|filter|filtration", "Noise": r"\bdb\b|decibel", "Power": r"\bwatts?\b|\d\s*w\b", "Warranty": r"warranty|guarantee"},
    "Baby sound machines": {"Sound modes": r"sounds?|noise", "Power": r"battery|usb|adapter|recharge", "Timer": r"timer|auto.off", "Volume": r"volume|decibel|\bdb\b", "Warranty": r"warranty|guarantee"},
    "Baby carriers": {"Weight limits": r"\d[\d .-]*(?:lb|pound|kg)", "Material": r"cotton|polyester|mesh|fabric", "Carry positions": r"position|front|back|facing", "Fit": r"waist|adjustable|size", "Care": r"wash|clean"},
    "Bark collars": {"Dog size": r"\d[\d .-]*(?:lb|pound|kg)|small|medium|large", "Modes": r"vibrat|beep|spray|static|shock", "Power": r"battery|recharge|usb", "Water resistance": r"waterproof|water.resistan|\bip\d", "Adjustability": r"adjust|sensitivity|levels?"},
    "1TB SSDs": {"Capacity": r"\d\s*(?:tb|gb)\b", "Interface": r"nvme|sata|pcie|usb|m\.2", "Speed": r"\d[\d ,.]*(?:mb/s|gb/s)", "Compatibility": r"compatible|windows|mac|linux|laptop|desktop", "Warranty": r"warranty|guarantee"},
    "Backpacks": {"Capacity": r"\d[\d .]*(?:liters?|litres?|l)\b", "Dimensions": r"\d[\d .x×]*(?:inch|cm|mm)|dimensions", "Material": r"nylon|polyester|leather|canvas|fabric", "Laptop fit": r"laptop|notebook", "Water resistance": r"waterproof|water.resistan"},
}


def clean_text(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<(?:br\s*/?|/p|/li)\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP]


def listing_text(p):
    return " ".join([p.title, *p.bullets, p.description, p.brand, p.color,
                     *(a.text for a in p.attributes), *(f.attribute+": "+f.value for f in p.merchant_facts)])


def source_blocks(p: Listing):
    blocks = []
    for field, texts in (("title", [p.title]), ("brand", [p.brand]), ("color", [p.color]),
                         ("bullets", p.bullets), ("description", re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", p.description))):
        for text in texts:
            if text.strip():
                digest = hashlib.sha256((field+"\0"+text).encode()).hexdigest()[:16]
                blocks.append(SourceBlock(block_id=field+"-"+digest, field=field, text=text.strip()))
    for fact in p.merchant_facts:
        text = fact.attribute+": "+fact.value
        digest = hashlib.sha256((text+fact.source_note+fact.confirmed_at).encode()).hexdigest()[:16]
        blocks.append(SourceBlock(block_id="merchant-"+digest, field="merchant_confirmed", text=text))
    blocks.extend(p.attributes)
    # The same fact can appear in several fields; ids remain exact and stable.
    return list({b.block_id:b for b in blocks}.values())


def audit_listing(p, query, category):
    text = listing_text(p)
    terms = set(tokens(query))
    present = terms & set(tokens(text))
    missing_terms = sorted(terms-present)
    overlap = len(present)/len(terms) if terms else 0
    specs = list(dict.fromkeys(m.group() for m in SPEC.finditer(text)))
    slots = SLOTS[category]
    presence = {k: bool(re.search(pattern, text, re.I)) for k,pattern in slots.items()}
    fluffy = {phrase: len(re.findall(re.escape(phrase), text.lower())) for phrase in FLUFF}
    fluff_tokens = sum(len(phrase.split())*count for phrase,count in fluffy.items())
    words = max(1, len(text.split()))
    fluff_ratio = min(1, fluff_tokens/words)
    scores = {"Buyer vocabulary": round(20*overlap,1), "Comparable specs": round(20*min(len(specs)/5,1),1),
              "Decision attributes": round(20*sum(presence.values())/len(presence),1),
              "Structure": round(20*(bool(p.title)+min(len(p.bullets)/5,1)+bool(p.description))/3,1),
              "Low fluff": round(20*max(0,1-fluff_ratio/.1),1)}
    issues = []
    if missing_terms: issues.append("Buyer terms absent: "+", ".join(missing_terms)+". Add only when supported by facts.")
    if len(specs)<5: issues.append(f"{len(specs)} explicit number + unit expressions found; inspect missing comparable specifications.")
    issues.extend("No detected mention of "+k+"; confirm before adding a claim." for k,v in presence.items() if not v)
    if len(p.bullets)<5: issues.append(f"Only {len(p.bullets)} bullet(s); do not invent facts to reach five.")
    if not p.description: issues.append("Description is absent in the dataset.")
    if fluff_tokens: issues.append("Promotional phrases detected: "+", ".join(k for k,v in fluffy.items() if v))
    return {"score": round(sum(scores.values()),1), "components": scores, "query_coverage": overlap,
            "spec_count": len(specs), "spec_examples": specs, "attribute_presence": presence,
            "fluff_ratio": fluff_ratio, "issues": issues,
            "method": "Five equal 20-point heuristics. Mentions are not verified facts; this is not selection probability."}


def bm25_scores(query, documents):
    corpus = [tokens(d) for d in documents]
    n = len(corpus)
    avg = sum(len(d) for d in corpus)/max(n,1) or 1
    terms = set(tokens(query))
    df = {term: sum(term in d for d in corpus) for term in terms}
    scores = []
    for doc in corpus:
        freq = Counter(doc)
        score = 0.0
        for term in terms:
            f = freq[term]
            idf = math.log(1+(n-df[term]+.5)/(df[term]+.5))
            score += idf*f*2.5/(f+1.5*(1-.75+.75*len(doc)/avg)) if f else 0
        scores.append(score)
    return scores
