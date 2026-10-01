from __future__ import annotations

from functools import lru_cache

from qdrant_client import models
from sklearn.feature_extraction.text import HashingVectorizer

from src.config.settings import settings


def _normalize_text(value: str) -> str:
    return " ".join(value.replace("\ufeff", " ").split()).strip()


@lru_cache(maxsize=8)
def _build_vectorizer(
    n_features: int,
    max_ngram: int,
) -> HashingVectorizer:
    return HashingVectorizer(
        n_features=n_features,
        alternate_sign=False,
        lowercase=True,
        norm=None,
        strip_accents="unicode",
        token_pattern=r"(?u)\b\w+\b",
        ngram_range=(1, max_ngram),
    )


def build_sparse_keyword_vector(
    text: str,
    *,
    n_features: int = settings.qdrant.sparse_keyword_dimensions,
    max_ngram: int = 2,
) -> models.SparseVector:
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return models.SparseVector(indices=[], values=[])

    row = _build_vectorizer(n_features, max_ngram).transform([normalized_text]).tocsr()
    return models.SparseVector(
        indices=row.indices.tolist(),
        values=row.data.astype(float).tolist(),
    )
