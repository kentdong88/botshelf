import json
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .models import Need, Product

ROOT = Path(__file__).resolve().parents[1]


def load_catalog(path=None):
    items = [Product.model_validate(x) for x in json.loads(Path(path or ROOT / "data/processed/catalog.json").read_text())]
    if len({p.product_id for p in items}) != len(items):
        raise ValueError("Duplicate product IDs")
    return items


def load_needs(path=None):
    return [Need.model_validate(x) for x in json.loads(Path(path or ROOT / "data/processed/needs.json").read_text())]


class Retriever:
    def __init__(self, products):
        self.products = products
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.matrix = self.vectorizer.fit_transform([p.name+" "+p.description+" "+p.features for p in products])

    def search(self, text, limit=15):
        scores = (self.matrix @ self.vectorizer.transform([text]).T).toarray().ravel()
        order = np.argsort(-scores, kind="stable")[:limit]
        return [self.products[i] for i in order if scores[i] > 0]
