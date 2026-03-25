# Intentionally Unmapped Scheme-Brand Tags

These tags are intentionally not mapped to any topic because they behave like scheme-brand labels, commemorative names, or proper nouns rather than domain labels.

## Current Policy

- Keep these tags unmapped in `topics`.
- Let other tags on the same scheme determine the topic.
- Track them explicitly so we do not accidentally treat them as domain signals later.

## Known Examples From The Unique Tag Set

- Abdul Kalam
- Ambedkar
- Atal
- Atal Sneh
- Banglar Yuba Sathi
- Bhimrao Ambedkar
- BIG
- Bose
- CLSS
- DAYALU-II
- Maulana Azad
- Sardar Patel

## Current Hits In `test_schemes`

- `Atal`
  - `Atal Beemit Vyakti Kalyan Yojana`
  - Topic still inferred from other tags: `Employment`
- `Maulana Azad`
  - `Maulana Azad Education Finance Foundation Scheme`
  - Topic still inferred from other tags: `Education`

## Notes

- These tags are safe to keep outside the topic mapper because they do not describe a sector on their own.
- If a future scheme has only scheme-brand tags and no sector tags, it should remain topic-empty and be flagged for manual review.
