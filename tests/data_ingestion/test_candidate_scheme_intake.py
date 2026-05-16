from __future__ import annotations

import unittest

from src.data_ingestion.candidate_scheme_intake import (
    CandidateScheme,
    canonicalize_url,
    is_supported_scheme_url,
)


class CandidateSchemeIntakeTests(unittest.TestCase):
    def test_canonicalize_url_strips_query_and_fragment(self) -> None:
        self.assertEqual(
            canonicalize_url("https://www.myscheme.gov.in/schemes/pmfby?x=1#section"),
            "https://www.myscheme.gov.in/schemes/pmfby",
        )

    def test_supported_scheme_url_requires_canonical_myscheme_path(self) -> None:
        self.assertTrue(
            is_supported_scheme_url("https://www.myscheme.gov.in/schemes/pmfby")
        )
        self.assertFalse(
            is_supported_scheme_url("https://www.myscheme.gov.in/search")
        )
        self.assertFalse(
            is_supported_scheme_url("https://example.com/schemes/pmfby")
        )

    def test_candidate_scheme_model_accepts_minimal_shape(self) -> None:
        candidate = CandidateScheme.model_validate(
            {"name": "PMFBY", "url": "https://www.myscheme.gov.in/schemes/pmfby"}
        )
        self.assertEqual(candidate.name, "PMFBY")


if __name__ == "__main__":
    unittest.main()
