from __future__ import annotations

import unittest
from collections import Counter, defaultdict

from src.eval.retrieval_dataset import (
    load_eval_personas,
    load_golden_records,
    load_shortlist_entries,
)


class RetrievalEvalArtifactsTests(unittest.TestCase):
    def test_seed_artifacts_have_expected_counts(self) -> None:
        personas = load_eval_personas()
        shortlist_entries = load_shortlist_entries()
        golden_records = load_golden_records()

        self.assertEqual(len(personas), 5)
        self.assertEqual(len(shortlist_entries), 50)
        self.assertEqual(len(golden_records), 15)

    def test_each_persona_has_three_golden_rows(self) -> None:
        golden_records = load_golden_records()

        counts = Counter(record.persona_id for record in golden_records)
        self.assertEqual(len(counts), 5)
        for persona_id, count in counts.items():
            self.assertEqual(count, 3, msg=f"{persona_id} should have 3 rows")

    def test_each_persona_has_positive_and_distractor_shortlists(self) -> None:
        shortlist_entries = load_shortlist_entries()

        roles_by_persona: dict[str, set[str]] = defaultdict(set)
        for entry in shortlist_entries:
            roles_by_persona[entry.persona_id].add(entry.role)

        self.assertEqual(len(roles_by_persona), 5)
        for persona_id, roles in roles_by_persona.items():
            self.assertTrue(
                {"core_positive", "central_fallback"}.intersection(roles),
                msg=f"{persona_id} should have at least one positive role",
            )
            self.assertTrue(
                any(role.startswith("distractor_") for role in roles),
                msg=f"{persona_id} should have at least one distractor role",
            )

    def test_golden_rows_reference_known_shortlist_scheme_ids(self) -> None:
        shortlist_entries = load_shortlist_entries()
        golden_records = load_golden_records()

        known_scheme_ids = {entry.scheme_id for entry in shortlist_entries}
        for record in golden_records:
            for scheme_id in record.must_retrieve_scheme_ids:
                self.assertIn(
                    scheme_id,
                    known_scheme_ids,
                    msg=f"{record.record_id} positive scheme missing from shortlist",
                )
            for scheme_id in record.must_not_retrieve_scheme_ids:
                self.assertIn(
                    scheme_id,
                    known_scheme_ids,
                    msg=f"{record.record_id} distractor scheme missing from shortlist",
                )


if __name__ == "__main__":
    unittest.main()
