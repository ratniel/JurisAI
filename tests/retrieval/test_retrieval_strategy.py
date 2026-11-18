import unittest
from unittest.mock import Mock

from qdrant_client import models
from src.config.settings import settings
from src.retrieval.qdrant_search import QdrantSchemeSearchClient


class RetrievalStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.search = object.__new__(QdrantSchemeSearchClient)
        self.search._client = Mock()
        self.search._collection_name = "test"
        self.search._collection_capabilities = {"named_dense": True, "sparse": True}

    def query(self, strategy: str, sparse: models.SparseVector | None = None):
        return self.search._query_profile_points(
            profile_name="embedding_a", query_filter=None,
            dense_query_vector=[0.2, 0.8],
            sparse_query_vector=sparse if sparse is not None else models.SparseVector(indices=[1], values=[1.0]),
            limit=5, retrieval_strategy=strategy,
        )

    def test_dense_uses_the_named_dense_vector(self) -> None:
        self.query("dense")
        kwargs = self.search._client.query_points.call_args.kwargs
        self.assertEqual(kwargs["using"], settings.qdrant.dense_vector_name)
        self.assertEqual(kwargs["query"], [0.2, 0.8])

    def test_sparse_uses_the_sparse_slot(self) -> None:
        self.query("sparse")
        kwargs = self.search._client.query_points.call_args.kwargs
        self.assertEqual(kwargs["using"], settings.qdrant.sparse_vector_name)
        self.assertIsInstance(kwargs["query"], models.SparseVector)

    def test_hybrid_fuses_two_scoped_prefetches(self) -> None:
        self.query("hybrid")
        kwargs = self.search._client.query_points.call_args.kwargs
        self.assertEqual(kwargs["query"].fusion, models.Fusion.RRF)
        self.assertEqual(len(kwargs["prefetch"]), 2)
        for prefetch in kwargs["prefetch"]:
            self.assertEqual(prefetch.filter.must[-1].match.value, "embedding_a")
            self.assertEqual(prefetch.limit, 5)

    def test_missing_sparse_slot_fails_without_querying(self) -> None:
        self.search._collection_capabilities = {"named_dense": True, "sparse": False}
        with self.assertRaisesRegex(ValueError, "does not expose sparse vectors"):
            self.query("hybrid")
        self.search._client.query_points.assert_not_called()

    def test_empty_sparse_query_falls_back_to_dense(self) -> None:
        self.query("hybrid", models.SparseVector(indices=[], values=[]))
        self.assertEqual(self.search._client.query_points.call_args.kwargs["query"], [0.2, 0.8])

    def test_unknown_strategy_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported retrieval strategy"):
            self.search._resolve_retrieval_strategy(retrieval_strategy="unknown")
